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

    def test_profile_cli_resolves_constraints_without_exposing_profile_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "career_profile.local.yaml"
            profile.write_text(
                "schema_version: 1\n"
                "profile:\n"
                "  commercial_years: 5\n"
                "  confirmed_production_experience: true\n"
                "  current_country_code: US\n"
                "  target_seniority: []\n",
                encoding="utf-8",
            )
            vacancy = Path(directory) / "vacancy.txt"
            vacancy.write_text(
                "AI Backend Engineer\n"
                "Remote; candidate must be outside Russia.\n"
                "Requirements:\n"
                "- Python and FastAPI\n"
                "- 3+ years of production experience\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/match_vacancy.py",
                    str(vacancy),
                    "--profile",
                    str(profile),
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
        self.assertEqual(payload["recommendation"], "APPLY")
        self.assertEqual(payload["unverifiedConstraints"], [])
        self.assertNotIn("US", result.stdout)

    def test_cli_rejects_invalid_profile_without_echoing_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "career_profile.local.yaml"
            profile.write_bytes(b"private-profile-value-\xff")

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/match_vacancy.py",
                    "tests/fixtures/vacancy_ai_backend.txt",
                    "--profile",
                    str(profile),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("local profile file must be UTF-8", result.stderr)
        self.assertNotIn("private-profile-value", result.stderr)

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
