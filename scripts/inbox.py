#!/usr/bin/env python3
"""Manage the local, evidence-aware Opportunity Inbox."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from career_radar.collected_vacancy import (  # noqa: E402
    CollectedVacancyInput,
    normalize_collected_vacancy,
)
from career_radar.local_profile import apply_local_profile, load_local_profile  # noqa: E402
from career_radar.matching import analyze_vacancy  # noqa: E402
from career_radar.matching_config import load_matching_config  # noqa: E402
from career_radar.opportunity_reporting import (  # noqa: E402
    import_result_to_json,
    import_result_to_markdown,
    opportunity_list_to_json,
    opportunity_list_to_markdown,
    opportunity_to_json,
    opportunity_to_markdown,
)
from career_radar.opportunity_store import OpportunityStore  # noqa: E402
from career_radar.validation import load_yaml  # noqa: E402


DEFAULT_DATABASE = ROOT / "career_radar.local.sqlite3"


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        output = _dispatch(arguments)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(output)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the local evidence-aware Opportunity Inbox."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    import_command = commands.add_parser("import", help="match and save a vacancy")
    import_command.add_argument("vacancy", type=Path, help="UTF-8 vacancy text file")
    import_command.add_argument("--source", default="manual")
    import_command.add_argument("--source-id")
    import_command.add_argument("--source-url")
    import_command.add_argument("--retrieved-at")
    import_command.add_argument("--profile", type=Path)
    _add_common_arguments(import_command)

    list_command = commands.add_parser("list", help="list ranked opportunities")
    list_command.add_argument(
        "--recommendation", choices=("APPLY", "REVIEW", "SKIP")
    )
    list_command.add_argument(
        "--status", choices=("new", "shortlisted", "dismissed")
    )
    list_command.add_argument("--limit", type=_limit, default=20)
    _add_common_arguments(list_command)

    show_command = commands.add_parser("show", help="show one explained opportunity")
    show_command.add_argument("vacancy_id")
    _add_common_arguments(show_command)

    status_command = commands.add_parser(
        "set-status", help="record a human inbox decision"
    )
    status_command.add_argument("vacancy_id")
    status_command.add_argument(
        "status", choices=("new", "shortlisted", "dismissed")
    )
    _add_common_arguments(status_command)
    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )


def _dispatch(arguments: argparse.Namespace) -> str:
    if arguments.command == "import":
        return _import(arguments)
    store = OpportunityStore(arguments.db)
    if arguments.command == "list":
        opportunities = store.list(
            recommendation=arguments.recommendation,
            status=arguments.status,
            limit=arguments.limit,
        )
        return (
            opportunity_list_to_json(opportunities)
            if arguments.format == "json"
            else opportunity_list_to_markdown(opportunities)
        )
    if arguments.command == "show":
        opportunity = store.get(arguments.vacancy_id)
        return (
            opportunity_to_json(opportunity, operation="show")
            if arguments.format == "json"
            else opportunity_to_markdown(opportunity)
        )
    opportunity = store.set_status(arguments.vacancy_id, arguments.status)
    return (
        opportunity_to_json(opportunity, operation="set-status")
        if arguments.format == "json"
        else opportunity_to_markdown(opportunity, heading="Opportunity Status Updated")
    )


def _import(arguments: argparse.Namespace) -> str:
    text = _read_vacancy(arguments.vacancy)
    projects = load_yaml(ROOT / "projects.yaml")
    skills = load_yaml(ROOT / "skills.yaml")
    goals = load_yaml(ROOT / "career_goals.yaml")
    if arguments.profile is not None:
        goals = apply_local_profile(goals, load_local_profile(arguments.profile))
    config = load_matching_config(ROOT / "matching.yaml", skills, goals)

    retrieved_at = _retrieved_at(arguments.retrieved_at)
    collection_method = "manual_url" if arguments.source_url else "manual_text"
    title, description = _split_vacancy(text)
    vacancy = normalize_collected_vacancy(
        CollectedVacancyInput(
            source=arguments.source,
            source_vacancy_id=arguments.source_id,
            source_url=arguments.source_url,
            retrieved_at=retrieved_at,
            collection_method=collection_method,
            title=title,
            description=description,
        )
    )
    report = analyze_vacancy(
        vacancy.matcher_text,
        projects_data=projects,
        skills_data=skills,
        goals_data=goals,
        config=config,
    )
    result = OpportunityStore(arguments.db).upsert(
        vacancy, report, datetime.now(timezone.utc)
    )
    return (
        import_result_to_json(result)
        if arguments.format == "json"
        else import_result_to_markdown(result)
    )


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


def _split_vacancy(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    title_index = next(
        (index for index, line in enumerate(lines) if line.strip()), None
    )
    if title_index is None:
        raise ValueError("vacancy text is empty")
    title = lines[title_index].strip()
    description = "\n".join(lines[title_index + 1 :]).strip()
    if not description:
        raise ValueError("vacancy description is empty")
    return title, description


def _retrieved_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("retrieved_at must be an RFC 3339 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("limit must be an integer") from error
    if not 1 <= limit <= 100:
        raise argparse.ArgumentTypeError("limit must be between 1 and 100")
    return limit


if __name__ == "__main__":
    raise SystemExit(main())
