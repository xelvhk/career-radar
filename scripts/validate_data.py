#!/usr/bin/env python3
"""Validate Career Radar's checked-in evidence data."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.validation import load_yaml, validate_dataset  # noqa: E402
from career_radar.matching_config import validate_matching_config  # noqa: E402


def main() -> int:
    try:
        projects = load_yaml(ROOT / "projects.yaml")
        skills = load_yaml(ROOT / "skills.yaml")
        goals = load_yaml(ROOT / "career_goals.yaml")
        matching = load_yaml(ROOT / "matching.yaml")
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1

    issues = validate_dataset(projects, skills, goals)
    matching_errors = validate_matching_config(matching, skills, goals)
    if issues:
        for issue in issues:
            print(f"ERROR {issue.path}: {issue.message}")
        print(f"Validation failed with {len(issues)} issue(s).")
        return 1
    if matching_errors:
        for error in matching_errors:
            print(f"ERROR matching: {error}")
        print(f"Validation failed with {len(matching_errors)} matching issue(s).")
        return 1

    project_count = len(projects["projects"])
    skill_count = len(skills["skills"])
    alias_count = len(matching["skill_aliases"])
    print(
        f"Career data is valid: {project_count} projects, {skill_count} skills, "
        f"{alias_count} matching profiles."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
