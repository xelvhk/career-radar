import unittest
import subprocess
import sys
from pathlib import Path

from career_radar.validation import load_yaml, validate_dataset


ROOT = Path(__file__).resolve().parents[1]


class RepositoryDataTests(unittest.TestCase):
    def test_checked_in_career_data_is_valid(self) -> None:
        projects = load_yaml(ROOT / "projects.yaml")
        skills = load_yaml(ROOT / "skills.yaml")
        goals = load_yaml(ROOT / "career_goals.yaml")

        issues = validate_dataset(projects, skills, goals)

        self.assertEqual(issues, [])

    def test_verified_catalog_has_expected_visibility_and_size(self) -> None:
        projects = load_yaml(ROOT / "projects.yaml")["projects"]
        skills = load_yaml(ROOT / "skills.yaml")["skills"]
        projects_by_id = {project["id"]: project for project in projects}

        self.assertEqual(len(projects), 3)
        self.assertEqual(sum(len(project["artifacts"]) for project in projects), 46)
        self.assertEqual(projects_by_id["contractops-ai"]["evidence_access"], "on_request")
        self.assertEqual(projects_by_id["onboardica"]["evidence_access"], "on_request")
        self.assertEqual(projects_by_id["vasya-ai"]["evidence_access"], "public")
        self.assertNotIn("production", {skill["level"] for skill in skills})

    def test_validation_script_runs_from_the_repository_root(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/validate_data.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Career data is valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
