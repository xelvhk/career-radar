import copy
import tempfile
import unittest
from pathlib import Path

from career_radar.validation import load_yaml, validate_dataset


def valid_dataset(
    *, repository_visibility: str = "public", disclosure: str = "public"
) -> tuple[dict, dict, dict]:
    projects = {
        "schema_version": 2,
        "projects": [
            {
                "id": "example-project",
                "name": "Example Project",
                "summary": "A verifiable example.",
                "repository_url": "https://github.com/example/example-project",
                "repository_visibility": repository_visibility,
                "evidence_access": disclosure,
                "source_commit": "a" * 40,
                "verified_at": "2026-08-12",
                "artifacts": [
                    {
                        "path": "README.md",
                        "kind": "documentation",
                        "verification": "verified",
                        "disclosure": disclosure,
                    }
                ],
            }
        ],
    }
    level = "public_evidence" if disclosure == "public" else "practical"
    skills = {
        "schema_version": 2,
        "skills": [
            {
                "id": "python",
                "name": "Python",
                "category": "backend",
                "level": level,
                "evidence": [
                    {
                        "project_id": "example-project",
                        "artifacts": ["README.md"],
                        "experience_context": "project",
                    }
                ],
            }
        ],
    }
    goals = {
        "schema_version": 2,
        "career_goals": {
            "horizon_months": 12,
            "target_roles": [
                {"id": "ai-engineer", "name": "AI Engineer", "priority": "high"}
            ],
            "preferred_domains": [],
            "work_preferences": {
                "remote": "preferred",
                "locations": [],
                "employment_types": ["full_time"],
                "languages": ["en"],
            },
            "compensation": {"currencies": [], "minimum": None, "target": None},
            "strategy": {
                "primary_metric": "evidence_coverage",
                "require_verified_claims_for_applications": True,
                "optimize_for": ["role_fit"],
            },
        },
    }
    return projects, skills, goals


class ValidationTests(unittest.TestCase):
    def test_accepts_verified_public_evidence_in_a_public_repository(self) -> None:
        projects, skills, goals = valid_dataset()

        self.assertEqual(validate_dataset(projects, skills, goals), [])

    def test_accepts_verified_on_request_evidence_as_practical(self) -> None:
        projects, skills, goals = valid_dataset(
            repository_visibility="private", disclosure="on_request"
        )

        self.assertEqual(validate_dataset(projects, skills, goals), [])

    def test_rejects_public_artifact_in_a_private_repository(self) -> None:
        projects, skills, goals = valid_dataset(
            repository_visibility="private", disclosure="on_request"
        )
        projects["projects"][0]["artifacts"][0]["disclosure"] = "public"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "projects[0].artifacts[0].disclosure"
                and "private repository" in issue.message
                for issue in issues
            )
        )

    def test_rejects_public_evidence_level_with_only_on_request_artifacts(self) -> None:
        projects, skills, goals = valid_dataset(
            repository_visibility="private", disclosure="on_request"
        )
        skills["skills"][0]["level"] = "public_evidence"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].level"
                and "verified public artifact" in issue.message
                for issue in issues
            )
        )

    def test_rejects_practical_level_without_verified_artifacts(self) -> None:
        projects, skills, goals = valid_dataset()
        projects["projects"][0]["artifacts"][0]["verification"] = "pending"
        skills["skills"][0]["level"] = "practical"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].level"
                and "verified artifact" in issue.message
                for issue in issues
            )
        )

    def test_rejects_production_level_without_explicit_production_context(self) -> None:
        projects, skills, goals = valid_dataset()
        skills["skills"][0]["level"] = "production"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].level"
                and "production context" in issue.message
                for issue in issues
            )
        )

    def test_rejects_evidence_for_an_unknown_project_artifact(self) -> None:
        projects, skills, goals = valid_dataset()
        skills["skills"][0]["evidence"][0]["artifacts"] = ["missing.py"]

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].evidence[0].artifacts[0]"
                and "unknown project artifact" in issue.message
                for issue in issues
            )
        )

    def test_rejects_invalid_source_commit(self) -> None:
        projects, skills, goals = valid_dataset()
        projects["projects"][0]["source_commit"] = "abc123"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(any(issue.path == "projects[0].source_commit" for issue in issues))

    def test_rejects_absolute_or_parent_artifact_paths(self) -> None:
        for invalid_path in ("/tmp/README.md", "../README.md"):
            with self.subTest(path=invalid_path):
                projects, skills, goals = valid_dataset()
                projects["projects"][0]["artifacts"][0]["path"] = invalid_path
                skills["skills"][0]["evidence"][0]["artifacts"] = [invalid_path]

                issues = validate_dataset(projects, skills, goals)

                self.assertTrue(
                    any(issue.path == "projects[0].artifacts[0].path" for issue in issues)
                )

    def test_rejects_schema_version_one(self) -> None:
        projects, skills, goals = valid_dataset()
        projects["schema_version"] = 1

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(any(issue.path == "projects.schema_version" for issue in issues))

    def test_does_not_mutate_input_data(self) -> None:
        projects, skills, goals = valid_dataset()
        original = copy.deepcopy((projects, skills, goals))

        validate_dataset(projects, skills, goals)

        self.assertEqual((projects, skills, goals), original)

    def test_load_yaml_rejects_a_non_mapping_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.yaml"
            source.write_text("- item\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mapping"):
                load_yaml(source)


if __name__ == "__main__":
    unittest.main()
