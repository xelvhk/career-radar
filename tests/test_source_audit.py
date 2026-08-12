import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from career_radar.source_audit import audit_sources, parse_repository_args
from tests.test_validation import valid_dataset


def git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class SourceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name) / "example-project"
        self.repository.mkdir()
        git(self.repository, "init", "-q")
        git(self.repository, "config", "user.name", "Career Radar Tests")
        git(self.repository, "config", "user.email", "career-radar@example.test")
        git(
            self.repository,
            "remote",
            "add",
            "origin",
            "git@github.com:example/example-project.git",
        )
        (self.repository / "README.md").write_text("evidence\n", encoding="utf-8")
        git(self.repository, "add", "README.md")
        git(self.repository, "commit", "-q", "-m", "test evidence")
        self.commit = git(self.repository, "rev-parse", "HEAD")
        self.projects = valid_dataset()[0]
        self.projects["projects"][0]["source_commit"] = self.commit

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_accepts_a_clean_repository_at_the_pinned_commit(self) -> None:
        issues = audit_sources(
            self.projects, {"example-project": self.repository}
        )

        self.assertEqual(issues, [])

    def test_rejects_an_artifact_missing_from_the_pinned_commit(self) -> None:
        projects = copy.deepcopy(self.projects)
        projects["projects"][0]["artifacts"][0]["path"] = "missing.py"

        issues = audit_sources(projects, {"example-project": self.repository})

        self.assertTrue(
            any(
                issue.path == "missing.py" and "pinned commit" in issue.message
                for issue in issues
            )
        )

    def test_rejects_a_modified_artifact(self) -> None:
        (self.repository / "README.md").write_text("changed\n", encoding="utf-8")

        issues = audit_sources(
            self.projects, {"example-project": self.repository}
        )

        self.assertTrue(
            any(
                issue.path == "README.md" and "local modifications" in issue.message
                for issue in issues
            )
        )

    def test_rejects_an_untracked_artifact(self) -> None:
        projects = copy.deepcopy(self.projects)
        projects["projects"][0]["artifacts"][0]["path"] = "new.py"
        (self.repository / "new.py").write_text("print('new')\n", encoding="utf-8")

        issues = audit_sources(projects, {"example-project": self.repository})

        self.assertTrue(
            any(
                issue.path == "new.py" and "not tracked" in issue.message
                for issue in issues
            )
        )

    def test_rejects_a_different_head_commit(self) -> None:
        (self.repository / "SECOND.md").write_text("second\n", encoding="utf-8")
        git(self.repository, "add", "SECOND.md")
        git(self.repository, "commit", "-q", "-m", "second commit")

        issues = audit_sources(
            self.projects, {"example-project": self.repository}
        )

        self.assertTrue(any("HEAD does not match" in issue.message for issue in issues))

    def test_rejects_a_mismatched_origin(self) -> None:
        git(
            self.repository,
            "remote",
            "set-url",
            "origin",
            "https://github.com/example/different-project.git",
        )

        issues = audit_sources(
            self.projects, {"example-project": self.repository}
        )

        self.assertTrue(any("origin does not match" in issue.message for issue in issues))

    def test_requires_a_path_mapping_for_each_project(self) -> None:
        issues = audit_sources(self.projects, {})

        self.assertTrue(any("repository path was not provided" in issue.message for issue in issues))

    def test_parse_repository_args_rejects_duplicates_and_relative_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "absolute"):
            parse_repository_args(["example-project=relative/path"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_repository_args(
                [
                    f"example-project={self.repository}",
                    f"example-project={self.repository}",
                ]
            )


if __name__ == "__main__":
    unittest.main()
