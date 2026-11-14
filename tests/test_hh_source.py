import json
import tempfile
import unittest
import urllib.error
from datetime import UTC, datetime
from email.message import Message
from pathlib import Path

from career_radar.hh_source import (
    MAX_RESPONSE_BYTES,
    HeadHunterAdapter,
    HeadHunterConfig,
    HeadHunterTransport,
    SourceBlockedError,
    SourceRequestError,
    VacancyUnavailableError,
    _NoRedirectHandler,
    load_hh_config,
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
FIXTURES = Path(__file__).parent / "fixtures" / "hh"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


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


class ErrorOpener:
    def __init__(self, status, headers=None):
        self.status = status
        self.headers = headers or Message()

    def open(self, request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, self.status, "external marker", self.headers, None
        )


class ResponseOpener:
    def __init__(self, body, url="https://api.hh.ru/vacancies"):
        self.body = body
        self.url = url

    def open(self, request, timeout):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.body


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
                fixture("search.json"),
                fixture("vacancy-101.json"),
                {
                    "id": "102",
                    "name": "Old role",
                    "archived": True,
                    "alternate_url": "https://hh.ru/vacancy/102",
                    "description": "old",
                },
            ]
        )
        adapter = HeadHunterAdapter(
            HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)"),
            transport=transport,
            clock=lambda: datetime(2026, 8, 28, tzinfo=UTC),
        )

        batch = adapter.collect(QUERY)

        self.assertEqual([item.source_vacancy_id for item in batch.records], ["101"])
        self.assertEqual(batch.skipped_count, 2)
        self.assertEqual(batch.records[0].collection_method, "api")
        self.assertEqual(transport.calls[0][1]["per_page"], "10")
        self.assertIn('"Python Backend Developer"', transport.calls[0][1]["text"])
        self.assertNotIn("contact@example.com", str(transport.calls[0][1]))

    def test_vacancy_that_disappears_after_search_is_skipped(self) -> None:
        adapter = HeadHunterAdapter(
            HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)"),
            transport=FakeTransport(
                [
                    {"items": [{"id": "101"}]},
                    VacancyUnavailableError("HeadHunter vacancy is no longer available"),
                ]
            ),
        )

        batch = adapter.collect(QUERY)

        self.assertEqual(batch.records, ())
        self.assertEqual(batch.skipped_count, 1)

    def test_invalid_search_and_detail_fail_with_safe_messages(self) -> None:
        config = HeadHunterConfig(True, True, "CareerRadar/0.1 (contact@example.com)")
        with self.assertRaisesRegex(SourceRequestError, "invalid search"):
            HeadHunterAdapter(config, transport=FakeTransport([{"items": None}])).collect(QUERY)

        adapter = HeadHunterAdapter(
            config,
            transport=FakeTransport(
                [
                    {"items": [{"id": "101"}]},
                    {
                        "id": "101",
                        "name": "Role",
                        "archived": False,
                        "alternate_url": "https://evil.example/101",
                        "description": "private-marker",
                    },
                ]
            ),
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

    def test_transport_maps_rate_limit_and_bounded_retry_after(self) -> None:
        headers = Message()
        headers["Retry-After"] = "120"
        transport = HeadHunterTransport()
        transport._opener = ErrorOpener(429, headers)

        with self.assertRaisesRegex(SourceRequestError, "120 seconds") as raised:
            transport.get_json("/vacancies", {}, "CareerRadar/0.1 (contact@example.com)")

        self.assertNotIn("external marker", str(raised.exception))
        raised.exception.__cause__.close()

    def test_transport_maps_http_statuses_to_stable_domain_errors(self) -> None:
        cases = (
            (302, SourceRequestError, "unsafe redirect"),
            (400, SourceRequestError, "rejected the search request"),
            (401, SourceRequestError, "rejected the application authorization"),
            (403, SourceRequestError, "rejected the application authorization"),
            (404, VacancyUnavailableError, "no longer available"),
            (500, SourceRequestError, "could not complete"),
        )
        for status, error_type, message in cases:
            with self.subTest(status=status):
                transport = HeadHunterTransport()
                transport._opener = ErrorOpener(status)
                with self.assertRaisesRegex(error_type, message) as raised:
                    transport.get_json("/vacancies", {}, "CareerRadar/0.1")
                raised.exception.__cause__.close()

    def test_transport_validates_path_origin_size_and_json(self) -> None:
        transport = HeadHunterTransport()
        with self.assertRaisesRegex(SourceRequestError, "could not complete"):
            transport.get_json("//evil.example", {}, "CareerRadar/0.1")

        transport._opener = ResponseOpener(b'{"ok": true}')
        self.assertEqual(transport.get_json("/vacancies", {}, "CareerRadar/0.1"), {"ok": True})

        transport._opener = ResponseOpener(b"{}", "https://evil.example/vacancies")
        with self.assertRaisesRegex(SourceRequestError, "unsafe redirect"):
            transport.get_json("/vacancies", {}, "CareerRadar/0.1")

        transport._opener = ResponseOpener(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(SourceRequestError, "too large"):
            transport.get_json("/vacancies", {}, "CareerRadar/0.1")

        transport._opener = ResponseOpener(b"not-json")
        with self.assertRaisesRegex(SourceRequestError, "invalid response"):
            transport.get_json("/vacancies", {}, "CareerRadar/0.1")


if __name__ == "__main__":
    unittest.main()
