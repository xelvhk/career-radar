import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from career_radar import OpportunityStore
from career_radar.collected_vacancy import (
    CollectedVacancyInput,
    normalize_collected_vacancy,
)
from career_radar.matching import MatchReport
from career_radar.vacancy import Vacancy


UTC_TIME = datetime(2026, 8, 22, 9, 30, tzinfo=timezone.utc)


class OpportunityStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "inbox.sqlite3"

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_initializes_schema_version_one_with_private_permissions(self) -> None:
        OpportunityStore(self.db_path)

        with closing(sqlite3.connect(self.db_path)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(opportunities)")
            }

        self.assertEqual(version, 1)
        self.assertIn("vacancy_id", columns)
        self.assertIn("description", columns)
        self.assertIn("report_json", columns)
        if os.name == "posix":
            self.assertEqual(self.db_path.stat().st_mode & 0o777, 0o600)

    def test_upserts_one_vacancy_and_preserves_human_status(self) -> None:
        store = OpportunityStore(self.db_path)
        first = store.upsert(self._vacancy(), self._report("REVIEW", 72), UTC_TIME)
        store.set_status(first.opportunity.vacancy.id, "shortlisted")
        second = store.upsert(
            self._vacancy(
                retrieved_at=UTC_TIME + timedelta(hours=1),
                description="Updated FastAPI and PostgreSQL role",
                source_url="https://hh.ru/vacancy/12345?from=favorites",
            ),
            self._report("APPLY", 88),
            UTC_TIME + timedelta(hours=1, minutes=1),
        )

        self.assertTrue(first.created)
        self.assertFalse(first.stale)
        self.assertFalse(second.created)
        self.assertFalse(second.stale)
        self.assertEqual(second.opportunity.seen_count, 2)
        self.assertEqual(second.opportunity.status, "shortlisted")
        self.assertEqual(second.opportunity.recommendation, "APPLY")
        self.assertEqual(second.opportunity.overall_score, 88)
        self.assertEqual(
            second.opportunity.vacancy.description,
            "Updated FastAPI and PostgreSQL role",
        )
        self.assertEqual(len(store.list()), 1)

    def test_stale_observation_changes_nothing(self) -> None:
        store = OpportunityStore(self.db_path)
        current = self._vacancy(retrieved_at=UTC_TIME + timedelta(days=1))
        saved = store.upsert(
            current,
            self._report("APPLY", 90),
            UTC_TIME + timedelta(days=1),
        )
        stale = store.upsert(
            self._vacancy(description="stale private marker"),
            self._report("SKIP", 10),
            UTC_TIME + timedelta(days=2),
        )

        self.assertTrue(stale.stale)
        self.assertFalse(stale.created)
        self.assertEqual(stale.opportunity, saved.opportunity)
        self.assertEqual(stale.opportunity.seen_count, 1)
        self.assertNotIn("stale private marker", self.db_path.read_bytes().decode("utf-8", errors="ignore"))

    def test_equal_timestamp_is_an_accepted_repeat_observation(self) -> None:
        store = OpportunityStore(self.db_path)
        store.upsert(self._vacancy(), self._report("REVIEW", 72), UTC_TIME)

        result = store.upsert(self._vacancy(), self._report("REVIEW", 72), UTC_TIME)

        self.assertFalse(result.stale)
        self.assertEqual(result.opportunity.seen_count, 2)

    def test_different_deterministic_ids_are_not_merged(self) -> None:
        store = OpportunityStore(self.db_path)
        store.upsert(self._vacancy(source_vacancy_id="12345"), self._report("APPLY", 90), UTC_TIME)
        store.upsert(self._vacancy(source_vacancy_id="67890"), self._report("APPLY", 90), UTC_TIME)

        self.assertEqual(len(store.list()), 2)

    def test_list_filters_and_sorts_deterministically(self) -> None:
        store = OpportunityStore(self.db_path)
        records = (
            ("apply-low", "APPLY", 70, UTC_TIME),
            ("apply-high", "APPLY", 90, UTC_TIME),
            ("review", "REVIEW", 99, UTC_TIME + timedelta(days=1)),
            ("skip", "SKIP", 99, UTC_TIME + timedelta(days=2)),
        )
        for source_id, recommendation, score, retrieved_at in records:
            result = store.upsert(
                self._vacancy(
                    source_vacancy_id=source_id,
                    retrieved_at=retrieved_at,
                ),
                self._report(recommendation, score),
                retrieved_at,
            )
            if source_id == "review":
                store.set_status(result.opportunity.vacancy.id, "dismissed")

        ordered = store.list()
        filtered = store.list(recommendation="REVIEW", status="dismissed")

        self.assertEqual(
            [item.overall_score for item in ordered],
            [90, 70, 99, 99],
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].recommendation, "REVIEW")
        self.assertEqual(filtered[0].status, "dismissed")

    def test_get_and_set_status_reject_unknown_ids_or_values(self) -> None:
        store = OpportunityStore(self.db_path)

        with self.assertRaisesRegex(ValueError, "opportunity was not found"):
            store.get("vac-" + "0" * 64)
        with self.assertRaisesRegex(ValueError, "status must be one of"):
            store.set_status("vac-" + "0" * 64, "applied")
        with self.assertRaisesRegex(ValueError, "vacancy_id must match"):
            store.get("not-an-id")
        with self.assertRaisesRegex(ValueError, "limit must be between 1 and 100"):
            store.list(limit=101)

    def test_rejects_sensitive_url_query_without_echoing_it(self) -> None:
        store = OpportunityStore(self.db_path)
        urls = (
            "https://hh.ru/vacancy/12345?access_token=private-value",
            "https://hh.ru/vacancy/12345?TOKEN",
        )
        for source_url in urls:
            with self.subTest(source_url=source_url):
                vacancy = self._vacancy(source_url=source_url)
                with self.assertRaises(ValueError) as context:
                    store.upsert(vacancy, self._report("REVIEW", 72), UTC_TIME)
                self.assertIn("sensitive query parameter", str(context.exception))
                self.assertNotIn("private-value", str(context.exception))
        self.assertFalse(self.db_path.read_bytes().find(b"private-value") >= 0)

    def test_rejects_invalid_match_snapshot_before_writing(self) -> None:
        store = OpportunityStore(self.db_path)
        invalid_report = replace(self._report("REVIEW", 72), overall_score=101)

        with self.assertRaisesRegex(
            ValueError, "overall_score must be between 0 and 100"
        ):
            store.upsert(self._vacancy(), invalid_report, UTC_TIME)

        self.assertEqual(store.list(), ())

    def test_rejects_newer_or_unrecognized_schema_without_modifying_it(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute("CREATE TABLE keep_me (value TEXT)")
            connection.execute("INSERT INTO keep_me VALUES ('unchanged')")
            connection.execute("PRAGMA user_version = 2")

        with self.assertRaisesRegex(ValueError, "schema version 2 is not supported"):
            OpportunityStore(self.db_path)

        with closing(sqlite3.connect(self.db_path)) as connection:
            value = connection.execute("SELECT value FROM keep_me").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual((value, version), ("unchanged", 2))

    def test_rejects_nonempty_version_zero_database_and_symlinks(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")

        with self.assertRaisesRegex(ValueError, "unrecognized version zero database"):
            OpportunityStore(self.db_path)

        target = Path(self.directory.name) / "target.sqlite3"
        link = Path(self.directory.name) / "link.sqlite3"
        target.touch()
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "database path must not be a symlink"):
            OpportunityStore(link)

    def test_rejects_corrupt_or_incomplete_version_one_databases(self) -> None:
        corrupt = Path(self.directory.name) / "corrupt.sqlite3"
        corrupt.write_bytes(b"not-a-sqlite-database")
        with self.assertRaisesRegex(
            ValueError, "opportunity database is invalid or cannot be read"
        ):
            OpportunityStore(corrupt)

        incomplete = Path(self.directory.name) / "incomplete.sqlite3"
        with closing(sqlite3.connect(incomplete)) as connection, connection:
            connection.execute("CREATE TABLE opportunities (vacancy_id TEXT)")
            connection.execute("PRAGMA user_version = 1")
        with self.assertRaisesRegex(
            ValueError, "opportunity schema version 1 is incomplete"
        ):
            OpportunityStore(incomplete)

    def _vacancy(self, **changes: object):
        values: dict[str, object] = {
            "source": "hh",
            "source_vacancy_id": "12345",
            "source_url": "https://hh.ru/vacancy/12345",
            "retrieved_at": UTC_TIME,
            "collection_method": "api",
            "title": "Python Backend Engineer",
            "description": "FastAPI and PostgreSQL",
        }
        values.update(changes)
        return normalize_collected_vacancy(CollectedVacancyInput(**values))

    def _report(self, recommendation: str, score: int) -> MatchReport:
        return MatchReport(
            vacancy=Vacancy(
                title="Python Backend Engineer",
                requirements=(),
                unmapped_requirement_lines=(),
                target_roles=("ai-backend-engineer",),
                domains=(),
                seniority=None,
                is_remote=True,
                minimum_years_experience=None,
                requires_production_experience=False,
                location_constraints=(),
            ),
            dimensions=(),
            requirement_mappings=(),
            required_gaps=(),
            unverified_constraints=(),
            overall_score=score,
            confidence=80,
            recommendation=recommendation,  # type: ignore[arg-type]
            reasons=("evidence-backed match",),
        )


if __name__ == "__main__":
    unittest.main()
