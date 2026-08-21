"""Private, local-only matcher inputs kept outside the evidence catalog."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROFILE_SCHEMA_VERSION = 1
MAX_PROFILE_BYTES = 64_000
SENIORITY_VALUES = {"junior", "middle", "senior", "lead"}
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")
PROFILE_FIELDS = {
    "commercial_years",
    "confirmed_production_experience",
    "current_country_code",
    "target_seniority",
}


@dataclass(frozen=True, slots=True)
class LocalProfile:
    commercial_years: int | None
    confirmed_production_experience: bool | None
    current_country_code: str | None
    target_seniority: tuple[str, ...]


def load_local_profile(path: Path) -> LocalProfile:
    """Load and validate the narrowly scoped local profile file."""
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_PROFILE_BYTES + 1)
    except OSError as error:
        raise ValueError("cannot read local profile file") from error
    if len(raw) > MAX_PROFILE_BYTES:
        raise ValueError("local profile file is too large")
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("local profile file must be UTF-8") from error
    except yaml.YAMLError as error:
        raise ValueError("local profile file is not valid YAML") from error

    errors = validate_local_profile(data)
    if errors:
        raise ValueError("invalid local profile: " + "; ".join(errors))

    profile = data["profile"]
    return LocalProfile(
        commercial_years=profile["commercial_years"],
        confirmed_production_experience=profile["confirmed_production_experience"],
        current_country_code=profile["current_country_code"],
        target_seniority=tuple(profile["target_seniority"]),
    )


def validate_local_profile(data: Any) -> list[str]:
    """Return concise field-level errors without exposing profile values."""
    if not isinstance(data, dict):
        return ["root must be a mapping"]

    errors: list[str] = []
    if set(data) != {"schema_version", "profile"}:
        errors.append("root must contain only schema_version and profile")
    if data.get("schema_version") != PROFILE_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {PROFILE_SCHEMA_VERSION}")

    profile = data.get("profile")
    if not isinstance(profile, dict):
        return errors + ["profile must be a mapping"]
    unknown_fields = set(profile) - PROFILE_FIELDS
    missing_fields = PROFILE_FIELDS - set(profile)
    if unknown_fields:
        errors.append("profile contains unsupported fields")
    if missing_fields:
        errors.append("profile is missing required fields")

    years = profile.get("commercial_years")
    if years is not None and (type(years) is not int or not 0 <= years <= 60):
        errors.append("profile.commercial_years must be an integer from 0 to 60 or null")
    production = profile.get("confirmed_production_experience")
    if production is not None and type(production) is not bool:
        errors.append("profile.confirmed_production_experience must be true, false, or null")
    country = profile.get("current_country_code")
    if country is not None and (
        not isinstance(country, str) or COUNTRY_CODE_PATTERN.fullmatch(country) is None
    ):
        errors.append("profile.current_country_code must be an ISO alpha-2 code or null")
    seniority = profile.get("target_seniority")
    if not isinstance(seniority, list) or any(
        value not in SENIORITY_VALUES for value in seniority
    ):
        errors.append("profile.target_seniority must contain supported seniority values")
    elif len(seniority) != len(set(seniority)):
        errors.append("profile.target_seniority must not contain duplicates")
    return errors


def apply_local_profile(
    goals_data: dict[str, Any], profile: LocalProfile
) -> dict[str, Any]:
    """Overlay explicit local facts without mutating checked-in career goals."""
    merged = copy.deepcopy(goals_data)
    goals = merged["career_goals"]

    existing_experience = goals.get("experience_profile", {})
    experience_profile = (
        dict(existing_experience) if isinstance(existing_experience, dict) else {}
    )
    if profile.commercial_years is not None:
        experience_profile["commercial_years"] = profile.commercial_years
    if profile.confirmed_production_experience is not None:
        experience_profile["verified_production_experience"] = (
            profile.confirmed_production_experience
        )
    if experience_profile:
        goals["experience_profile"] = experience_profile

    if profile.current_country_code is not None:
        work_preferences = goals["work_preferences"]
        work_preferences["current_country_codes"] = [profile.current_country_code]
    if profile.target_seniority:
        goals["target_seniority"] = list(profile.target_seniority)
    return merged
