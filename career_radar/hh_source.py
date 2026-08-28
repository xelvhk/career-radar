"""Official HeadHunter API adapter with a fail-closed local boundary."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

import yaml

from .collected_vacancy import CollectedVacancy, CollectedVacancyInput, normalize_collected_vacancy
from .search_profiles import CompiledSearchQuery


CONFIG_SCHEMA_VERSION = 1
MAX_CONFIG_BYTES = 16_000
MAX_RESPONSE_BYTES = 2_000_000
API_ORIGIN = "https://api.hh.ru"
SAFE_MESSAGE = "HeadHunter could not complete the scan"


@dataclass(frozen=True, slots=True)
class HeadHunterConfig:
    enabled: bool
    registered_application: bool
    user_agent: str


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    records: tuple[CollectedVacancy, ...]
    skipped_count: int


class SourceBlockedError(ValueError):
    """Raised before network access when source authorization is incomplete."""


class SourceRequestError(RuntimeError):
    """A safe, bounded external-source failure."""


class VacancyUnavailableError(SourceRequestError):
    """A vacancy disappeared between search and detail retrieval."""


class JsonTransport(Protocol):
    def get_json(self, path: str, parameters: dict[str, str], user_agent: str) -> Any:
        """Fetch one JSON document from the fixed HeadHunter API origin."""


class HeadHunterTransport:
    """Small urllib transport which never exposes request or response content."""

    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def get_json(self, path: str, parameters: dict[str, str], user_agent: str) -> Any:
        if not path.startswith("/") or path.startswith("//"):
            raise SourceRequestError(SAFE_MESSAGE)
        query = urllib.parse.urlencode(parameters)
        request = urllib.request.Request(
            f"{API_ORIGIN}{path}?{query}" if query else f"{API_ORIGIN}{path}",
            headers={"HH-User-Agent": user_agent, "Accept": "application/json"},
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                final = urllib.parse.urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "api.hh.ru":
                    raise SourceRequestError("HeadHunter returned an unsafe redirect")
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400:
                raise SourceRequestError("HeadHunter returned an unsafe redirect") from error
            if error.code == 429:
                raise SourceRequestError("HeadHunter rate limit reached; try again later") from error
            if error.code in {401, 403}:
                raise SourceRequestError("HeadHunter rejected the application authorization") from error
            if error.code == 404:
                raise VacancyUnavailableError("HeadHunter vacancy is no longer available") from error
            if error.code == 400:
                raise SourceRequestError("HeadHunter rejected the search request") from error
            raise SourceRequestError(SAFE_MESSAGE) from error
        except (OSError, TimeoutError, urllib.error.URLError) as error:
            raise SourceRequestError(SAFE_MESSAGE) from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise SourceRequestError("HeadHunter response is too large")
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceRequestError("HeadHunter returned an invalid response") from error


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class HeadHunterAdapter:
    source = "hh"

    def __init__(
        self,
        config: HeadHunterConfig,
        *,
        transport: JsonTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        per_page: int = 10,
    ) -> None:
        if not config.enabled or not config.registered_application:
            raise SourceBlockedError(
                "Register and enable the HeadHunter application in local configuration"
            )
        if not 1 <= per_page <= 10:
            raise ValueError("per_page must be between 1 and 10")
        self.config = config
        self.transport = transport or HeadHunterTransport()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.per_page = per_page

    def collect(self, query: CompiledSearchQuery) -> CollectionBatch:
        search = self.transport.get_json(
            "/vacancies",
            {
                "text": _query_text(query),
                "page": "0",
                "per_page": str(self.per_page),
                "period": "7",
                "order_by": "publication_time",
            },
            self.config.user_agent,
        )
        if not isinstance(search, dict) or not isinstance(search.get("items"), list):
            raise SourceRequestError("HeadHunter returned an invalid search response")

        records: list[CollectedVacancy] = []
        skipped = 0
        seen: set[str] = set()
        for item in search["items"][: self.per_page]:
            try:
                vacancy_id = _vacancy_id(item)
            except SourceRequestError:
                skipped += 1
                continue
            if vacancy_id in seen:
                continue
            seen.add(vacancy_id)
            try:
                detail = self.transport.get_json(
                    f"/vacancies/{vacancy_id}", {}, self.config.user_agent
                )
            except VacancyUnavailableError:
                skipped += 1
                continue
            try:
                record = _normalize_detail(detail, vacancy_id, self.clock())
            except SourceRequestError:
                skipped += 1
                continue
            if record is not None:
                records.append(record)
            else:
                skipped += 1
        return CollectionBatch(tuple(records), skipped)


def load_hh_config(path: Path) -> HeadHunterConfig:
    """Read a narrow ignored config without echoing its values in errors."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise SourceBlockedError(
            "HeadHunter local configuration is missing or unreadable"
        ) from error
    if len(raw) > MAX_CONFIG_BYTES:
        raise SourceBlockedError("HeadHunter local configuration is too large")
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise SourceBlockedError("HeadHunter local configuration is invalid") from error
    errors = _validate_config(data)
    if errors:
        raise SourceBlockedError("Invalid HeadHunter local configuration: " + "; ".join(errors))
    source = data["source"]
    return HeadHunterConfig(
        enabled=source["enabled"],
        registered_application=source["registered_application"],
        user_agent=source["user_agent"],
    )


def _validate_config(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["root must be a mapping"]
    errors: list[str] = []
    if set(data) != {"schema_version", "source"}:
        errors.append("root must contain only schema_version and source")
    if data.get("schema_version") != CONFIG_SCHEMA_VERSION:
        errors.append("schema_version must equal 1")
    source = data.get("source")
    if not isinstance(source, dict):
        return errors + ["source must be a mapping"]
    if set(source) != {"enabled", "registered_application", "user_agent"}:
        errors.append("source must define exactly the supported fields")
    if type(source.get("enabled")) is not bool:
        errors.append("source.enabled must be boolean")
    if type(source.get("registered_application")) is not bool:
        errors.append("source.registered_application must be boolean")
    user_agent = source.get("user_agent")
    if not isinstance(user_agent, str) or not _valid_user_agent(user_agent):
        errors.append("source.user_agent must identify the app and contact email")
    return errors


def _valid_user_agent(value: str) -> bool:
    return (
        value == value.strip()
        and 10 <= len(value) <= 200
        and "@" in value
        and "(" in value
        and value.endswith(")")
        and all(32 <= ord(character) < 127 for character in value)
    )


def _query_text(query: CompiledSearchQuery) -> str:
    positive = [f'"{query.title_phrase}"', *query.skill_terms]
    negative = [f"NOT {term}" for term in query.exclude_terms]
    return " ".join([*positive, *negative])


def _vacancy_id(item: Any) -> str:
    value = item.get("id") if isinstance(item, dict) else None
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{1,30}", value) is None:
        raise SourceRequestError("HeadHunter returned an invalid vacancy ID")
    return value


def _normalize_detail(
    detail: Any, expected_id: str, retrieved_at: datetime
) -> CollectedVacancy | None:
    if not isinstance(detail, dict) or detail.get("id") != expected_id:
        raise SourceRequestError("HeadHunter returned an invalid vacancy response")
    if detail.get("archived") is True:
        return None
    if type(detail.get("archived")) is not bool:
        raise SourceRequestError("HeadHunter returned an invalid vacancy response")
    title = detail.get("name")
    description = detail.get("description")
    source_url = detail.get("alternate_url")
    if not all(isinstance(value, str) for value in (title, description, source_url)):
        raise SourceRequestError("HeadHunter returned an invalid vacancy response")
    try:
        record = normalize_collected_vacancy(
            CollectedVacancyInput(
                source="hh",
                source_vacancy_id=expected_id,
                source_url=source_url,
                retrieved_at=retrieved_at,
                collection_method="api",
                title=title,
                description=description,
            )
        )
    except ValueError as error:
        raise SourceRequestError("HeadHunter returned an invalid vacancy response") from error
    if urllib.parse.urlsplit(record.source_url or "").hostname != "hh.ru":
        raise SourceRequestError("HeadHunter returned an invalid vacancy URL")
    return record
