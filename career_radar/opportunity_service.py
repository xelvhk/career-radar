"""Application service for matching and storing manually supplied vacancies."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .collected_vacancy import CollectedVacancyInput, normalize_collected_vacancy
from .local_profile import apply_local_profile, load_local_profile
from .matching import analyze_vacancy
from .matching_config import load_matching_config
from .opportunity_store import OpportunityStore, UpsertResult
from .validation import load_yaml


MAX_VACANCY_BYTES = 800_000


class OpportunityImporter:
    """Run the existing deterministic matcher and persist its safe snapshot."""

    def __init__(
        self,
        root: Path,
        database: Path | str,
        *,
        profile: Path | None = None,
    ) -> None:
        self.store = OpportunityStore(database)
        self.projects = load_yaml(root / "projects.yaml")
        self.skills = load_yaml(root / "skills.yaml")
        goals = load_yaml(root / "career_goals.yaml")
        if profile is not None:
            goals = apply_local_profile(goals, load_local_profile(profile))
        self.goals = goals
        self.config = load_matching_config(
            root / "matching.yaml", self.skills, self.goals
        )

    def import_text(
        self,
        text: str,
        *,
        source: str = "manual",
        source_vacancy_id: str | None = None,
        source_url: str | None = None,
        retrieved_at: datetime | str | None = None,
        matched_at: datetime | None = None,
    ) -> UpsertResult:
        if not isinstance(text, str):
            raise ValueError("vacancy text must be a string")
        if len(text.encode("utf-8")) > MAX_VACANCY_BYTES:
            raise ValueError("vacancy text is too large")
        title, description = split_vacancy(text)
        retrieval_time = parse_retrieved_at(retrieved_at)
        vacancy = normalize_collected_vacancy(
            CollectedVacancyInput(
                source=source,
                source_vacancy_id=source_vacancy_id,
                source_url=source_url,
                retrieved_at=retrieval_time,
                collection_method="manual_url" if source_url else "manual_text",
                title=title,
                description=description,
            )
        )
        report = analyze_vacancy(
            vacancy.matcher_text,
            projects_data=self.projects,
            skills_data=self.skills,
            goals_data=self.goals,
            config=self.config,
        )
        return self.store.upsert(
            vacancy, report, matched_at or datetime.now(timezone.utc)
        )


def split_vacancy(text: str) -> tuple[str, str]:
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


def parse_retrieved_at(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("retrieved_at must be an RFC 3339 timestamp") from error
    else:
        raise ValueError("retrieved_at must be an RFC 3339 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone")
    return parsed.astimezone(timezone.utc)
