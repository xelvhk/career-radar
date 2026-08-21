"""Validated, source-neutral search plans backed by cataloged evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .validation import ID_PATTERN


SEARCH_PROFILE_SCHEMA_VERSION = 1
SEARCHABLE_LEVELS = {"practical", "public_evidence", "production"}
PROFILE_FIELDS = {
    "id",
    "name",
    "target_role_id",
    "enabled",
    "exclude_terms",
    "variants",
}
VARIANT_FIELDS = {"title_phrase", "skill_ids"}


@dataclass(frozen=True, slots=True)
class SearchVariant:
    title_phrase: str
    skill_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SearchProfile:
    id: str
    name: str
    target_role_id: str
    enabled: bool
    exclude_terms: tuple[str, ...]
    variants: tuple[SearchVariant, ...]


@dataclass(frozen=True, slots=True)
class CompiledSearchQuery:
    profile_id: str
    profile_name: str
    target_role_id: str
    title_phrase: str
    skill_ids: tuple[str, ...]
    skill_terms: tuple[str, ...]
    exclude_terms: tuple[str, ...]


def validate_search_profiles(
    data: dict[str, Any],
    skills_data: dict[str, Any],
    goals_data: dict[str, Any],
    matching_data: dict[str, Any],
) -> list[str]:
    """Return deterministic cross-file errors for saved search profiles."""
    errors: list[str] = []
    if data.get("schema_version") != SEARCH_PROFILE_SCHEMA_VERSION:
        errors.append(
            f"schema_version must equal {SEARCH_PROFILE_SCHEMA_VERSION}"
        )
    profiles = data.get("search_profiles")
    if not isinstance(profiles, list) or not profiles:
        return errors + ["search_profiles must be a non-empty list"]

    skill_items = skills_data.get("skills")
    if not isinstance(skill_items, list):
        skill_items = []
    skills = {
        item.get("id"): item
        for item in skill_items
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    career_goals = goals_data.get("career_goals")
    if not isinstance(career_goals, dict):
        career_goals = {}
    target_roles = career_goals.get("target_roles")
    if not isinstance(target_roles, list):
        target_roles = []
    roles = {
        item.get("id")
        for item in target_roles
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    aliases = matching_data.get("skill_aliases")
    if not isinstance(aliases, dict):
        aliases = {}
    seen_ids: set[str] = set()

    for index, profile in enumerate(profiles):
        path = f"search_profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{path} must be a mapping")
            continue
        if set(profile) != PROFILE_FIELDS:
            errors.append(f"{path} must define exactly the profile contract fields")

        profile_id = profile.get("id")
        if not isinstance(profile_id, str) or ID_PATTERN.fullmatch(profile_id) is None:
            errors.append(f"{path}.id must be a lowercase kebab-case identifier")
        elif profile_id in seen_ids:
            errors.append(f"{path}.id is a duplicate profile id")
        else:
            seen_ids.add(profile_id)
        if not _bounded_text(profile.get("name"), 100):
            errors.append(f"{path}.name must be non-empty text up to 100 characters")
        if profile.get("target_role_id") not in roles:
            errors.append(f"{path}.target_role_id references an unknown target role")
        if type(profile.get("enabled")) is not bool:
            errors.append(f"{path}.enabled must be boolean")

        exclusions = profile.get("exclude_terms")
        if not _term_list(exclusions, maximum=20):
            errors.append(
                f"{path}.exclude_terms must contain 1 to 20 unique non-empty terms"
            )

        variants = profile.get("variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{path}.variants must be a non-empty list")
            continue
        seen_variants: set[tuple[str, tuple[str, ...]]] = set()
        for variant_index, variant in enumerate(variants):
            variant_path = f"{path}.variants[{variant_index}]"
            if not isinstance(variant, dict):
                errors.append(f"{variant_path} must be a mapping")
                continue
            if set(variant) != VARIANT_FIELDS:
                errors.append(
                    f"{variant_path} must define title_phrase and skill_ids"
                )
            if not _bounded_text(variant.get("title_phrase"), 120):
                errors.append(
                    f"{variant_path}.title_phrase must be non-empty text up to 120 characters"
                )
            skill_ids = variant.get("skill_ids")
            if not _id_list(skill_ids, maximum=5):
                errors.append(
                    f"{variant_path}.skill_ids must contain 1 to 5 unique skill IDs"
                )
                continue
            title_phrase = variant.get("title_phrase")
            if isinstance(title_phrase, str):
                signature = (title_phrase, tuple(skill_ids))
                if signature in seen_variants:
                    errors.append(f"{variant_path} is a duplicate query variant")
                else:
                    seen_variants.add(signature)
            for skill_id in skill_ids:
                skill = skills.get(skill_id)
                if skill is None:
                    errors.append(
                        f"{variant_path}.skill_ids references unknown skill {skill_id}"
                    )
                    continue
                if skill.get("level") not in SEARCHABLE_LEVELS:
                    errors.append(
                        f"{variant_path}.skill_ids {skill_id} lacks verified evidence"
                    )
                skill_aliases = aliases.get(skill_id)
                if not isinstance(skill_aliases, list) or not skill_aliases:
                    errors.append(
                        f"{variant_path}.skill_ids {skill_id} has no search alias"
                    )
    return errors


def parse_search_profiles(
    data: dict[str, Any],
    skills_data: dict[str, Any],
    goals_data: dict[str, Any],
    matching_data: dict[str, Any],
) -> tuple[SearchProfile, ...]:
    errors = validate_search_profiles(data, skills_data, goals_data, matching_data)
    if errors:
        raise ValueError("invalid search profiles: " + "; ".join(errors))
    return tuple(
        SearchProfile(
            id=item["id"],
            name=item["name"],
            target_role_id=item["target_role_id"],
            enabled=item["enabled"],
            exclude_terms=tuple(item["exclude_terms"]),
            variants=tuple(
                SearchVariant(
                    title_phrase=variant["title_phrase"],
                    skill_ids=tuple(variant["skill_ids"]),
                )
                for variant in item["variants"]
            ),
        )
        for item in data["search_profiles"]
    )


def compile_search_queries(
    profiles: tuple[SearchProfile, ...], matching_data: dict[str, Any]
) -> tuple[CompiledSearchQuery, ...]:
    aliases = matching_data["skill_aliases"]
    return tuple(
        CompiledSearchQuery(
            profile_id=profile.id,
            profile_name=profile.name,
            target_role_id=profile.target_role_id,
            title_phrase=variant.title_phrase,
            skill_ids=variant.skill_ids,
            skill_terms=tuple(aliases[skill_id][0] for skill_id in variant.skill_ids),
            exclude_terms=profile.exclude_terms,
        )
        for profile in profiles
        if profile.enabled
        for variant in profile.variants
    )


def _bounded_text(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= maximum
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def _id_list(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, list)
        and 1 <= len(value) <= maximum
        and all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value))
    )


def _term_list(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, list)
        and 1 <= len(value) <= maximum
        and all(_bounded_text(item, 80) for item in value)
        and len(value) == len({item.casefold() for item in value})
    )
