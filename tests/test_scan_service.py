import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from career_radar.collected_vacancy import CollectedVacancyInput, normalize_collected_vacancy
from career_radar.hh_source import CollectionBatch, SourceRequestError
from career_radar.opportunity_service import OpportunityImporter
from career_radar.opportunity_store import OpportunityStore
from career_radar.scan_service import ScanService
from tests.test_repository_data import ROOT


def vacancy(
    identifier: str = "101",
    *,
    retrieved_at: datetime = datetime(2026, 8, 28, 9, 0, tzinfo=UTC),
    description: str = "Python, FastAPI and PostgreSQL",
):
    return normalize_collected_vacancy(
        CollectedVacancyInput(
            source="hh",
            source_vacancy_id=identifier,
            source_url=f"https://hh.ru/vacancy/{identifier}",
            retrieved_at=retrieved_at,
            collection_method="api",
            title="Python Backend Engineer",
            description=description,
        )
    )


class FakeAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def collect(self, _query):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ScanServiceTests(unittest.TestCase):
    def test_blocked_scan_performs_no_import_and_reports_safe_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(
                ROOT,
                OpportunityImporter(ROOT, database),
                None,
                blocked_message="Registration is required",
            )

            report = service.scan("python-fastapi")

            self.assertEqual(report.status, "blocked")
            self.assertEqual(report.sources[0].fetched_count, 0)
            self.assertEqual(OpportunityStore(database).list(), ())

    def test_scan_deduplicates_variants_and_imports_through_matcher(self) -> None:
        item = vacancy()
        adapter = FakeAdapter(
            [
                CollectionBatch((item,), 0),
                CollectionBatch((item,), 1),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)

            report = service.scan("python-fastapi")
            saved = OpportunityStore(database).list()

        self.assertEqual(report.status, "completed")
        self.assertEqual(report.sources[0].fetched_count, 1)
        self.assertEqual(report.sources[0].created_count, 1)
        self.assertEqual(report.sources[0].skipped_count, 1)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].vacancy.source, "hh")

    def test_repeat_scan_reports_unchanged_observation_as_skipped(self) -> None:
        item = vacancy()
        adapter = FakeAdapter(
            [
                CollectionBatch((item,), 0),
                CollectionBatch((), 0),
                CollectionBatch((item,), 0),
                CollectionBatch((), 0),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)

            first = service.scan("python-fastapi")
            repeated = service.scan("python-fastapi")
            saved = OpportunityStore(database).list()

        self.assertEqual(first.sources[0].created_count, 1)
        self.assertEqual(repeated.sources[0].imported_count, 0)
        self.assertEqual(repeated.sources[0].updated_count, 0)
        self.assertEqual(repeated.sources[0].skipped_count, 1)
        self.assertEqual(saved[0].seen_count, 1)

    def test_one_failed_variant_is_partial_and_preserves_success(self) -> None:
        adapter = FakeAdapter(
            [
                SourceRequestError("HeadHunter rate limit reached; try again later"),
                CollectionBatch((vacancy("202"),), 0),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)
            report = service.scan("python-fastapi")
            saved = OpportunityStore(database).list()

        self.assertEqual(report.status, "partial")
        self.assertEqual(len(saved), 1)
        self.assertIn("rate limit", report.sources[0].message)

    def test_all_failed_variants_return_failed_without_importing(self) -> None:
        adapter = FakeAdapter(
            [
                SourceRequestError("HeadHunter request one failed"),
                SourceRequestError("HeadHunter request two failed"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)

            report = service.scan("python-fastapi")

            self.assertEqual(report.status, "failed")
            self.assertIn("request two failed", report.sources[0].message)
            self.assertEqual(OpportunityStore(database).list(), ())

    def test_newer_observation_is_reported_as_updated(self) -> None:
        original = vacancy()
        updated = vacancy(
            retrieved_at=datetime(2026, 8, 29, 9, 0, tzinfo=UTC),
            description="Python, FastAPI, PostgreSQL and Docker",
        )
        adapter = FakeAdapter(
            [
                CollectionBatch((original,), 0),
                CollectionBatch((), 0),
                CollectionBatch((updated,), 0),
                CollectionBatch((), 0),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)

            service.scan("python-fastapi")
            report = service.scan("python-fastapi")

        self.assertEqual(report.sources[0].imported_count, 1)
        self.assertEqual(report.sources[0].created_count, 0)
        self.assertEqual(report.sources[0].updated_count, 1)

    def test_unknown_profile_is_rejected_without_source_call(self) -> None:
        adapter = FakeAdapter([])
        with tempfile.TemporaryDirectory() as directory:
            service = ScanService(
                ROOT,
                OpportunityImporter(ROOT, Path(directory) / "inbox.sqlite3"),
                adapter,
            )
            with self.assertRaisesRegex(ValueError, "search profile"):
                service.scan("unknown")


if __name__ == "__main__":
    unittest.main()
