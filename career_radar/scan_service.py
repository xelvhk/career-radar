"""Orchestrate a bounded source scan into the local Opportunity Inbox."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .collected_vacancy import CollectedVacancy
from .hh_source import HeadHunterAdapter, SourceRequestError
from .opportunity_service import OpportunityImporter
from .search_profiles import CompiledSearchQuery, compile_search_queries, parse_search_profiles
from .validation import load_yaml

SCAN_VERSION = 1
ScanStatus = Literal["completed", "partial", "blocked", "failed"]


@dataclass(frozen=True, slots=True)
class SourceScanResult:
    source: str
    status: ScanStatus
    fetched_count: int
    imported_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "status": self.status,
            "fetchedCount": self.fetched_count,
            "importedCount": self.imported_count,
            "createdCount": self.created_count,
            "updatedCount": self.updated_count,
            "skippedCount": self.skipped_count,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ScanReport:
    profile_id: str
    status: ScanStatus
    started_at: datetime
    finished_at: datetime
    sources: tuple[SourceScanResult, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "scanVersion": SCAN_VERSION,
            "profileId": self.profile_id,
            "status": self.status,
            "startedAt": _time(self.started_at),
            "finishedAt": _time(self.finished_at),
            "sources": [source.to_dict() for source in self.sources],
        }


@dataclass(frozen=True, slots=True)
class _CollectionSummary:
    records: tuple[CollectedVacancy, ...]
    skipped_count: int
    failure_count: int
    failure_message: str


@dataclass(frozen=True, slots=True)
class _ImportSummary:
    imported_count: int
    created_count: int
    updated_count: int
    skipped_count: int


class ScanService:
    def __init__(
        self,
        root: Path,
        importer: OpportunityImporter,
        adapter: HeadHunterAdapter | None,
        *,
        blocked_message: str | None = None,
    ) -> None:
        self.importer = importer
        self.adapter = adapter
        self.blocked_message = blocked_message or "HeadHunter source is not configured"
        skills = load_yaml(root / "skills.yaml")
        goals = load_yaml(root / "career_goals.yaml")
        matching = load_yaml(root / "matching.yaml")
        profiles = parse_search_profiles(
            load_yaml(root / "search_profiles.yaml"), skills, goals, matching
        )
        self.profiles = tuple(
            {"id": profile.id, "name": profile.name} for profile in profiles if profile.enabled
        )
        self.queries = compile_search_queries(profiles, matching)

    def scan(self, profile_id: str) -> ScanReport:
        started = datetime.now(UTC)
        selected = tuple(query for query in self.queries if query.profile_id == profile_id)
        if not selected:
            raise ValueError("search profile was not found or is disabled")
        if self.adapter is None:
            result = SourceScanResult("hh", "blocked", 0, 0, 0, 0, 0, self.blocked_message)
            return ScanReport(profile_id, "blocked", started, datetime.now(UTC), (result,))

        collection = _collect_records(self.adapter, selected)
        imported = _import_records(self.importer, collection.records)
        status, message = _scan_outcome(
            collection.failure_count,
            len(selected),
            collection.failure_message,
        )
        source = SourceScanResult(
            "hh",
            status,
            len(collection.records),
            imported.imported_count,
            imported.created_count,
            imported.updated_count,
            collection.skipped_count + imported.skipped_count,
            message,
        )
        return ScanReport(profile_id, status, started, datetime.now(UTC), (source,))


def _collect_records(
    adapter: HeadHunterAdapter,
    queries: tuple[CompiledSearchQuery, ...],
) -> _CollectionSummary:
    records: dict[str, CollectedVacancy] = {}
    skipped = failures = 0
    failure_message = ""
    for query in queries:
        try:
            batch = adapter.collect(query)
        except SourceRequestError as error:
            failures += 1
            failure_message = str(error)
            continue
        skipped += batch.skipped_count
        for record in batch.records:
            records[record.id] = record
    return _CollectionSummary(tuple(records.values()), skipped, failures, failure_message)


def _import_records(
    importer: OpportunityImporter,
    records: tuple[CollectedVacancy, ...],
) -> _ImportSummary:
    created = updated = imported = skipped = 0
    for record in records:
        upsert_result = importer.import_collected(record)
        if upsert_result.stale or upsert_result.unchanged:
            skipped += 1
            continue
        imported += 1
        if upsert_result.created:
            created += 1
        else:
            updated += 1
    return _ImportSummary(imported, created, updated, skipped)


def _scan_outcome(
    failure_count: int,
    query_count: int,
    failure_message: str,
) -> tuple[ScanStatus, str]:
    if failure_count == query_count:
        return "failed", failure_message or "HeadHunter could not complete the scan"
    if failure_count:
        return "partial", f"HeadHunter scan completed partially: {failure_message}"
    return "completed", "HeadHunter scan completed"


def _time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
