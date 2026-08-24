import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_radar.opportunity_service import OpportunityImporter
from career_radar.opportunity_store import OpportunityStore
from tests.test_repository_data import ROOT


class OpportunityImporterTests(unittest.TestCase):
    def test_import_text_runs_matcher_and_persists_without_returning_description(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            importer = OpportunityImporter(ROOT, database)

            result = importer.import_text(
                "AI Backend Engineer\nRequirements:\n- Python and FastAPI\n",
                source="manual",
                source_url="https://example.com/vacancies/42",
                retrieved_at=datetime(2026, 8, 24, 9, 0, tzinfo=timezone.utc),
                matched_at=datetime(2026, 8, 24, 9, 1, tzinfo=timezone.utc),
            )
            saved = OpportunityStore(database).get(result.opportunity.vacancy.id)

        self.assertTrue(result.created)
        self.assertEqual(saved.vacancy.title, "AI Backend Engineer")
        self.assertIn("Python and FastAPI", saved.vacancy.description)
        self.assertIn(saved.recommendation, {"APPLY", "REVIEW", "SKIP"})

    def test_import_text_rejects_empty_description_and_oversized_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            importer = OpportunityImporter(ROOT, Path(directory) / "inbox.sqlite3")
            with self.assertRaisesRegex(ValueError, "description is empty"):
                importer.import_text("Only a title")
            with self.assertRaisesRegex(ValueError, "too large"):
                importer.import_text("Role\n" + "я" * 400_001)

    def test_invalid_timestamp_is_rejected_without_echoing_input(self) -> None:
        marker = "private-timestamp-value"
        with tempfile.TemporaryDirectory() as directory:
            importer = OpportunityImporter(ROOT, Path(directory) / "inbox.sqlite3")
            with self.assertRaises(ValueError) as raised:
                importer.import_text(
                    "Role\nDescription",
                    retrieved_at=marker,
                )
        self.assertEqual(
            str(raised.exception), "retrieved_at must be an RFC 3339 timestamp"
        )
        self.assertNotIn(marker, str(raised.exception))
