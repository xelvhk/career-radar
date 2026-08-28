import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_radar.hh_source import CollectionBatch, SourceRequestError
from career_radar.collected_vacancy import CollectedVacancyInput, normalize_collected_vacancy
from career_radar.opportunity_service import OpportunityImporter
from career_radar.opportunity_store import OpportunityStore
from career_radar.scan_service import ScanService
from tests.test_repository_data import ROOT


def vacancy(identifier: str = "101"):
    return normalize_collected_vacancy(
        CollectedVacancyInput(
            source="hh",
            source_vacancy_id=identifier,
            source_url=f"https://hh.ru/vacancy/{identifier}",
            retrieved_at=datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc),
            collection_method="api",
            title="Python Backend Engineer",
            description="Python, FastAPI and PostgreSQL",
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
        adapter = FakeAdapter([
            CollectionBatch((item,), 0),
            CollectionBatch((item,), 1),
        ])
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

    def test_one_failed_variant_is_partial_and_preserves_success(self) -> None:
        adapter = FakeAdapter([
            SourceRequestError("HeadHunter rate limit reached; try again later"),
            CollectionBatch((vacancy("202"),), 0),
        ])
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            service = ScanService(ROOT, OpportunityImporter(ROOT, database), adapter)
            report = service.scan("python-fastapi")
            saved = OpportunityStore(database).list()

        self.assertEqual(report.status, "partial")
        self.assertEqual(len(saved), 1)
        self.assertIn("rate limit", report.sources[0].message)

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
