import copy
import tempfile
import unittest
from pathlib import Path

from career_radar.matching import analyze_vacancy
from career_radar.matching_config import load_matching_config
from career_radar.validation import load_yaml
from tests.test_repository_data import ROOT


class LocalProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projects = load_yaml(ROOT / "projects.yaml")
        cls.skills = load_yaml(ROOT / "skills.yaml")
        cls.goals = load_yaml(ROOT / "career_goals.yaml")
        cls.config = load_matching_config(ROOT / "matching.yaml", cls.skills, cls.goals)

    def test_valid_profile_overlays_only_explicit_match_inputs(self) -> None:
        from career_radar.local_profile import apply_local_profile, load_local_profile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "career_profile.local.yaml"
            path.write_text(
                "schema_version: 1\n"
                "profile:\n"
                "  commercial_years: 5\n"
                "  confirmed_production_experience: true\n"
                "  current_country_code: US\n"
                "  target_seniority: [middle, senior]\n",
                encoding="utf-8",
            )
            profile = load_local_profile(path)

        merged = apply_local_profile(self.goals, profile)
        self.assertEqual(self.goals["career_goals"].get("experience_profile"), None)
        self.assertEqual(
            merged["career_goals"]["experience_profile"],
            {"commercial_years": 5, "verified_production_experience": True},
        )
        self.assertEqual(
            merged["career_goals"]["work_preferences"]["current_country_codes"],
            ["US"],
        )
        self.assertEqual(merged["career_goals"]["target_seniority"], ["middle", "senior"])

        report = analyze_vacancy(
            "AI Backend Engineer\n"
            "Remote; candidate must be outside Russia.\n"
            "Requirements:\n"
            "- Python and FastAPI\n"
            "- 3+ years of production experience\n",
            projects_data=self.projects,
            skills_data=self.skills,
            goals_data=merged,
            config=self.config,
        )
        self.assertEqual(report.unverified_constraints, ())
        self.assertEqual(report.recommendation, "APPLY")

    def test_empty_example_profile_preserves_goals(self) -> None:
        from career_radar.local_profile import apply_local_profile, load_local_profile

        profile = load_local_profile(ROOT / "career_profile.local.example.yaml")

        merged = apply_local_profile(self.goals, profile)

        self.assertEqual(merged, self.goals)
        self.assertIsNot(merged, self.goals)

    def test_partial_profile_preserves_existing_explicit_inputs(self) -> None:
        from career_radar.local_profile import LocalProfile, apply_local_profile

        goals = copy.deepcopy(self.goals)
        goals["career_goals"]["experience_profile"] = {"verified_production_experience": True}
        profile = LocalProfile(
            commercial_years=3,
            confirmed_production_experience=None,
            current_country_code=None,
            target_seniority=(),
        )

        merged = apply_local_profile(goals, profile)

        self.assertEqual(
            merged["career_goals"]["experience_profile"],
            {"commercial_years": 3, "verified_production_experience": True},
        )

    def test_rejects_unknown_or_invalid_profile_values(self) -> None:
        from career_radar.local_profile import load_local_profile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "career_profile.local.yaml"
            path.write_text(
                "schema_version: 1\n"
                "profile:\n"
                "  commercial_years: true\n"
                "  confirmed_production_experience: null\n"
                "  current_country_code: usa\n"
                "  target_seniority: [principal]\n"
                "  employer: private\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "commercial_years"):
                load_local_profile(path)

    def test_validation_reports_structure_and_value_errors_in_stable_order(self) -> None:
        from career_radar.local_profile import validate_local_profile

        self.assertEqual(validate_local_profile([]), ["root must be a mapping"])
        self.assertEqual(
            validate_local_profile({"schema_version": 2, "profile": []}),
            ["schema_version must equal 1", "profile must be a mapping"],
        )

        errors = validate_local_profile(
            {
                "schema_version": 1,
                "profile": {
                    "commercial_years": True,
                    "confirmed_production_experience": "yes",
                    "current_country_code": "usa",
                    "target_seniority": ["senior", "senior"],
                    "private_note": "must not be exposed",
                },
            }
        )

        self.assertEqual(
            errors,
            [
                "profile contains unsupported fields",
                "profile.commercial_years must be an integer from 0 to 60 or null",
                "profile.confirmed_production_experience must be true, false, or null",
                "profile.current_country_code must be an ISO alpha-2 code or null",
                "profile.target_seniority must not contain duplicates",
            ],
        )
        self.assertNotIn("private_note", "; ".join(errors))

    def test_rejects_non_utf8_and_oversized_files_without_echoing_content(self) -> None:
        from career_radar.local_profile import load_local_profile

        with tempfile.TemporaryDirectory() as directory:
            non_utf8 = Path(directory) / "non-utf8.yaml"
            non_utf8.write_bytes(b"private-value-\xff")
            with self.assertRaisesRegex(ValueError, "must be UTF-8") as error:
                load_local_profile(non_utf8)
            self.assertNotIn("private-value", str(error.exception))

            oversized = Path(directory) / "oversized.yaml"
            oversized.write_bytes(b"x" * 64_001)
            with self.assertRaisesRegex(ValueError, "too large"):
                load_local_profile(oversized)


if __name__ == "__main__":
    unittest.main()
