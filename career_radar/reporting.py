"""Stable JSON and human-readable Markdown vacancy match reports."""

from __future__ import annotations

import json
from typing import Any

from .matching import MatchReport


def report_to_dict(report: MatchReport) -> dict[str, Any]:
    return {
        "reportVersion": 1,
        "vacancy": {
            "title": report.vacancy.title,
            "seniority": report.vacancy.seniority,
            "isRemote": report.vacancy.is_remote,
            "targetRoles": list(report.vacancy.target_roles),
            "domains": list(report.vacancy.domains),
            "unmappedRequirementLines": list(
                report.vacancy.unmapped_requirement_lines
            ),
        },
        "overallScore": report.overall_score,
        "confidence": report.confidence,
        "recommendation": report.recommendation,
        "reasons": list(report.reasons),
        "requiredGaps": list(report.required_gaps),
        "dimensions": [
            {
                "name": item.name,
                "status": item.status,
                "score": item.score,
                "weight": item.weight,
                "reason": item.reason,
            }
            for item in report.dimensions
        ],
        "requirementMappings": [
            {
                "skillId": item.skill_id,
                "skillName": item.skill_name,
                "importance": item.importance,
                "skillLevel": item.skill_level,
                "evidenceStatus": item.evidence_status,
                "projects": list(item.projects),
                "artifacts": list(item.artifacts),
            }
            for item in report.requirement_mappings
        ],
    }


def report_to_json(report: MatchReport) -> str:
    return json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True)


def report_to_markdown(report: MatchReport) -> str:
    lines = [
        "# Vacancy Match",
        "",
        f"**Role:** {_escape_markdown(report.vacancy.title)}",
        f"**Recommendation:** {report.recommendation}",
        f"**Opportunity score:** {report.overall_score}%",
        f"**Confidence:** {report.confidence}%",
        "",
        "## Why",
        "",
    ]
    lines.extend(f"- {_escape_markdown(reason)}." for reason in report.reasons)
    lines.extend(["", "## Dimensions", "", "| Dimension | Score | Weight | Explanation |", "|---|---:|---:|---|"])
    for item in report.dimensions:
        score = f"{item.score}%" if item.score is not None else "unknown"
        lines.append(
            f"| {_escape_markdown(item.name)} | {score} | {item.weight} | "
            f"{_escape_markdown(item.reason)} |"
        )

    lines.extend(
        [
            "",
            "## Evidence mapping",
            "",
            "| Requirement | Importance | Evidence | Projects |",
            "|---|---|---|---|",
        ]
    )
    if report.requirement_mappings:
        for item in report.requirement_mappings:
            projects = _escape_markdown(", ".join(item.projects) or "none")
            lines.append(
                f"| {_escape_markdown(item.skill_name)} | "
                f"{_escape_markdown(item.importance)} | "
                f"{_escape_markdown(item.evidence_status)} | {projects} |"
            )
    else:
        lines.append("| none recognized | — | gap | none |")

    if report.required_gaps:
        lines.extend(["", "## Required gaps", ""])
        lines.extend(f"- `{skill_id}`" for skill_id in report.required_gaps)
    if report.vacancy.unmapped_requirement_lines:
        lines.extend(["", "## Unmapped requirement lines", ""])
        lines.extend(
            f"- {_escape_markdown(line)}"
            for line in report.vacancy.unmapped_requirement_lines
        )
    return "\n".join(lines) + "\n"


def _escape_markdown(value: str) -> str:
    safe_value = "".join(
        character for character in value if ord(character) >= 32 and ord(character) != 127
    )
    escaped = safe_value.replace("\\", "\\\\")
    for character in ("`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "!", "|", "<", ">"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped
