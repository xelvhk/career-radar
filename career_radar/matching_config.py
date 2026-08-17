"""Validated configuration for deterministic vacancy matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validation import load_yaml


DIMENSION_NAMES = (
    "technical",
    "evidence",
    "direction",
    "domain",
    "seniority",
    "location",
    "salary",
)


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    compiled_skill_aliases: tuple[tuple[str, re.Pattern[str]], ...]
    compiled_role_aliases: tuple[tuple[str, re.Pattern[str]], ...]
    compiled_domain_aliases: tuple[tuple[str, re.Pattern[str]], ...]
    compiled_seniority_aliases: tuple[tuple[str, re.Pattern[str]], ...]
    compiled_location_constraint_aliases: tuple[tuple[str, re.Pattern[str]], ...]
    preferred_markers: tuple[str, ...]
    negation_markers: tuple[str, ...]
    required_section_markers: tuple[str, ...]
    preferred_section_markers: tuple[str, ...]
    section_stop_markers: tuple[str, ...]
    requirement_line_markers: tuple[str, ...]
    remote_markers: tuple[str, ...]
    onsite_markers: tuple[str, ...]
    production_experience_markers: tuple[str, ...]
    weights: dict[str, int]
    apply_score: int
    skip_score: int
    minimum_confidence: int


def load_matching_config(
    path: Path, skills_data: dict[str, Any], goals_data: dict[str, Any]
) -> MatchingConfig:
    data = load_yaml(path)
    errors = validate_matching_config(data, skills_data, goals_data)
    if errors:
        raise ValueError("invalid matching config: " + "; ".join(errors))
    return MatchingConfig(
        compiled_skill_aliases=_compile_alias_map(data["skill_aliases"]),
        compiled_role_aliases=_compile_alias_map(data["role_aliases"]),
        compiled_domain_aliases=_compile_alias_map(data["domain_aliases"]),
        compiled_seniority_aliases=_compile_alias_map(data["seniority_aliases"]),
        compiled_location_constraint_aliases=_compile_alias_map(
            data["location_constraint_aliases"]
        ),
        preferred_markers=_markers(data["preferred_markers"]),
        negation_markers=_markers(data["negation_markers"]),
        required_section_markers=_markers(data["required_section_markers"]),
        preferred_section_markers=_markers(data["preferred_section_markers"]),
        section_stop_markers=_markers(data["section_stop_markers"]),
        requirement_line_markers=_markers(data["requirement_line_markers"]),
        remote_markers=_markers(data["remote_markers"]),
        onsite_markers=_markers(data["onsite_markers"]),
        production_experience_markers=_markers(
            data["production_experience_markers"]
        ),
        weights=dict(data["weights"]),
        apply_score=data["thresholds"]["apply_score"],
        skip_score=data["thresholds"]["skip_score"],
        minimum_confidence=data["thresholds"]["minimum_confidence"],
    )


def validate_matching_config(
    data: dict[str, Any], skills_data: dict[str, Any], goals_data: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 2:
        errors.append("schema_version must equal 2")

    skill_ids = _ids(skills_data.get("skills"))
    goals = goals_data.get("career_goals", {})
    role_ids = _ids(goals.get("target_roles") if isinstance(goals, dict) else None)
    domain_ids = set(goals.get("preferred_domains", [])) if isinstance(goals, dict) else set()
    for key, known_ids in (
        ("skill_aliases", skill_ids),
        ("role_aliases", role_ids),
        ("domain_aliases", domain_ids),
    ):
        aliases = data.get(key)
        if not isinstance(aliases, dict) or not aliases:
            errors.append(f"{key} must be a non-empty mapping")
            continue
        unknown = set(aliases) - known_ids
        if unknown:
            errors.append(f"{key} references unknown IDs: {', '.join(sorted(unknown))}")
        _validate_alias_values(key, aliases, errors)

    seniority = data.get("seniority_aliases")
    if not isinstance(seniority, dict) or not seniority:
        errors.append("seniority_aliases must be a non-empty mapping")
    else:
        _validate_alias_values("seniority_aliases", seniority, errors)

    location_constraints = data.get("location_constraint_aliases")
    if not isinstance(location_constraints, dict) or not location_constraints:
        errors.append("location_constraint_aliases must be a non-empty mapping")
    else:
        _validate_alias_values(
            "location_constraint_aliases", location_constraints, errors
        )

    for key in (
        "preferred_markers",
        "negation_markers",
        "required_section_markers",
        "preferred_section_markers",
        "section_stop_markers",
        "requirement_line_markers",
        "remote_markers",
        "onsite_markers",
        "production_experience_markers",
    ):
        if not _string_list(data.get(key)):
            errors.append(f"{key} must be a non-empty list of strings")

    weights = data.get("weights")
    if not isinstance(weights, dict) or set(weights) != set(DIMENSION_NAMES):
        errors.append("weights must define exactly the seven match dimensions")
    elif not all(isinstance(value, int) and value > 0 for value in weights.values()):
        errors.append("weights must be positive integers")
    elif sum(weights.values()) != 100:
        errors.append("weights must total 100")

    thresholds = data.get("thresholds")
    required_thresholds = {"apply_score", "skip_score", "minimum_confidence"}
    if not isinstance(thresholds, dict) or set(thresholds) != required_thresholds:
        errors.append("thresholds must define apply_score, skip_score, minimum_confidence")
    elif not all(
        isinstance(value, int) and 0 <= value <= 100 for value in thresholds.values()
    ):
        errors.append("thresholds must be integer percentages")
    elif thresholds["skip_score"] >= thresholds["apply_score"]:
        errors.append("skip_score must be lower than apply_score")

    duplicate_aliases: dict[str, str] = {}
    for map_name in ("skill_aliases", "role_aliases", "domain_aliases"):
        aliases = data.get(map_name, {})
        if not isinstance(aliases, dict):
            continue
        for item_id, values in aliases.items():
            if not isinstance(values, list):
                continue
            for alias in values:
                if not isinstance(alias, str):
                    continue
                normalized = _normalize(alias)
                owner = duplicate_aliases.get(normalized)
                if owner and owner != item_id:
                    errors.append(f"alias {alias!r} is shared by {owner} and {item_id}")
                duplicate_aliases[normalized] = item_id
    return errors


def _compile_alias_map(data: dict[str, list[str]]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for item_id, aliases in data.items():
        alternatives = sorted(
            (_escaped_phrase(alias) for alias in aliases), key=len, reverse=True
        )
        compiled.append(
            (item_id, re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)", re.IGNORECASE))
        )
    return tuple(compiled)


def _escaped_phrase(value: str) -> str:
    return re.escape(_normalize(value)).replace(r"\ ", r"\s+")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def _markers(values: list[str]) -> tuple[str, ...]:
    return tuple(_normalize(value) for value in values)


def _ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {
        item["id"]
        for item in value
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _validate_alias_values(
    name: str, aliases: dict[str, Any], errors: list[str]
) -> None:
    for item_id, values in aliases.items():
        if not _string_list(values):
            errors.append(f"{name}.{item_id} must be a non-empty list of strings")


def _string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )
