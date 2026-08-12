#!/usr/bin/env python3
"""Audit Career Radar evidence against local Git repositories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.source_audit import audit_sources, parse_repository_args  # noqa: E402
from career_radar.validation import load_yaml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify pinned evidence without modifying source repositories."
    )
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        metavar="PROJECT_ID=/ABSOLUTE/PATH",
        help="map a Career Radar project ID to a local Git checkout",
    )
    arguments = parser.parse_args(argv)
    try:
        repositories = parse_repository_args(arguments.repo)
        projects = load_yaml(ROOT / "projects.yaml")
    except ValueError as error:
        parser.error(str(error))

    issues = audit_sources(projects, repositories)
    if issues:
        for issue in issues:
            location = f"/{issue.path}" if issue.path else ""
            print(f"ERROR {issue.project_id}{location}: {issue.message}")
        print(f"Source audit failed with {len(issues)} issue(s).")
        return 1

    artifact_count = sum(
        len(project.get("artifacts", [])) for project in projects["projects"]
    )
    print(
        f"Source audit passed: {len(projects['projects'])} projects, "
        f"{artifact_count} artifacts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
