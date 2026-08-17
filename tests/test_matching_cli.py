import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_repository_data import ROOT


class MatchingCliTests(unittest.TestCase):
    def test_json_cli_returns_stable_machine_readable_report(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/match_vacancy.py",
                "tests/fixtures/vacancy_ai_backend.txt",
                "--format",
                "json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["reportVersion"], 1)
        self.assertEqual(payload["vacancy"]["title"], "AI Backend Engineer")
        self.assertIn(payload["recommendation"], {"APPLY", "REVIEW", "SKIP"})
        self.assertIn("dimensions", payload)
        self.assertIn("requirementMappings", payload)
        self.assertIn("minimumYearsExperience", payload["vacancy"])
        self.assertIn("requiresProductionExperience", payload["vacancy"])
        self.assertIn("locationConstraints", payload["vacancy"])
        self.assertIn("unverifiedConstraints", payload)

    def test_markdown_cli_explains_recommendation(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/match_vacancy.py",
                "tests/fixtures/vacancy_rag_ru.txt",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Vacancy Match", result.stdout)
        self.assertIn("Recommendation:", result.stdout)
        self.assertIn("Evidence mapping", result.stdout)

    def test_markdown_output_escapes_untrusted_vacancy_text(self) -> None:
        from career_radar.matching import analyze_vacancy
        from career_radar.matching_config import load_matching_config
        from career_radar.reporting import report_to_markdown
        from career_radar.validation import load_yaml

        projects = load_yaml(ROOT / "projects.yaml")
        skills = load_yaml(ROOT / "skills.yaml")
        goals = load_yaml(ROOT / "career_goals.yaml")
        config = load_matching_config(ROOT / "matching.yaml", skills, goals)
        report = analyze_vacancy(
            "AI \x1b[31m[click](https://example.test) | Engineer\nRequirements:\n- Python\n",
            projects_data=projects,
            skills_data=skills,
            goals_data=goals,
            config=config,
        )

        output = report_to_markdown(report)

        self.assertIn(r"\[click\]\(https://example.test\)", output)
        self.assertIn(r"\| Engineer", output)
        self.assertNotIn("\x1b", output)

    def test_cli_rejects_non_utf8_input_without_echoing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vacancy = Path(directory) / "vacancy.txt"
            vacancy.write_bytes(b"private-content-\xff")

            result = subprocess.run(
                [sys.executable, "scripts/match_vacancy.py", str(vacancy)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("must be UTF-8", result.stderr)
        self.assertNotIn("private-content", result.stderr)


if __name__ == "__main__":
    unittest.main()
