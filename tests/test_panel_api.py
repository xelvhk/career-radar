import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from career_radar.panel import create_app
from tests.test_repository_data import ROOT


MUTATION_HEADERS = {
    "Origin": "http://127.0.0.1",
    "X-Career-Radar-Request": "1",
}


class PanelApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary_directory.name) / "panel.sqlite3"
        self.client = TestClient(
            create_app(db_path=self.database, root=ROOT),
            base_url="http://127.0.0.1",
        )

    def tearDown(self) -> None:
        self.client.close()
        self.temporary_directory.cleanup()

    def test_empty_inbox_and_static_panel_are_available_offline(self) -> None:
        page = self.client.get("/")
        response = self.client.get("/api/opportunities")

        self.assertEqual(page.status_code, 200)
        self.assertIn("Career Radar", page.text)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["panelVersion"], 1)
        self.assertEqual(response.json()["opportunities"], [])
        self.assertIn("default-src 'self'", page.headers["content-security-policy"])
        self.assertEqual(page.headers["cache-control"], "no-store")

    def test_import_list_detail_and_status_form_one_browser_flow(self) -> None:
        marker = "full-description-local-only-marker"
        imported = self.client.post(
            "/api/opportunities",
            headers=MUTATION_HEADERS,
            json={
                "text": (
                    "AI Backend Engineer\n"
                    f"Internal context: {marker}\n"
                    "Requirements:\n- Python, FastAPI and PostgreSQL\n"
                ),
                "source": "manual",
                "sourceUrl": "https://example.com/vacancies/42",
                "retrievedAt": "2026-08-24T09:00:00Z",
            },
        )
        vacancy_id = imported.json()["opportunity"]["id"]
        detail = self.client.get(f"/api/opportunities/{vacancy_id}")
        updated = self.client.patch(
            f"/api/opportunities/{vacancy_id}",
            headers=MUTATION_HEADERS,
            json={"status": "shortlisted"},
        )
        listed = self.client.get(
            "/api/opportunities", params={"status": "shortlisted"}
        )

        self.assertEqual(imported.status_code, 201)
        self.assertTrue(imported.json()["created"])
        self.assertNotIn(marker, imported.text)
        self.assertNotIn("description", imported.text.casefold())
        self.assertEqual(detail.status_code, 200)
        self.assertIn("matchReport", detail.json()["opportunity"])
        self.assertNotIn(marker, detail.text)
        self.assertEqual(updated.json()["opportunity"]["status"], "shortlisted")
        self.assertEqual(listed.json()["opportunityCount"], 1)

    def test_mutations_require_same_origin_marker(self) -> None:
        payload = {"text": "Python Engineer\nRequirements:\n- Python"}
        missing = self.client.post("/api/opportunities", json=payload)
        foreign = self.client.post(
            "/api/opportunities",
            headers={
                "Origin": "https://attacker.example",
                "X-Career-Radar-Request": "1",
            },
            json=payload,
        )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(foreign.status_code, 403)
        self.assertEqual(missing.json()["error"]["code"], "FORBIDDEN")

    def test_private_profile_values_never_enter_api_or_database(self) -> None:
        profile = Path(self.temporary_directory.name) / "career_profile.local.yaml"
        profile.write_text(
            "schema_version: 1\n"
            "profile:\n"
            "  commercial_years: 5\n"
            "  confirmed_production_experience: true\n"
            "  current_country_code: QZ\n"
            "  target_seniority: []\n",
            encoding="utf-8",
        )
        client = TestClient(
            create_app(
                db_path=self.database,
                root=ROOT,
                profile_path=profile,
            ),
            base_url="http://127.0.0.1",
        )
        try:
            response = client.post(
                "/api/opportunities",
                headers=MUTATION_HEADERS,
                json={
                    "text": (
                        "Senior Python Engineer\n"
                        "Remote, candidate must be outside Russia.\n"
                        "Requirements: 3+ years of production experience and Python."
                    )
                },
            )
        finally:
            client.close()
        with closing(sqlite3.connect(self.database)) as connection:
            stored_report = connection.execute(
                "SELECT report_json FROM opportunities"
            ).fetchone()[0]

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("QZ", response.text)
        self.assertNotIn("QZ", stored_report)

    def test_invalid_requests_use_safe_stable_errors(self) -> None:
        private_url = "https://example.com/vacancy?token=private-value"
        unsafe = self.client.post(
            "/api/opportunities",
            headers=MUTATION_HEADERS,
            json={
                "text": "Python Engineer\nRequirements:\n- Python",
                "sourceUrl": private_url,
            },
        )
        invalid_filter = self.client.get(
            "/api/opportunities", params={"status": "unknown"}
        )
        unknown = self.client.get("/api/opportunities/vac-" + "0" * 64)

        self.assertEqual(unsafe.status_code, 400)
        self.assertNotIn("private-value", unsafe.text)
        self.assertEqual(invalid_filter.status_code, 422)
        self.assertEqual(unknown.status_code, 404)
        for response in (unsafe, invalid_filter, unknown):
            self.assertEqual(set(response.json()), {"error"})

    def test_non_loopback_host_is_rejected(self) -> None:
        response = self.client.get(
            "/api/opportunities", headers={"Host": "career-radar.example"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_HOST")
