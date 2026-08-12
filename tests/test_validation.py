import tempfile
import unittest
from pathlib import Path

from career_radar.validation import load_yaml, validate_dataset


def valid_dataset() -> tuple[dict, dict, dict]:
    projects = {
        "schema_version": 1,
        "projects": [
            {
                "id": "example-project",
                "name": "Example Project",
                "summary": "A verifiable example.",
                "visibility": "public",
                "repository_url": "https://example.test/repository",
                "verification": "verified",
                "artifacts": [
                    {
                        "path": "README.md",
                        "kind": "documentation",
                        "verification": "verified",
                    }
                ],
            }
        ],
    }
    skills = {
        "schema_version": 1,
        "skills": [
            {
                "id": "python",
                "name": "Python",
                "category": "backend",
                "level": "public_evidence",
                "evidence": [
                    {
                        "project_id": "example-project",
                        "verification": "verified",
                        "artifacts": ["README.md"],
                    }
                ],
            }
        ],
    }
    goals = {
        "schema_version": 1,
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
    def test_accepts_a_consistent_verified_dataset(self) -> None:
        projects, skills, goals = valid_dataset()

        issues = validate_dataset(projects, skills, goals)

        self.assertEqual(issues, [])

    def test_rejects_evidence_for_an_unknown_project(self) -> None:
        projects, skills, goals = valid_dataset()
        skills["skills"][0]["evidence"][0]["project_id"] = "missing-project"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].evidence[0].project_id"
                and "unknown project" in issue.message
                for issue in issues
            )
        )

    def test_rejects_public_evidence_level_without_verified_evidence(self) -> None:
        projects, skills, goals = valid_dataset()
        skills["skills"][0]["evidence"][0]["verification"] = "pending"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(
            any(
                issue.path == "skills[0].level"
                and "verified evidence" in issue.message
                for issue in issues
            )
        )

    def test_rejects_non_kebab_case_identifiers(self) -> None:
        projects, skills, goals = valid_dataset()
        projects["projects"][0]["id"] = "Example_Project"

        issues = validate_dataset(projects, skills, goals)

        self.assertTrue(any(issue.path == "projects[0].id" for issue in issues))

    def test_load_yaml_rejects_a_non_mapping_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.yaml"
            source.write_text("- item\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "mapping"):
                load_yaml(source)


if __name__ == "__main__":
    unittest.main()
