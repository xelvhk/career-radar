"""Deterministic parsing of untrusted pasted vacancy text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .matching_config import MatchingConfig


RequirementImportance = Literal["required", "preferred"]


@dataclass(frozen=True, slots=True)
class VacancyRequirement:
    skill_id: str
    importance: RequirementImportance
    source_line: str


@dataclass(frozen=True, slots=True)
class Vacancy:
    title: str
    requirements: tuple[VacancyRequirement, ...]
    unmapped_requirement_lines: tuple[str, ...]
    target_roles: tuple[str, ...]
    domains: tuple[str, ...]
    seniority: str | None
    is_remote: bool | None
    minimum_years_experience: int | None
    requires_production_experience: bool
    location_constraints: tuple[str, ...]


@dataclass(slots=True)
class _RequirementState:
    requirements: dict[str, VacancyRequirement]
    unmapped: list[str]
    section: RequirementImportance | None = None
    minimum_years_experience: int | None = None
    requires_production_experience: bool = False


_YEAR_WORDS = {
    "один": 1,
    "одного": 1,
    "два": 2,
    "двух": 2,
    "три": 3,
    "трех": 3,
    "четыре": 4,
    "четырех": 4,
    "пять": 5,
    "пяти": 5,
    "шесть": 6,
    "шести": 6,
    "семь": 7,
    "семи": 7,
    "восемь": 8,
    "восьми": 8,
    "девять": 9,
    "девяти": 9,
    "десять": 10,
    "десяти": 10,
}
_DIGIT_YEARS = re.compile(r"(?<!\w)(\d{1,2})\s*\+?\s*(?:years?|лет|года|год)(?!\w)")
_WORD_YEARS = re.compile(rf"(?<!\w)({'|'.join(_YEAR_WORDS)})\s+(?:лет|года|год)(?!\w)")


def parse_vacancy(text: str, config: MatchingConfig) -> Vacancy:
    """Parse cataloged signals from vacancy text without executing its content."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("vacancy text is empty")
    if len(text) > 200_000:
        raise ValueError("vacancy text exceeds the 200000 character limit")

    raw_lines = [line.strip() for line in text.splitlines()]
    title_index = next(index for index, line in enumerate(raw_lines) if line)
    title = _clean_line(raw_lines[title_index])[:160]
    normalized_text = _normalize(text)

    state = _parse_requirement_lines(raw_lines[title_index + 1 :], config)

    return Vacancy(
        title=title,
        requirements=tuple(state.requirements.values()),
        unmapped_requirement_lines=tuple(dict.fromkeys(state.unmapped)),
        target_roles=tuple(_extract_ids(_normalize(title), config.compiled_role_aliases)),
        domains=tuple(_extract_ids(normalized_text, config.compiled_domain_aliases)),
        seniority=_extract_first(normalized_text, config.compiled_seniority_aliases),
        is_remote=_work_mode(normalized_text, config),
        minimum_years_experience=state.minimum_years_experience,
        requires_production_experience=state.requires_production_experience,
        location_constraints=tuple(
            _extract_ids(normalized_text, config.compiled_location_constraint_aliases)
        ),
    )


def _parse_requirement_lines(raw_lines: list[str], config: MatchingConfig) -> _RequirementState:
    state = _RequirementState({}, [])
    for raw_line in raw_lines:
        if raw_line:
            _consume_requirement_line(state, raw_line, config)
    return state


def _consume_requirement_line(
    state: _RequirementState, raw_line: str, config: MatchingConfig
) -> None:
    clean_line = _clean_line(raw_line)
    normalized_line = _normalize(clean_line.rstrip(":"))
    is_heading, section = _heading_section(normalized_line, state.section, config)
    if is_heading:
        state.section = section
        return
    if _contains_marker(normalized_line, config.negation_markers):
        return

    is_bullet = raw_line.lstrip().startswith(("-", "*", "•"))
    if not _is_requirement_candidate(normalized_line, state.section, is_bullet, config):
        return

    years = _extract_years(normalized_line)
    if years is not None:
        state.minimum_years_experience = max(state.minimum_years_experience or 0, years)
    has_production_constraint = _contains_marker(
        normalized_line, config.production_experience_markers
    )
    state.requires_production_experience |= has_production_constraint
    skill_ids = _extract_ids(normalized_line, config.compiled_skill_aliases)
    importance = _requirement_importance(normalized_line, state.section, config)
    _record_requirements(state.requirements, skill_ids, importance, clean_line)

    looks_like_requirement = state.section is not None and (
        is_bullet or _contains_marker(normalized_line, config.requirement_line_markers)
    )
    if looks_like_requirement and not skill_ids and years is None and not has_production_constraint:
        state.unmapped.append(clean_line)


def _heading_section(
    line: str,
    current: RequirementImportance | None,
    config: MatchingConfig,
) -> tuple[bool, RequirementImportance | None]:
    if _matches_heading(line, config.required_section_markers):
        return True, "required"
    if _matches_heading(line, config.preferred_section_markers):
        return True, "preferred"
    if _matches_heading(line, config.section_stop_markers):
        return True, None
    return False, current


def _is_requirement_candidate(
    line: str,
    section: RequirementImportance | None,
    is_bullet: bool,
    config: MatchingConfig,
) -> bool:
    return (
        section is not None
        or is_bullet
        or _contains_marker(line, config.requirement_line_markers)
        or _contains_marker(line, config.preferred_markers)
    )


def _requirement_importance(
    line: str, section: RequirementImportance | None, config: MatchingConfig
) -> RequirementImportance:
    if section == "preferred" or _contains_marker(line, config.preferred_markers):
        return "preferred"
    return "required"


def _record_requirements(
    requirements: dict[str, VacancyRequirement],
    skill_ids: list[str],
    importance: RequirementImportance,
    source_line: str,
) -> None:
    for skill_id in skill_ids:
        existing = requirements.get(skill_id)
        should_replace = existing is None or (
            existing.importance == "preferred" and importance == "required"
        )
        if should_replace:
            requirements[skill_id] = VacancyRequirement(skill_id, importance, source_line)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").split())


def _clean_line(value: str) -> str:
    return value.strip().lstrip("-*• ").strip()


def _matches_heading(line: str, markers: tuple[str, ...]) -> bool:
    return any(line == marker or line.startswith(f"{marker} ") for marker in markers)


def _contains_marker(line: str, markers: tuple[str, ...]) -> bool:
    return any(_phrase_pattern(marker).search(line) for marker in markers)


def _extract_ids(text: str, aliases: tuple[tuple[str, re.Pattern[str]], ...]) -> list[str]:
    found: list[tuple[int, int, str]] = []
    for item_id, pattern in aliases:
        match = pattern.search(text)
        if match:
            found.append((match.start(), -(match.end() - match.start()), item_id))
    found.sort()
    return list(dict.fromkeys(item_id for _, _, item_id in found))


def _extract_first(text: str, aliases: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
    values = _extract_ids(text, aliases)
    return values[0] if values else None


def _work_mode(text: str, config: MatchingConfig) -> bool | None:
    if _contains_marker(text, config.remote_markers):
        return True
    if _contains_marker(text, config.onsite_markers):
        return False
    return None


def _extract_years(text: str) -> int | None:
    values = [int(value) for value in _DIGIT_YEARS.findall(text)]
    values.extend(_YEAR_WORDS[value] for value in _WORD_YEARS.findall(text))
    return max(values) if values else None


def _phrase_pattern(value: str) -> re.Pattern[str]:
    escaped = re.escape(_normalize(value)).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
