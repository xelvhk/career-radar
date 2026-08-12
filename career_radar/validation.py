"""Deterministic validation for Career Radar's versioned YAML sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERIFICATION_STATES = {"pending", "verified", "private"}
SKILL_LEVELS = {"knowledge", "practical", "public_evidence", "production"}
SKILL_CATEGORIES = {
    "backend",
    "ai_engineering",
    "infrastructure",
    "education_product",
}


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    path: str
    message: str


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
    project_artifacts: dict[str, set[str]] = {}
    for index, project in enumerate(projects):
        path = f"projects[{index}]"
        if not isinstance(project, dict):
            issues.append(ValidationIssue(path, "must be a mapping"))
            continue
        project_id = _identifier(project, path, project_ids, issues)
        _required_text(project, "name", path, issues)
        _enum(project, "visibility", {"public", "private", "unknown"}, path, issues)
        _enum(project, "verification", VERIFICATION_STATES, path, issues)
        artifact_paths: set[str] = set()
        artifacts = project.get("artifacts")
        if not isinstance(artifacts, list):
            issues.append(ValidationIssue(f"{path}.artifacts", "must be a list"))
        else:
            for artifact_index, artifact in enumerate(artifacts):
                artifact_path = f"{path}.artifacts[{artifact_index}]"
                if not isinstance(artifact, dict):
                    issues.append(ValidationIssue(artifact_path, "must be a mapping"))
                    continue
                value = artifact.get("path")
                if not isinstance(value, str) or not value.strip():
                    issues.append(ValidationIssue(f"{artifact_path}.path", "must be non-empty text"))
                elif value in artifact_paths:
                    issues.append(ValidationIssue(f"{artifact_path}.path", "must be unique within project"))
                else:
                    artifact_paths.add(value)
                _required_text(artifact, "kind", artifact_path, issues)
                _enum(artifact, "verification", VERIFICATION_STATES, artifact_path, issues)
        if project_id:
            project_artifacts[project_id] = artifact_paths

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
        has_verified_evidence = False
        if not isinstance(evidence, list):
            issues.append(ValidationIssue(f"{path}.evidence", "must be a list"))
            evidence = []
        for evidence_index, item in enumerate(evidence):
            evidence_path = f"{path}.evidence[{evidence_index}]"
            if not isinstance(item, dict):
                issues.append(ValidationIssue(evidence_path, "must be a mapping"))
                continue
            project_id = item.get("project_id")
            if project_id not in project_ids:
                issues.append(ValidationIssue(f"{evidence_path}.project_id", "references an unknown project"))
            state = _enum(item, "verification", VERIFICATION_STATES, evidence_path, issues)
            artifact_refs = item.get("artifacts")
            if not isinstance(artifact_refs, list) or not all(
                isinstance(value, str) and value for value in artifact_refs
            ):
                issues.append(ValidationIssue(f"{evidence_path}.artifacts", "must be a list of non-empty paths"))
                artifact_refs = []
            known_artifacts = project_artifacts.get(project_id, set())
            for artifact_index, artifact_ref in enumerate(artifact_refs):
                if artifact_ref not in known_artifacts:
                    issues.append(
                        ValidationIssue(
                            f"{evidence_path}.artifacts[{artifact_index}]",
                            "references an unknown project artifact",
                        )
                    )
            has_verified_evidence |= state == "verified" and bool(artifact_refs)
        if level in {"public_evidence", "production"} and not has_verified_evidence:
            issues.append(ValidationIssue(f"{path}.level", f"{level} requires verified evidence with an artifact"))

    _validate_goals(goals_data.get("career_goals"), issues)
    return issues


def _collection(data: dict[str, Any], key: str, issues: list[ValidationIssue]) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        issues.append(ValidationIssue(key, "must be a list"))
        return []
    return value


def _schema_version(data: dict[str, Any], path: str, issues: list[ValidationIssue]) -> None:
    if data.get("schema_version") != 1:
        issues.append(ValidationIssue(f"{path}.schema_version", "must equal 1"))


def _identifier(item: dict[str, Any], path: str, seen: set[str], issues: list[ValidationIssue]) -> str | None:
    value = item.get("id")
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        issues.append(ValidationIssue(f"{path}.id", "must be a lowercase kebab-case identifier"))
        return None
    if value in seen:
        issues.append(ValidationIssue(f"{path}.id", "must be unique"))
    seen.add(value)
    return value


def _required_text(item: dict[str, Any], key: str, path: str, issues: list[ValidationIssue]) -> None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(f"{path}.{key}", "must be non-empty text"))


def _enum(
    item: dict[str, Any], key: str, allowed: set[str], path: str, issues: list[ValidationIssue]
) -> Any:
    value = item.get(key)
    if value not in allowed:
        issues.append(ValidationIssue(f"{path}.{key}", f"must be one of: {', '.join(sorted(allowed))}"))
    return value


def _validate_goals(value: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, dict):
        issues.append(ValidationIssue("career_goals", "must be a mapping"))
        return
    horizon = value.get("horizon_months")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        issues.append(ValidationIssue("career_goals.horizon_months", "must be a positive integer"))
    roles = value.get("target_roles")
    if not isinstance(roles, list) or not roles:
        issues.append(ValidationIssue("career_goals.target_roles", "must be a non-empty list"))
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
