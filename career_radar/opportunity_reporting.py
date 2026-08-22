"""Stable privacy-safe JSON and Markdown Opportunity Inbox output."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .opportunity_store import Opportunity, UpsertResult


INBOX_OUTPUT_VERSION = 1


def import_result_to_json(result: UpsertResult) -> str:
    return _to_json(
        {
            "inboxVersion": INBOX_OUTPUT_VERSION,
            "operation": "import",
            "created": result.created,
            "stale": result.stale,
            "opportunity": opportunity_to_dict(
                result.opportunity, include_match_report=True
            ),
        }
    )


def opportunity_to_json(opportunity: Opportunity, *, operation: str) -> str:
    return _to_json(
        {
            "inboxVersion": INBOX_OUTPUT_VERSION,
            "operation": operation,
            "opportunity": opportunity_to_dict(
                opportunity, include_match_report=True
            ),
        }
    )


def opportunity_list_to_json(opportunities: tuple[Opportunity, ...]) -> str:
    return _to_json(
        {
            "inboxVersion": INBOX_OUTPUT_VERSION,
            "operation": "list",
            "opportunityCount": len(opportunities),
            "opportunities": [
                opportunity_to_dict(item, include_match_report=False)
                for item in opportunities
            ],
        }
    )


def opportunity_to_dict(
    opportunity: Opportunity, *, include_match_report: bool
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": opportunity.vacancy.id,
        "title": opportunity.vacancy.title,
        "source": {
            "name": opportunity.vacancy.source,
            "vacancyId": opportunity.vacancy.source_vacancy_id,
            "url": opportunity.vacancy.source_url,
        },
        "collectionMethod": opportunity.vacancy.collection_method,
        "firstSeenAt": _format_time(opportunity.first_seen_at),
        "lastSeenAt": _format_time(opportunity.last_seen_at),
        "seenCount": opportunity.seen_count,
        "matchedAt": _format_time(opportunity.matched_at),
        "status": opportunity.status,
        "recommendation": opportunity.recommendation,
        "overallScore": opportunity.overall_score,
        "confidence": opportunity.confidence,
    }
    if include_match_report:
        payload["matchReport"] = opportunity.match_report
    return payload


def import_result_to_markdown(result: UpsertResult) -> str:
    state = "created" if result.created else "stale" if result.stale else "updated"
    return _opportunity_markdown(result.opportunity, heading="Opportunity Imported", state=state)


def opportunity_to_markdown(
    opportunity: Opportunity, *, heading: str = "Opportunity"
) -> str:
    return _opportunity_markdown(opportunity, heading=heading, state=None)


def opportunity_list_to_markdown(
    opportunities: tuple[Opportunity, ...]
) -> str:
    lines = [
        "# Opportunity Inbox",
        "",
        "| Recommendation | Score | Status | Role | Last seen | ID |",
        "|---|---:|---|---|---|---|",
    ]
    if not opportunities:
        lines.append("| — | — | — | No opportunities | — | — |")
    for item in opportunities:
        lines.append(
            f"| {item.recommendation} | {item.overall_score}% | "
            f"{_escape_markdown(item.status)} | "
            f"{_escape_markdown(item.vacancy.title)} | "
            f"{_format_time(item.last_seen_at)} | `{item.vacancy.id}` |"
        )
    return "\n".join(lines) + "\n"


def _opportunity_markdown(
    opportunity: Opportunity, *, heading: str, state: str | None
) -> str:
    source_url = opportunity.vacancy.source_url or "not recorded"
    source_id = opportunity.vacancy.source_vacancy_id or "not recorded"
    lines = [
        f"# {heading}",
        "",
        f"**Role:** {_escape_markdown(opportunity.vacancy.title)}",
        f"**Recommendation:** {opportunity.recommendation}",
        f"**Opportunity score:** {opportunity.overall_score}%",
        f"**Confidence:** {opportunity.confidence}%",
        f"**Inbox status:** {_escape_markdown(opportunity.status)}",
        f"**Vacancy ID:** `{opportunity.vacancy.id}`",
    ]
    if state is not None:
        lines.append(f"**Import result:** {state}")
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"- Source: `{_escape_markdown(opportunity.vacancy.source)}`",
            f"- Source vacancy ID: `{_escape_markdown(source_id)}`",
            f"- Source URL: `{_escape_markdown(source_url)}`",
            f"- Collection method: `{opportunity.vacancy.collection_method}`",
            f"- First seen: `{_format_time(opportunity.first_seen_at)}`",
            f"- Last seen: `{_format_time(opportunity.last_seen_at)}`",
            f"- Seen count: {opportunity.seen_count}",
            "",
            "## Why",
            "",
        ]
    )
    report = opportunity.match_report
    reasons = _string_list(report.get("reasons"))
    lines.extend(
        f"- {_escape_markdown(reason)}" for reason in reasons
    )
    if not reasons:
        lines.append("- No explanation recorded")

    _append_list_section(lines, "Required gaps", report.get("requiredGaps"))
    _append_list_section(
        lines, "Unverified mandatory constraints", report.get("unverifiedConstraints")
    )
    mappings = report.get("requirementMappings")
    lines.extend(
        [
            "",
            "## Evidence mapping",
            "",
            "| Requirement | Importance | Evidence | Projects |",
            "|---|---|---|---|",
        ]
    )
    if isinstance(mappings, list):
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            projects = mapping.get("projects")
            project_names = ", ".join(_string_list(projects)) or "none"
            lines.append(
                f"| {_escape_markdown(str(mapping.get('skillName', 'unknown')))} | "
                f"{_escape_markdown(str(mapping.get('importance', 'unknown')))} | "
                f"{_escape_markdown(str(mapping.get('evidenceStatus', 'unknown')))} | "
                f"{_escape_markdown(project_names)} |"
            )
    if len(lines) == 0 or lines[-1] == "|---|---|---|---|":
        lines.append("| none recognized | — | gap | none |")
    return "\n".join(lines) + "\n"


def _append_list_section(lines: list[str], heading: str, value: object) -> None:
    items = _string_list(value)
    if not items:
        return
    lines.extend(["", f"## {heading}", ""])
    lines.extend(f"- `{_escape_markdown(item)}`" for item in items)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _escape_markdown(value: str) -> str:
    safe_value = "".join(
        character
        for character in value
        if ord(character) >= 32 and ord(character) != 127
    )
    escaped = safe_value.replace("\\", "\\\\")
    for character in ("`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "!", "|", "<", ">"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _format_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
