import re
import unittest
from datetime import datetime, timedelta, timezone

from career_radar import (
    CollectedVacancy,
    CollectedVacancyInput,
    collected_vacancy_to_dict,
    normalize_collected_vacancy,
)


UTC_TIME = datetime(2026, 8, 22, 9, 30, tzinfo=timezone.utc)


class CollectedVacancyTests(unittest.TestCase):
    def test_normalizes_a_source_id_record_with_immutable_provenance(self) -> None:
        record = normalize_collected_vacancy(
            CollectedVacancyInput(
                source="hh",
                source_vacancy_id=" 12345 ",
                source_url="https://hh.ru/vacancy/12345#description",
                retrieved_at=datetime(
                    2026, 8, 22, 12, 30, tzinfo=timezone(timedelta(hours=3))
                ),
                collection_method="api",
                title="  Python Backend Engineer  ",
                description="  FastAPI and PostgreSQL\n  ",
            )
        )

        self.assertIsInstance(record, CollectedVacancy)
        self.assertEqual(
            record.id,
            "vac-83be295090a10a7a26abbcfee32c8dacb8a08dd652454561a87b797df4ee0a34",
        )
        self.assertEqual(record.source, "hh")
        self.assertEqual(record.source_vacancy_id, "12345")
        self.assertEqual(record.source_url, "https://hh.ru/vacancy/12345")
        self.assertEqual(record.retrieved_at, UTC_TIME)
        self.assertEqual(record.collection_method, "api")
        self.assertEqual(record.title, "Python Backend Engineer")
        self.assertEqual(record.description, "FastAPI and PostgreSQL")

    def test_native_source_id_stays_stable_across_observations(self) -> None:
        first = self._normalize(
            source_vacancy_id="12345",
            source_url="https://hh.ru/vacancy/12345?from=search",
            collection_method="api",
        )
        second = self._normalize(
            source_vacancy_id="12345",
            source_url="https://hh.ru/vacancy/12345?from=favorites",
            collection_method="browser",
            retrieved_at=UTC_TIME + timedelta(days=1),
        )

        self.assertEqual(first.id, second.id)

    def test_canonical_url_is_a_stable_fallback_identity(self) -> None:
        first = self._normalize(
            source_vacancy_id=None,
            source_url="https://HH.RU:443/vacancy/12345?from=search#details",
            collection_method="manual_url",
        )
        second = self._normalize(
            source_vacancy_id=None,
            source_url="https://hh.ru/vacancy/12345?from=search",
            collection_method="browser",
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            first.source_url, "https://hh.ru/vacancy/12345?from=search"
        )

    def test_manual_text_identity_normalizes_case_and_whitespace(self) -> None:
        first = self._normalize(
            source="manual",
            source_vacancy_id=None,
            source_url=None,
            collection_method="manual_text",
            title="Python Engineer",
            description="FastAPI\nPostgreSQL",
        )
        second = self._normalize(
            source="manual",
            source_vacancy_id=None,
            source_url=None,
            collection_method="manual_text",
            title="  PYTHON   ENGINEER ",
            description=" fastapi   postgresql ",
        )

        self.assertEqual(first.id, second.id)

    def test_serializes_one_stable_record_shape(self) -> None:
        record = self._normalize()

        self.assertEqual(
            collected_vacancy_to_dict(record),
            {
                "recordVersion": 1,
                "id": record.id,
                "source": {
                    "name": "hh",
                    "vacancyId": "12345",
                    "url": "https://hh.ru/vacancy/12345",
                },
                "retrievedAt": "2026-08-22T09:30:00Z",
                "collectionMethod": "api",
                "title": "Python Backend Engineer",
                "description": "FastAPI and PostgreSQL",
            },
        )

    def test_matcher_text_excludes_provenance_metadata(self) -> None:
        record = self._normalize()

        self.assertEqual(
            record.matcher_text,
            "Python Backend Engineer\nFastAPI and PostgreSQL",
        )
        self.assertNotIn("hh.ru", record.matcher_text)
        self.assertNotIn("12345", record.matcher_text)

    def test_rejects_invalid_provenance_and_content(self) -> None:
        invalid_cases = (
            ({"source": "Head Hunter"}, "source must be a lowercase kebab-case identifier"),
            ({"collection_method": "scraper"}, "collection_method must be one of"),
            ({"retrieved_at": datetime(2026, 8, 22, 9, 30)}, "retrieved_at must be timezone-aware"),
            ({"source_url": "http://hh.ru/vacancy/12345"}, "source_url must use HTTPS"),
            ({"source_url": "https://user:secret@hh.ru/vacancy/12345"}, "source_url must not contain credentials"),
            ({"title": "   "}, "title must be non-empty"),
            ({"description": "x" * 200_001}, "description exceeds the 200000 character limit"),
        )
        for changes, message in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, re.escape(message)):
                    self._normalize(**changes)

    def test_non_manual_collection_requires_a_source_locator(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "source_vacancy_id or source_url is required for api collection",
        ):
            self._normalize(
                source_vacancy_id=None,
                source_url=None,
                collection_method="api",
            )

    def _normalize(self, **changes: object):
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


if __name__ == "__main__":
    unittest.main()
