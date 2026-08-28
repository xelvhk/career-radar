import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from career_radar.hh_source import (
    HeadHunterAdapter,
    HeadHunterConfig,
    SourceBlockedError,
    SourceRequestError,
    load_hh_config,
    _NoRedirectHandler,
)
from career_radar.search_profiles import CompiledSearchQuery


QUERY = CompiledSearchQuery(
    profile_id="python-fastapi",
    profile_name="Python / FastAPI",
    target_role_id="ai-backend-engineer",
    title_phrase="Python Backend Developer",
    skill_ids=("python", "fastapi"),
    skill_terms=("python", "fastapi"),
    exclude_terms=("php", "bitrix"),
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, path, parameters, user_agent):
        self.calls.append((path, parameters, user_agent))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class HeadHunterSourceTests(unittest.TestCase):
    def test_transport_disables_redirect_following(self) -> None:
        handler = _NoRedirectHandler()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example")
        )

    def test_config_is_strict_and_registration_is_required_before_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hh.yaml"
            path.write_text(
                "schema_version: 1\nsource:\n  enabled: true\n"
                "  registered_application: false\n"
                "  user_agent: CareerRadar/0.1 (contact@example.com)\n",
                encoding="utf-8",
            )
            config = load_hh_config(path)
        with self.assertRaisesRegex(SourceBlockedError, "Register and enable"):
            HeadHunterAdapter(config, transport=FakeTransport([]))

    def test_collects_valid_detail_and_skips_archived_or_malformed_items(self) -> None:
        transport = FakeTransport(
            [
                {"items": [{"id": "101"}, {"id": "bad"}, {"id": "102"}]},
                {
                    "id": "101", "name": "Python Engineer", "archived": False,
                    "alternate_url": "https://hh.ru/vacancy/101",
                    "description": "Python, FastAPI and PostgreSQL",
                },
                {
                    "id": "102", "name": "Old role", "archived": True,
                    "alternate_url": "https://hh.ru/vacancy/102", "description": "old",
                },
            ]
        )
        adapter = HeadHunterAdapter(
            HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)"),
            transport=transport,
            clock=lambda: datetime(2026, 8, 28, tzinfo=timezone.utc),
        )

        batch = adapter.collect(QUERY)

        self.assertEqual([item.source_vacancy_id for item in batch.records], ["101"])
        self.assertEqual(batch.skipped_count, 2)
        self.assertEqual(batch.records[0].collection_method, "api")
        self.assertEqual(transport.calls[0][1]["per_page"], "10")
        self.assertIn('"Python Backend Developer"', transport.calls[0][1]["text"])
        self.assertNotIn("contact@example.com", str(transport.calls[0][1]))

    def test_invalid_search_and_detail_fail_with_safe_messages(self) -> None:
        config = HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)")
        with self.assertRaisesRegex(SourceRequestError, "invalid search"):
            HeadHunterAdapter(config, transport=FakeTransport([{"items": None}])).collect(QUERY)

        adapter = HeadHunterAdapter(
            config,
            transport=FakeTransport([
                {"items": [{"id": "101"}]},
                {"id": "101", "name": "Role", "archived": False,
                 "alternate_url": "https://evil.example/101", "description": "private-marker"},
            ]),
        )
        batch = adapter.collect(QUERY)
        self.assertEqual(batch.records, ())
        self.assertEqual(batch.skipped_count, 1)

    def test_transport_failure_does_not_echo_private_response(self) -> None:
        marker = "private-response-marker"
        adapter = HeadHunterAdapter(
            HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)"),
            transport=FakeTransport([SourceRequestError("HeadHunter could not complete the scan")]),
        )
        with self.assertRaises(SourceRequestError) as raised:
            adapter.collect(QUERY)
        self.assertNotIn(marker, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
