"""Deterministic validation for Career Radar's versioned YAML sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml


SCHEMA_VERSION = 2
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VERIFICATION_STATES = {"pending", "verified"}
DISCLOSURE_STATES = {"public", "on_request", "private"}
REPOSITORY_VISIBILITIES = {"public", "private"}
SKILL_LEVELS = {"knowledge", "practical", "public_evidence", "production"}
SKILL_CATEGORIES = {
    "backend",
    "ai_engineering",
    "infrastructure",
    "education_product",
    "frontend",
    "security",
}
EXPERIENCE_CONTEXTS = {"project", "production"}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    verification: str
    disclosure: str


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping without accepting arbitrary Python objects."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot load {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be a mapping")
    return data


def validate_dataset(
    projects_data: dict[str, Any],
    skills_data: dict[str, Any],
    goals_data: dict[str, Any],
) -> list[ValidationIssue]:
    """Return every deterministic contract violation in a Career Radar dataset."""
    issues: list[ValidationIssue] = []
    projects = _collection(projects_data, "projects", issues)
    skills = _collection(skills_data, "skills", issues)
    _schema_version(projects_data, "projects", issues)
    _schema_version(skills_data, "skills", issues)
    _schema_version(goals_data, "career_goals", issues)

    project_ids: set[str] = set()
    project_artifacts: dict[str, dict[str, ArtifactMetadata]] = {}
    project_visibilities: dict[str, str] = {}

    for index, project in enumerate(projects):
        path = f"projects[{index}]"
        if not isinstance(project, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue
        project_id = _identifier(project, path, project_ids, issues)
        _required_text(project, "name", path, issues)
        _required_text(project, "summary", path, issues)
        _https_url(project, "repository_url", path, issues)
        visibility = _enum(
            project, "repository_visibility", REPOSITORY_VISIBILITIES, path, issues
        )
        access = _enum(project, "evidence_access", DISCLOSURE_STATES, path, issues)
        _commit(project, "source_commit", path, issues)
        _date(project, "verified_at", path, issues)

        if visibility == "private" and access == "public":
            issues.append(
                ValidationIssue(
                    f"{path}.evidence_access",
                    "a private repository cannot have public evidence access",
                )
            )

        artifacts_by_path = _validate_artifacts(
            project.get("artifacts"), path, visibility, access, issues
        )
        if project_id:
            project_artifacts[project_id] = artifacts_by_path
            project_visibilities[project_id] = visibility

    skill_ids: set[str] = set()
    for index, skill in enumerate(skills):
        path = f"skills[{index}]"
        if not isinstance(skill, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue
        _identifier(skill, path, skill_ids, issues)
        _required_text(skill, "name", path, issues)
        _enum(skill, "category", SKILL_CATEGORIES, path, issues)
        level = _enum(skill, "level", SKILL_LEVELS, path, issues)
        evidence = skill.get("evidence")
        if not isinstance(evidence, list):
            issues.append(ValidationIssue(f"{path}.evidence", "must be a list"))
            evidence = []

        has_verified = False
        has_verified_public = False
        has_production_context = False
        for evidence_index, item in enumerate(evidence):
            evidence_path = f"{path}.evidence[{evidence_index}]"
            if not isinstance(item, dict):
                issues.append(ValidationIssue(evidence_path, "must be a mapping"))
                continue
            project_id = item.get("project_id")
            if project_id not in project_ids:
                issues.append(
                    ValidationIssue(
                        f"{evidence_path}.project_id", "references an unknown project"
                    )
                )
            context = _enum(
                item, "experience_context", EXPERIENCE_CONTEXTS, evidence_path, issues
            )
            if context == "production":
                _required_text(item, "production_note", evidence_path, issues)

            artifact_refs = item.get("artifacts")
            if not isinstance(artifact_refs, list) or not all(
                isinstance(value, str) and value for value in artifact_refs
            ):
                issues.append(
                    ValidationIssue(
                        f"{evidence_path}.artifacts",
                        "must be a list of non-empty paths",
                    )
                )
                artifact_refs = []

            known_artifacts = project_artifacts.get(project_id, {})
            referenced_metadata: list[ArtifactMetadata] = []
            for artifact_index, artifact_ref in enumerate(artifact_refs):
                metadata = known_artifacts.get(artifact_ref)
                if metadata is None:
                    issues.append(
                        ValidationIssue(
                            f"{evidence_path}.artifacts[{artifact_index}]",
                            "references an unknown project artifact",
                        )
                    )
                else:
                    referenced_metadata.append(metadata)

            verified = any(
                metadata.verification == "verified" for metadata in referenced_metadata
            )
            verified_public = any(
                metadata.verification == "verified"
                and metadata.disclosure == "public"
                for metadata in referenced_metadata
            ) and project_visibilities.get(project_id) == "public"
            has_verified |= verified
            has_verified_public |= verified_public
            has_production_context |= context == "production" and verified

        if level in {"practical", "public_evidence", "production"} and not has_verified:
            issues.append(
                ValidationIssue(
                    f"{path}.level", f"{level} requires at least one verified artifact"
                )
            )
        if level == "public_evidence" and not has_verified_public:
            issues.append(
                ValidationIssue(
                    f"{path}.level",
                    "public_evidence requires a verified public artifact in a public repository",
                )
            )
        if level == "production" and not has_production_context:
            issues.append(
                ValidationIssue(
                    f"{path}.level",
                    "production requires verified evidence with explicit production context",
                )
            )

    _validate_goals(goals_data.get("career_goals"), issues)
    return issues


def _validate_artifacts(
    value: Any,
    project_path: str,
    repository_visibility: Any,
    evidence_access: Any,
    issues: list[ValidationIssue],
) -> dict[str, ArtifactMetadata]:
    if not isinstance(value, list):
        issues.append(ValidationIssue(f"{project_path}.artifacts", "must be a list"))
        return {}
    artifacts: dict[str, ArtifactMetadata] = {}
    access_rank = {"private": 0, "on_request": 1, "public": 2}
    for index, artifact in enumerate(value):
        path = f"{project_path}.artifacts[{index}]"
        if not isinstance(artifact, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue
        artifact_path = artifact.get("path")
        if not _is_safe_relative_path(artifact_path):
            issues.append(
                ValidationIssue(
                    f"{path}.path", "must be a normalized relative POSIX path"
                )
            )
        elif artifact_path in artifacts:
            issues.append(
                ValidationIssue(f"{path}.path", "must be unique within project")
            )
        _required_text(artifact, "kind", path, issues)
        verification = _enum(
            artifact, "verification", VERIFICATION_STATES, path, issues
        )
        disclosure = _enum(artifact, "disclosure", DISCLOSURE_STATES, path, issues)
        if repository_visibility == "private" and disclosure == "public":
            issues.append(
                ValidationIssue(
                    f"{path}.disclosure",
                    "an artifact in a private repository cannot be public",
                )
            )
        if disclosure in access_rank and evidence_access in access_rank:
            if access_rank[disclosure] > access_rank[evidence_access]:
                issues.append(
                    ValidationIssue(
                        f"{path}.disclosure",
                        "cannot be broader than project evidence_access",
                    )
                )
        if isinstance(artifact_path, str) and artifact_path not in artifacts:
            artifacts[artifact_path] = ArtifactMetadata(verification, disclosure)
    return artifacts


def _collection(data: dict[str, Any], key: str, issues: list[ValidationIssue]) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        issues.append(ValidationIssue(key, "must be a list"))
        return []
    return value


def _schema_version(data: dict[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                f"{path}.schema_version", f"must equal {SCHEMA_VERSION}"
            )
        )


def _identifier(
    item: dict[str, Any], path: str, seen: set[str], issues: list[ValidationIssue]
) -> str | None:
    value = item.get("id")
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        issues.append(
            ValidationIssue(
                f"{path}.id", "must be a lowercase kebab-case identifier"
            )
        )
        return None
    if value in seen:
        issues.append(ValidationIssue(f"{path}.id", "must be unique"))
    seen.add(value)
    return value


def _required_text(
    item: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]
) -> None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(f"{path}.{key}", "must be non-empty text"))


def _enum(
    item: dict[str, Any],
    key: str,
    allowed: set[str],
    path: str,
    issues: list[ValidationIssue],
) -> Any:
    value = item.get(key)
    if value not in allowed:
        issues.append(
            ValidationIssue(
                f"{path}.{key}", f"must be one of: {', '.join(sorted(allowed))}"
            )
        )
    return value


def _https_url(
    item: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]
) -> None:
    value = item.get(key)
    parsed = urlparse(value) if isinstance(value, str) else None
    if (
        parsed is None
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        issues.append(
            ValidationIssue(
                f"{path}.{key}", "must be an HTTPS URL without credentials or query data"
            )
        )


def _commit(
    item: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]
) -> None:
    value = item.get(key)
    if not isinstance(value, str) or COMMIT_PATTERN.fullmatch(value) is None:
        issues.append(
            ValidationIssue(f"{path}.{key}", "must be a full lowercase Git commit SHA")
        )


def _date(
    item: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]
) -> None:
    value = item.get(key)
    try:
        date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        value = None
    if not isinstance(value, str) or not value:
        issues.append(ValidationIssue(f"{path}.{key}", "must be an ISO date"))


def _is_safe_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and value == path.as_posix()
        and value not in {".", ""}
    )


def _validate_goals(value: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, dict):
        issues.append(ValidationIssue("career_goals", "must be a mapping"))
        return
    horizon = value.get("horizon_months")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        issues.append(
            ValidationIssue(
                "career_goals.horizon_months", "must be a positive integer"
            )
        )
    roles = value.get("target_roles")
    if not isinstance(roles, list) or not roles:
        issues.append(
            ValidationIssue("career_goals.target_roles", "must be a non-empty list")
        )
        return
    role_ids: set[str] = set()
    for index, role in enumerate(roles):
        path = f"career_goals.target_roles[{index}]"
        if not isinstance(role, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue
        _identifier(role, path, role_ids, issues)
        _required_text(role, "name", path, issues)
        _enum(role, "priority", {"low", "medium", "high"}, path, issues)
