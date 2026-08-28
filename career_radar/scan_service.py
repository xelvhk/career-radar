"""Orchestrate a bounded source scan into the local Opportunity Inbox."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .hh_source import HeadHunterAdapter, SourceRequestError
from .opportunity_service import OpportunityImporter
from .search_profiles import compile_search_queries, parse_search_profiles
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
        values = asdict(self)
        return {"source": values.pop("source"), "status": values.pop("status"), **{
            "fetchedCount": values["fetched_count"],
            "importedCount": values["imported_count"],
            "createdCount": values["created_count"],
            "updatedCount": values["updated_count"],
            "skippedCount": values["skipped_count"],
            "message": values["message"],
        }}


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
            {"id": profile.id, "name": profile.name}
            for profile in profiles
            if profile.enabled
        )
        self.queries = compile_search_queries(profiles, matching)

    def scan(self, profile_id: str) -> ScanReport:
        started = datetime.now(timezone.utc)
        selected = tuple(query for query in self.queries if query.profile_id == profile_id)
        if not selected:
            raise ValueError("search profile was not found or is disabled")
        if self.adapter is None:
            result = SourceScanResult(
                "hh", "blocked", 0, 0, 0, 0, 0, self.blocked_message
            )
            return ScanReport(profile_id, "blocked", started, datetime.now(timezone.utc), (result,))

        records = {}
        skipped = 0
        failures = 0
        failure_message = ""
        for query in selected:
            try:
                batch = self.adapter.collect(query)
            except SourceRequestError as error:
                failures += 1
                failure_message = str(error)
                continue
            skipped += batch.skipped_count
            for record in batch.records:
                records[record.id] = record

        created = updated = imported = 0
        for record in records.values():
            result = self.importer.import_collected(record)
            if result.stale:
                skipped += 1
                continue
            imported += 1
            if result.created:
                created += 1
            else:
                updated += 1

        if failures == len(selected):
            status: ScanStatus = "failed"
            message = failure_message or "HeadHunter could not complete the scan"
        elif failures:
            status = "partial"
            message = "HeadHunter scan completed with a variant failure"
        else:
            status = "completed"
            message = "HeadHunter scan completed"
        source = SourceScanResult(
            "hh", status, len(records), imported, created, updated, skipped, message
        )
        return ScanReport(profile_id, status, started, datetime.now(timezone.utc), (source,))


def _time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
