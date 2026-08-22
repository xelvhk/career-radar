"""Validated boundary for untrusted vacancy collector output."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, cast
from urllib.parse import SplitResult, urlsplit, urlunsplit


CollectionMethod = Literal["api", "browser", "manual_url", "manual_text"]

RECORD_VERSION = 1
IDENTITY_VERSION = "collected-vacancy:v1"
COLLECTION_METHODS = {"api", "browser", "manual_url", "manual_text"}
SOURCE_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class CollectedVacancyInput:
    source: str
    source_vacancy_id: str | None
    source_url: str | None
    retrieved_at: datetime
    collection_method: str
    title: str
    description: str


@dataclass(frozen=True, slots=True)
class CollectedVacancy:
    id: str
    source: str
    source_vacancy_id: str | None
    source_url: str | None
    retrieved_at: datetime
    collection_method: CollectionMethod
    title: str
    description: str

    @property
    def matcher_text(self) -> str:
        """Return only vacancy content, excluding collector metadata."""
        return f"{self.title}\n{self.description}"


def normalize_collected_vacancy(
    raw: CollectedVacancyInput,
) -> CollectedVacancy:
    """Validate and normalize one untrusted observation from a collector."""
    source = _normalize_source(raw.source)
    source_vacancy_id = _optional_bounded_text(
        raw.source_vacancy_id, field="source_vacancy_id", maximum=300
    )
    source_url = _canonical_https_url(raw.source_url)
    retrieved_at = _utc_timestamp(raw.retrieved_at)
    collection_method = _collection_method(raw.collection_method)
    title = _required_text(raw.title, field="title", maximum=300)
    description = _required_text(
        raw.description, field="description", maximum=200_000
    )

    if (
        source_vacancy_id is None
        and source_url is None
        and collection_method != "manual_text"
    ):
        raise ValueError(
            "source_vacancy_id or source_url is required for "
            f"{collection_method} collection"
        )

    return CollectedVacancy(
        id=_vacancy_id(
            source=source,
            source_vacancy_id=source_vacancy_id,
            source_url=source_url,
            title=title,
            description=description,
        ),
        source=source,
        source_vacancy_id=source_vacancy_id,
        source_url=source_url,
        retrieved_at=retrieved_at,
        collection_method=collection_method,
        title=title,
        description=description,
    )


def collected_vacancy_to_dict(record: CollectedVacancy) -> dict[str, object]:
    """Serialize a record to the stable version-one persistence shape."""
    return {
        "recordVersion": RECORD_VERSION,
        "id": record.id,
        "source": {
            "name": record.source,
            "vacancyId": record.source_vacancy_id,
            "url": record.source_url,
        },
        "retrievedAt": record.retrieved_at.isoformat().replace("+00:00", "Z"),
        "collectionMethod": record.collection_method,
        "title": record.title,
        "description": record.description,
    }


def _normalize_source(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 50
        or SOURCE_PATTERN.fullmatch(value) is None
    ):
        raise ValueError("source must be a lowercase kebab-case identifier")
    return value


def _collection_method(value: object) -> CollectionMethod:
    if not isinstance(value, str) or value not in COLLECTION_METHODS:
        raise ValueError(
            "collection_method must be one of api, browser, manual_url, manual_text"
        )
    return cast(CollectionMethod, value)


def _required_text(value: object, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds the {maximum} character limit")
    return normalized


def _optional_bounded_text(
    value: object, *, field: str, maximum: int
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text when provided")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds the {maximum} character limit")
    return normalized


def _utc_timestamp(value: object) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("retrieved_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical_https_url(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source_url must be non-empty text when provided")
    candidate = value.strip()
    if len(candidate) > 2_048:
        raise ValueError("source_url exceeds the 2048 character limit")
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as error:
        raise ValueError("source_url must be a valid HTTPS URL") from error
    if parsed.scheme.lower() != "https":
        raise ValueError("source_url must use HTTPS")
    if not parsed.hostname:
        raise ValueError("source_url must be a valid HTTPS URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("source_url must not contain credentials")

    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname if port in (None, 443) else f"{hostname}:{port}"
    canonical = SplitResult("https", netloc, parsed.path, parsed.query, "")
    return urlunsplit(canonical)


def _vacancy_id(
    *,
    source: str,
    source_vacancy_id: str | None,
    source_url: str | None,
    title: str,
    description: str,
) -> str:
    if source_vacancy_id is not None:
        identity = (IDENTITY_VERSION, "source-id", source, source_vacancy_id)
    elif source_url is not None:
        identity = (IDENTITY_VERSION, "source-url", source, source_url)
    else:
        identity = (
            IDENTITY_VERSION,
            "manual-content",
            source,
            _identity_text(title),
            _identity_text(description),
        )
    encoded = json.dumps(
        identity, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return "vac-" + hashlib.sha256(encoded).hexdigest()


def _identity_text(value: str) -> str:
    return " ".join(value.casefold().split())
