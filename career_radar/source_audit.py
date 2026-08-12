"""Read-only verification of evidence artifacts against local Git checkouts."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
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
        issues.append(
            SourceAuditIssue(project_id, None, "mapping references an unknown project")
        )

    for project in projects:
        if not isinstance(project, dict):
            continue
        project_id = project.get("id")
        if not isinstance(project_id, str):
            continue
        repository = repositories.get(project_id)
        if repository is None:
            issues.append(
                SourceAuditIssue(project_id, None, "repository path was not provided")
            )
            continue
        issues.extend(_audit_project(project, repository))
    return issues


def _audit_project(project: dict[str, Any], repository: Path) -> list[SourceAuditIssue]:
    project_id = str(project.get("id"))
    issues: list[SourceAuditIssue] = []
    try:
        repository = repository.resolve(strict=True)
    except OSError:
        return [SourceAuditIssue(project_id, None, "repository path does not exist")]
    if not repository.is_dir():
        return [SourceAuditIssue(project_id, None, "repository path is not a directory")]

    root = _git(repository, "rev-parse", "--show-toplevel")
    if not root.ok:
        return [SourceAuditIssue(project_id, None, "path is not a Git repository")]
    if Path(root.stdout).resolve() != repository:
        issues.append(
            SourceAuditIssue(project_id, None, "path must point to the Git repository root")
        )

    origin = _git(repository, "remote", "get-url", "origin")
    expected_origin = project.get("repository_url")
    if not origin.ok:
        issues.append(SourceAuditIssue(project_id, None, "origin remote is missing"))
    elif _normalize_repository_url(origin.stdout) != _normalize_repository_url(
        expected_origin
    ):
        issues.append(
            SourceAuditIssue(project_id, None, "origin does not match repository_url")
        )

    head = _git(repository, "rev-parse", "HEAD")
    pinned_commit = project.get("source_commit")
    if not head.ok:
        issues.append(SourceAuditIssue(project_id, None, "cannot resolve repository HEAD"))
        return issues
    if head.stdout != pinned_commit:
        issues.append(
            SourceAuditIssue(project_id, None, "HEAD does not match source_commit")
        )

    artifacts = project.get("artifacts")
    if not isinstance(artifacts, list):
        return issues
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("verification") != "verified":
            continue
        artifact_path = artifact.get("path")
        if not isinstance(artifact_path, str):
            continue
        at_commit = _git(repository, "cat-file", "-e", f"{pinned_commit}:{artifact_path}")
        if not at_commit.ok:
            qualifier = "not tracked" if (repository / artifact_path).exists() else "missing"
            issues.append(
                SourceAuditIssue(
                    project_id,
                    artifact_path,
                    f"artifact is {qualifier} at the pinned commit",
                )
            )
            continue
        status = _git(
            repository,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            artifact_path,
        )
        if not status.ok:
            issues.append(
                SourceAuditIssue(project_id, artifact_path, "cannot inspect artifact state")
            )
        elif status.stdout:
            issues.append(
                SourceAuditIssue(project_id, artifact_path, "artifact has local modifications")
            )
    return issues


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
