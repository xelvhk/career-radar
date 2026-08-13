#!/usr/bin/env python3
"""Match one local vacancy text file against verified career evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.matching import analyze_vacancy  # noqa: E402
from career_radar.matching_config import load_matching_config  # noqa: E402
from career_radar.reporting import report_to_json, report_to_markdown  # noqa: E402
from career_radar.validation import load_yaml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Produce an evidence-backed match report for one vacancy."
    )
    parser.add_argument("vacancy", type=Path, help="UTF-8 vacancy text file")
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    arguments = parser.parse_args(argv)

    try:
        text = _read_vacancy(arguments.vacancy)
        projects = load_yaml(ROOT / "projects.yaml")
        skills = load_yaml(ROOT / "skills.yaml")
        goals = load_yaml(ROOT / "career_goals.yaml")
        config = load_matching_config(ROOT / "matching.yaml", skills, goals)
        report = analyze_vacancy(
            text,
            projects_data=projects,
            skills_data=skills,
            goals_data=goals,
            config=config,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    output = report_to_json(report) if arguments.format == "json" else report_to_markdown(report)
    print(output)
    return 0


def _read_vacancy(path: Path) -> str:
    try:
        if not path.is_file():
            raise ValueError("vacancy path must be a regular file")
        with path.open("rb") as source:
            raw = source.read(800_001)
    except OSError as error:
        raise ValueError("cannot read vacancy file") from error
    if len(raw) > 800_000:
        raise ValueError("vacancy file is too large")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("vacancy file must be UTF-8") from error


if __name__ == "__main__":
    raise SystemExit(main())
