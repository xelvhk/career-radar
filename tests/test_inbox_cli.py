import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from tests.test_repository_data import ROOT


class InboxCliTests(unittest.TestCase):
    def test_import_list_show_and_status_form_one_persistent_flow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            database = temp / "inbox.sqlite3"
            vacancy = temp / "vacancy.txt"
            private_marker = "local-only-full-description-marker"
            vacancy.write_text(
                "AI Backend Engineer\n"
                f"Company context: {private_marker}\n"
                "Requirements:\n"
                "- Python, FastAPI and PostgreSQL\n",
                encoding="utf-8",
            )
            arguments = [
                "import",
                str(vacancy),
                "--db",
                str(database),
                "--source",
                "manual",
                "--source-url",
                "https://example.com/vacancies/123",
                "--retrieved-at",
                "2026-08-22T09:30:00Z",
                "--format",
                "json",
            ]

            imported = self._run(*arguments)
            repeated = self._run(*arguments)
            imported_payload = json.loads(imported.stdout)
            vacancy_id = imported_payload["opportunity"]["id"]
            recommendation = imported_payload["opportunity"]["recommendation"]

            updated = self._run(
                "set-status",
                vacancy_id,
                "shortlisted",
                "--db",
                str(database),
                "--format",
                "json",
            )
            listed = self._run(
                "list",
                "--db",
                str(database),
                "--recommendation",
                recommendation,
                "--status",
                "shortlisted",
                "--format",
                "json",
            )
            shown = self._run(
                "show",
                vacancy_id,
                "--db",
                str(database),
                "--format",
                "json",
            )
            with closing(sqlite3.connect(database)) as connection:
                stored_description = connection.execute(
                    "SELECT description FROM opportunities"
                ).fetchone()[0]

        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertTrue(imported_payload["created"])
        self.assertFalse(json.loads(repeated.stdout)["created"])
        self.assertNotIn(private_marker, imported.stdout)
        self.assertNotIn("description", imported_payload["opportunity"])
        self.assertTrue(stored_description.startswith("Company context:"))
        self.assertIn(private_marker, stored_description)

        updated_payload = json.loads(updated.stdout)
        listed_payload = json.loads(listed.stdout)
        shown_payload = json.loads(shown.stdout)
        self.assertEqual(updated_payload["opportunity"]["status"], "shortlisted")
        self.assertEqual(updated_payload["opportunity"]["recommendation"], recommendation)
        self.assertEqual(listed_payload["opportunityCount"], 1)
        self.assertEqual(listed_payload["opportunities"][0]["seenCount"], 2)
        self.assertEqual(shown_payload["opportunity"]["seenCount"], 2)
        self.assertIn("matchReport", shown_payload["opportunity"])
        self.assertNotIn(private_marker, shown.stdout)

    def test_private_profile_values_are_never_persisted_or_printed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            database = temp / "inbox.sqlite3"
            vacancy = temp / "vacancy.txt"
            vacancy.write_text(
                "AI Backend Engineer\n"
                "Remote; candidate must be outside Russia.\n"
                "Requirements:\n"
                "- Python and FastAPI\n"
                "- 3+ years of production experience\n",
                encoding="utf-8",
            )
            profile = temp / "career_profile.local.yaml"
            profile.write_text(
                "schema_version: 1\n"
                "profile:\n"
                "  commercial_years: 5\n"
                "  confirmed_production_experience: true\n"
                "  current_country_code: QZ\n"
                "  target_seniority: []\n",
                encoding="utf-8",
            )

            result = self._run(
                "import",
                str(vacancy),
                "--db",
                str(database),
                "--profile",
                str(profile),
                "--format",
                "json",
            )
            database_bytes = database.read_bytes()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("QZ", result.stdout)
        self.assertNotIn(b"QZ", database_bytes)

    def test_rejects_unsafe_files_and_urls_without_echoing_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            database = temp / "inbox.sqlite3"
            invalid = temp / "invalid.txt"
            invalid.write_bytes(b"private-file-value-\xff")
            invalid_result = self._run(
                "import",
                str(invalid),
                "--db",
                str(database),
            )

            vacancy = temp / "vacancy.txt"
            vacancy.write_text("Python Engineer\nRequirements:\n- Python\n", encoding="utf-8")
            unsafe_result = self._run(
                "import",
                str(vacancy),
                "--db",
                str(database),
                "--source-url",
                "https://example.com/vacancy/1?token=private-url-value",
            )

        self.assertEqual(invalid_result.returncode, 2)
        self.assertIn("must be UTF-8", invalid_result.stderr)
        self.assertNotIn("private-file-value", invalid_result.stderr)
        self.assertEqual(unsafe_result.returncode, 2)
        self.assertIn("sensitive query parameter", unsafe_result.stderr)
        self.assertNotIn("private-url-value", unsafe_result.stderr)

    def test_markdown_show_escapes_untrusted_stored_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            database = temp / "inbox.sqlite3"
            vacancy = temp / "vacancy.txt"
            vacancy.write_text(
                "AI [click](https://example.test) | Engineer\n"
                "Requirements:\n- Python\n",
                encoding="utf-8",
            )
            imported = self._run(
                "import",
                str(vacancy),
                "--db",
                str(database),
                "--format",
                "json",
            )
            vacancy_id = json.loads(imported.stdout)["opportunity"]["id"]

            shown = self._run("show", vacancy_id, "--db", str(database))

        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn(r"AI \[click\]\(https://example.test\) \| Engineer", shown.stdout)
        self.assertNotIn("[click](https://example.test) | Engineer", shown.stdout)

    def test_incompatible_database_returns_a_stable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "inbox.sqlite3"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("PRAGMA user_version = 99")

            result = self._run("list", "--db", str(database))

        self.assertEqual(result.returncode, 2)
        self.assertIn("schema version 99 is not supported", result.stderr)
        self.assertNotIn(str(database), result.stderr)

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/inbox.py", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
