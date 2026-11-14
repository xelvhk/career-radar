"""Read-only verification of evidence artifacts against local Git checkouts."""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class SourceAuditIssue:
    project_id: str
    path: str | None
    message: str


def parse_repository_args(values: Iterable[str]) -> dict[str, Path]:
    """Parse repeated PROJECT_ID=/absolute/path CLI arguments."""
    repositories: dict[str, Path] = {}
    for value in values:
        project_id, separator, raw_path = value.partition("=")
        if not separator or not PROJECT_ID_PATTERN.fullmatch(project_id):
            raise ValueError("repository mapping must be PROJECT_ID=/absolute/path")
        path = Path(raw_path)
        if not path.is_absolute():
            raise ValueError(f"repository path for {project_id} must be absolute")
        if project_id in repositories:
            raise ValueError(f"duplicate repository mapping for {project_id}")
        repositories[project_id] = path
    return repositories


def audit_sources(
    projects_data: dict[str, Any], repositories: dict[str, Path]
) -> list[SourceAuditIssue]:
    """Verify pinned commits, origins, and artifacts without modifying repositories."""
    issues: list[SourceAuditIssue] = []
    projects = projects_data.get("projects")
    if not isinstance(projects, list):
        return [SourceAuditIssue("<dataset>", None, "projects must be a list")]

    known_ids = {
        project.get("id")
        for project in projects
        if isinstance(project, dict) and isinstance(project.get("id"), str)
    }
    for project_id in sorted(repositories.keys() - known_ids):
        issues.append(SourceAuditIssue(project_id, None, "mapping references an unknown project"))

    for project in projects:
        if not isinstance(project, dict):
            continue
        current_project_id = project.get("id")
        if not isinstance(current_project_id, str):
            continue
        repository = repositories.get(current_project_id)
        if repository is None:
            issues.append(
                SourceAuditIssue(current_project_id, None, "repository path was not provided")
            )
            continue
        issues.extend(_audit_project(project, repository))
    return issues


def _audit_project(project: dict[str, Any], repository: Path) -> list[SourceAuditIssue]:
    project_id = str(project.get("id"))
    resolved_repository, issues = _inspect_repository(project_id, repository)
    if resolved_repository is None:
        return issues

    issues.extend(_audit_origin(project_id, resolved_repository, project.get("repository_url")))
    pinned_commit = project.get("source_commit")
    head_available, head_issues = _audit_head(project_id, resolved_repository, pinned_commit)
    issues.extend(head_issues)
    if head_available:
        issues.extend(
            _audit_artifacts(
                project_id,
                resolved_repository,
                pinned_commit,
                project.get("artifacts"),
            )
        )
    return issues


def _inspect_repository(
    project_id: str, repository: Path
) -> tuple[Path | None, list[SourceAuditIssue]]:
    try:
        repository = repository.resolve(strict=True)
    except OSError:
        return None, [SourceAuditIssue(project_id, None, "repository path does not exist")]
    if not repository.is_dir():
        return None, [SourceAuditIssue(project_id, None, "repository path is not a directory")]

    root = _git(repository, "rev-parse", "--show-toplevel")
    if not root.ok:
        return None, [SourceAuditIssue(project_id, None, "path is not a Git repository")]
    if Path(root.stdout).resolve() != repository:
        return repository, [
            SourceAuditIssue(project_id, None, "path must point to the Git repository root")
        ]
    return repository, []


def _audit_origin(
    project_id: str, repository: Path, expected_origin: Any
) -> list[SourceAuditIssue]:
    origin = _git(repository, "remote", "get-url", "origin")
    if not origin.ok:
        return [SourceAuditIssue(project_id, None, "origin remote is missing")]
    if _normalize_repository_url(origin.stdout) != _normalize_repository_url(expected_origin):
        return [SourceAuditIssue(project_id, None, "origin does not match repository_url")]
    return []


def _audit_head(
    project_id: str, repository: Path, pinned_commit: Any
) -> tuple[bool, list[SourceAuditIssue]]:
    head = _git(repository, "rev-parse", "HEAD")
    if not head.ok:
        return False, [SourceAuditIssue(project_id, None, "cannot resolve repository HEAD")]
    if head.stdout != pinned_commit:
        return True, [SourceAuditIssue(project_id, None, "HEAD does not match source_commit")]
    return True, []


def _audit_artifacts(
    project_id: str,
    repository: Path,
    pinned_commit: Any,
    artifacts: Any,
) -> list[SourceAuditIssue]:
    issues: list[SourceAuditIssue] = []
    for artifact_path in _verified_artifact_paths(artifacts):
        issue = _audit_artifact(project_id, repository, pinned_commit, artifact_path)
        if issue is not None:
            issues.append(issue)
    return issues


def _verified_artifact_paths(artifacts: Any) -> Iterable[str]:
    if not isinstance(artifacts, list):
        return
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("verification") != "verified":
            continue
        artifact_path = artifact.get("path")
        if isinstance(artifact_path, str):
            yield artifact_path


def _audit_artifact(
    project_id: str,
    repository: Path,
    pinned_commit: Any,
    artifact_path: str,
) -> SourceAuditIssue | None:
    at_commit = _git(repository, "cat-file", "-e", f"{pinned_commit}:{artifact_path}")
    if not at_commit.ok:
        qualifier = "not tracked" if (repository / artifact_path).exists() else "missing"
        return SourceAuditIssue(
            project_id,
            artifact_path,
            f"artifact is {qualifier} at the pinned commit",
        )
    status = _git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        artifact_path,
    )
    if not status.ok:
        return SourceAuditIssue(project_id, artifact_path, "cannot inspect artifact state")
    if status.stdout:
        return SourceAuditIssue(project_id, artifact_path, "artifact has local modifications")
    return None


@dataclass(frozen=True, slots=True)
class _GitResult:
    returncode: int
    stdout: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _git(repository: Path, *args: str) -> _GitResult:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _GitResult(1, "")
    return _GitResult(result.returncode, result.stdout.strip())


def _normalize_repository_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip().rstrip("/")
    if normalized.startswith("git@") and ":" in normalized:
        host_and_path = normalized[4:]
        host, path = host_and_path.split(":", 1)
        normalized = f"https://{host}/{path}"
    parsed = urlparse(normalized)
    if parsed.scheme == "ssh" and parsed.hostname:
        normalized = f"https://{parsed.hostname}{parsed.path}"
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.casefold()
