"""Transactional local SQLite storage for matched opportunities."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import parse_qsl, urlsplit

from .collected_vacancy import CollectedVacancy, CollectionMethod
from .matching import MatchReport
from .reporting import report_to_dict


InboxStatus = Literal["new", "shortlisted", "dismissed"]
Recommendation = Literal["APPLY", "REVIEW", "SKIP"]

SCHEMA_VERSION = 1
STATUSES = {"new", "shortlisted", "dismissed"}
RECOMMENDATIONS = {"APPLY", "REVIEW", "SKIP"}
VACANCY_ID_PATTERN = re.compile(r"vac-[0-9a-f]{64}")
SENSITIVE_QUERY_KEYS = {
    "auth",
    "authorization",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "key",
    "session",
    "session_id",
    "sessionid",
}
DATABASE_ERROR = "opportunity database is invalid or cannot be read"

EXPECTED_COLUMNS = {
    "vacancy_id",
    "record_version",
    "source",
    "source_vacancy_id",
    "source_url",
    "collection_method",
    "title",
    "description",
    "first_seen_at",
    "last_seen_at",
    "seen_count",
    "recommendation",
    "overall_score",
    "confidence",
    "report_json",
    "matched_at",
    "status",
}

CREATE_SCHEMA = """
CREATE TABLE opportunities (
    vacancy_id TEXT PRIMARY KEY,
    record_version INTEGER NOT NULL CHECK (record_version = 1),
    source TEXT NOT NULL,
    source_vacancy_id TEXT,
    source_url TEXT,
    collection_method TEXT NOT NULL
        CHECK (collection_method IN ('api', 'browser', 'manual_url', 'manual_text')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    seen_count INTEGER NOT NULL CHECK (seen_count >= 1),
    recommendation TEXT NOT NULL
        CHECK (recommendation IN ('APPLY', 'REVIEW', 'SKIP')),
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 0 AND 100),
    confidence INTEGER NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    report_json TEXT NOT NULL,
    matched_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'shortlisted', 'dismissed'))
);
PRAGMA user_version = 1;
"""


@dataclass(frozen=True, slots=True)
class Opportunity:
    vacancy: CollectedVacancy
    first_seen_at: datetime
    last_seen_at: datetime
    seen_count: int
    recommendation: Recommendation
    overall_score: int
    confidence: int
    match_report: dict[str, Any]
    matched_at: datetime
    status: InboxStatus


@dataclass(frozen=True, slots=True)
class UpsertResult:
    opportunity: Opportunity
    created: bool
    stale: bool


class OpportunityStore:
    """Persist current opportunity state without leaking storage concerns."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._validate_path()
        existed = self.path.exists()
        if not existed:
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                    0o600,
                )
                os.close(descriptor)
            except FileExistsError:
                self._validate_path()
                existed = True
            except OSError as error:
                raise ValueError("cannot create opportunity database") from error
        try:
            with closing(self._connect()) as connection:
                self._prepare_schema(connection)
        except sqlite3.DatabaseError as error:
            raise ValueError(DATABASE_ERROR) from error
        if not existed and os.name == "posix":
            try:
                self.path.chmod(0o600)
            except OSError as error:
                raise ValueError("cannot restrict opportunity database permissions") from error

    def upsert(
        self,
        vacancy: CollectedVacancy,
        report: MatchReport,
        matched_at: datetime,
    ) -> UpsertResult:
        _validate_persistable_url(vacancy.source_url)
        _validate_report(report)
        matched_at = _as_utc(matched_at, "matched_at")
        report_payload = report_to_dict(report)
        report_json = json.dumps(
            report_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        retrieved_at = _format_time(vacancy.retrieved_at)
        values = (
            vacancy.source,
            vacancy.source_vacancy_id,
            vacancy.source_url,
            vacancy.collection_method,
            vacancy.title,
            vacancy.description,
            retrieved_at,
            report.recommendation,
            report.overall_score,
            report.confidence,
            report_json,
            _format_time(matched_at),
        )
        try:
            with closing(self._connect()) as connection, connection:
                row = connection.execute(
                    "SELECT * FROM opportunities WHERE vacancy_id = ?",
                    (vacancy.id,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        """
                        INSERT INTO opportunities (
                            vacancy_id, record_version, source, source_vacancy_id,
                            source_url, collection_method, title, description,
                            first_seen_at, last_seen_at, seen_count, recommendation,
                            overall_score, confidence, report_json, matched_at, status
                        ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, 'new')
                        """,
                        (vacancy.id, *values[:6], retrieved_at, *values[6:]),
                    )
                    saved = self._select_one(connection, vacancy.id)
                    return UpsertResult(saved, created=True, stale=False)

                current = _row_to_opportunity(row)
                if vacancy.retrieved_at < current.last_seen_at:
                    return UpsertResult(current, created=False, stale=True)

                connection.execute(
                    """
                    UPDATE opportunities SET
                        source = ?, source_vacancy_id = ?, source_url = ?,
                        collection_method = ?, title = ?, description = ?,
                        last_seen_at = ?, seen_count = seen_count + 1,
                        recommendation = ?, overall_score = ?, confidence = ?,
                        report_json = ?, matched_at = ?
                    WHERE vacancy_id = ?
                    """,
                    (*values, vacancy.id),
                )
                saved = self._select_one(connection, vacancy.id)
                return UpsertResult(saved, created=False, stale=False)
        except sqlite3.DatabaseError as error:
            raise ValueError(DATABASE_ERROR) from error

    def get(self, vacancy_id: str) -> Opportunity:
        _validate_vacancy_id(vacancy_id)
        try:
            with closing(self._connect()) as connection:
                return self._select_one(connection, vacancy_id)
        except sqlite3.DatabaseError as error:
            raise ValueError(DATABASE_ERROR) from error

    def list(
        self,
        *,
        recommendation: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> tuple[Opportunity, ...]:
        if recommendation is not None and recommendation not in RECOMMENDATIONS:
            raise ValueError("recommendation must be one of APPLY, REVIEW, SKIP")
        if status is not None and status not in STATUSES:
            raise ValueError("status must be one of new, shortlisted, dismissed")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        clauses: list[str] = []
        parameters: list[object] = []
        if recommendation is not None:
            clauses.append("recommendation = ?")
            parameters.append(recommendation)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        query = f"""
            SELECT * FROM opportunities
            {where}
            ORDER BY
                CASE recommendation WHEN 'APPLY' THEN 0 WHEN 'REVIEW' THEN 1 ELSE 2 END,
                overall_score DESC,
                last_seen_at DESC,
                vacancy_id ASC
            LIMIT ?
        """
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(query, parameters).fetchall()
                return tuple(_row_to_opportunity(row) for row in rows)
        except sqlite3.DatabaseError as error:
            raise ValueError(DATABASE_ERROR) from error

    def set_status(self, vacancy_id: str, status: str) -> Opportunity:
        if status not in STATUSES:
            raise ValueError("status must be one of new, shortlisted, dismissed")
        _validate_vacancy_id(vacancy_id)
        try:
            with closing(self._connect()) as connection, connection:
                cursor = connection.execute(
                    "UPDATE opportunities SET status = ? WHERE vacancy_id = ?",
                    (status, vacancy_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("opportunity was not found")
                return self._select_one(connection, vacancy_id)
        except sqlite3.DatabaseError as error:
            raise ValueError(DATABASE_ERROR) from error

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _prepare_schema(self, connection: sqlite3.Connection) -> None:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError(f"opportunity schema version {version} is not supported")
        if version == 0:
            tables = connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
            if tables:
                raise ValueError("unrecognized version zero database")
            with connection:
                connection.executescript(CREATE_SCHEMA)
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(DATABASE_ERROR)
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(opportunities)")
        }
        if not EXPECTED_COLUMNS.issubset(columns):
            raise ValueError("opportunity schema version 1 is incomplete")

    def _select_one(
        self, connection: sqlite3.Connection, vacancy_id: str
    ) -> Opportunity:
        row = connection.execute(
            "SELECT * FROM opportunities WHERE vacancy_id = ?", (vacancy_id,)
        ).fetchone()
        if row is None:
            raise ValueError("opportunity was not found")
        return _row_to_opportunity(row)

    def _validate_path(self) -> None:
        if self.path.is_symlink():
            raise ValueError("database path must not be a symlink")
        if self.path.exists() and not self.path.is_file():
            raise ValueError("database path must be a regular file")
        if not self.path.parent.is_dir():
            raise ValueError("database parent directory must exist")


def _row_to_opportunity(row: sqlite3.Row) -> Opportunity:
    try:
        match_report = json.loads(row["report_json"])
        if not isinstance(match_report, dict):
            raise ValueError(DATABASE_ERROR)
        vacancy = CollectedVacancy(
            id=row["vacancy_id"],
            source=row["source"],
            source_vacancy_id=row["source_vacancy_id"],
            source_url=row["source_url"],
            retrieved_at=_parse_time(row["last_seen_at"]),
            collection_method=cast(CollectionMethod, row["collection_method"]),
            title=row["title"],
            description=row["description"],
        )
        return Opportunity(
            vacancy=vacancy,
            first_seen_at=_parse_time(row["first_seen_at"]),
            last_seen_at=_parse_time(row["last_seen_at"]),
            seen_count=row["seen_count"],
            recommendation=cast(Recommendation, row["recommendation"]),
            overall_score=row["overall_score"],
            confidence=row["confidence"],
            match_report=match_report,
            matched_at=_parse_time(row["matched_at"]),
            status=cast(InboxStatus, row["status"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ValueError) and str(error) == DATABASE_ERROR:
            raise
        raise ValueError(DATABASE_ERROR) from error


def _validate_vacancy_id(value: object) -> None:
    if not isinstance(value, str) or VACANCY_ID_PATTERN.fullmatch(value) is None:
        raise ValueError("vacancy_id must match vac-<64 lowercase hex characters>")


def _validate_persistable_url(value: str | None) -> None:
    if value is None:
        return
    query_keys = {
        key.casefold()
        for key, _ in parse_qsl(urlsplit(value).query, keep_blank_values=True)
    }
    if query_keys & SENSITIVE_QUERY_KEYS:
        raise ValueError("source_url contains a sensitive query parameter")


def _validate_report(report: MatchReport) -> None:
    if report.recommendation not in RECOMMENDATIONS:
        raise ValueError("recommendation must be one of APPLY, REVIEW, SKIP")
    if type(report.overall_score) is not int or not 0 <= report.overall_score <= 100:
        raise ValueError("overall_score must be between 0 and 100")
    if type(report.confidence) is not int or not 0 <= report.confidence <= 100:
        raise ValueError("confidence must be between 0 and 100")


def _as_utc(value: object, field: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return _as_utc(value, "timestamp").isoformat().replace("+00:00", "Z")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError(DATABASE_ERROR)
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")), "timestamp")
