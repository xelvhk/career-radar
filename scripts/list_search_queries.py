#!/usr/bin/env python3
"""List source-neutral, evidence-backed vacancy search query plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.search_profiles import (  # noqa: E402
    CompiledSearchQuery,
    compile_search_queries,
    parse_search_profiles,
)
from career_radar.validation import load_yaml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List source-neutral vacancy search query plans."
    )
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    arguments = parser.parse_args(argv)

    try:
        profile_data = load_yaml(ROOT / "search_profiles.yaml")
        skills = load_yaml(ROOT / "skills.yaml")
        goals = load_yaml(ROOT / "career_goals.yaml")
        matching = load_yaml(ROOT / "matching.yaml")
        profiles = parse_search_profiles(profile_data, skills, goals, matching)
        queries = compile_search_queries(profiles, matching)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if arguments.format == "json":
        print(_to_json(queries))
    else:
        print(_to_markdown(queries))
    return 0


def _to_json(queries: tuple[CompiledSearchQuery, ...]) -> str:
    profile_ids = tuple(dict.fromkeys(query.profile_id for query in queries))
    payload = {
        "queryPlanVersion": 1,
        "profileCount": len(profile_ids),
        "queryCount": len(queries),
        "queries": [_query_to_dict(query) for query in queries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _query_to_dict(query: CompiledSearchQuery) -> dict[str, object]:
    return {
        "profileId": query.profile_id,
        "profileName": query.profile_name,
        "targetRoleId": query.target_role_id,
        "titlePhrase": query.title_phrase,
        "skillIds": list(query.skill_ids),
        "skillTerms": list(query.skill_terms),
        "excludeTerms": list(query.exclude_terms),
    }


def _to_markdown(queries: tuple[CompiledSearchQuery, ...]) -> str:
    lines = ["# Saved Search Queries"]
    current_profile: str | None = None
    for query in queries:
        if query.profile_id != current_profile:
            current_profile = query.profile_id
            lines.extend(
                [
                    "",
                    f"## {_escape_markdown(query.profile_name)}",
                    "",
                    f"Target role: `{query.target_role_id}`",
                    "",
                ]
            )
        skills = ", ".join(_escape_markdown(term) for term in query.skill_terms)
        exclusions = ", ".join(
            _escape_markdown(term) for term in query.exclude_terms
        )
        lines.append(
            f"- **{_escape_markdown(query.title_phrase)}** — skills: {skills}; "
            f"exclude: {exclusions}"
        )
    return "\n".join(lines) + "\n"


def _escape_markdown(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "<", ">", "|"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


if __name__ == "__main__":
    raise SystemExit(main())
