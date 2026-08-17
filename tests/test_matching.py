import copy
import unittest

from career_radar.matching import analyze_vacancy
from career_radar.matching_config import load_matching_config, validate_matching_config
from career_radar.validation import load_yaml

from tests.test_repository_data import ROOT


class VacancyMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projects = load_yaml(ROOT / "projects.yaml")
        cls.skills = load_yaml(ROOT / "skills.yaml")
        cls.goals = load_yaml(ROOT / "career_goals.yaml")
        cls.config = load_matching_config(
            ROOT / "matching.yaml", cls.skills, cls.goals
        )

    def analyze(self, text: str):
        return analyze_vacancy(
            text,
            projects_data=self.projects,
            skills_data=self.skills,
            goals_data=self.goals,
            config=self.config,
        )

    def test_maps_public_on_request_and_gap_evidence(self) -> None:
        report = self.analyze(
            "AI Backend Engineer\nRequirements:\n- Python\n- RAG\n- AWS\n"
        )

        mappings = {item.skill_id: item for item in report.requirement_mappings}
        self.assertEqual(mappings["python"].evidence_status, "public")
        self.assertEqual(mappings["rag"].evidence_status, "on_request")
        self.assertEqual(mappings["aws"].evidence_status, "gap")
        self.assertTrue(mappings["python"].artifacts)
        self.assertTrue(
            all(not artifact.startswith("/") for artifact in mappings["python"].artifacts)
        )
        self.assertIn("aws", report.required_gaps)
        self.assertEqual(report.recommendation, "REVIEW")

    def test_high_evidence_match_is_apply(self) -> None:
        report = self.analyze(
            "AI Backend Engineer\nRequirements:\n- Python\n- FastAPI\n"
            "Remote document processing role\n"
        )

        self.assertGreaterEqual(report.overall_score, 75)
        self.assertGreaterEqual(report.confidence, 60)
        self.assertEqual(report.required_gaps, ())
        self.assertEqual(report.recommendation, "APPLY")

    def test_low_match_with_sufficient_confidence_is_skip(self) -> None:
        report = self.analyze(
            "AI Backend Engineer\nRequirements:\n- AWS\n- Kubernetes\n"
            "Remote document processing role\n"
        )

        self.assertLess(report.overall_score, 50)
        self.assertGreaterEqual(report.confidence, 60)
        self.assertEqual(report.recommendation, "SKIP")

    def test_low_confidence_never_returns_apply_or_skip(self) -> None:
        report = self.analyze("Unknown Role\nWe build useful products.\n")

        self.assertLess(report.confidence, 60)
        self.assertEqual(report.recommendation, "REVIEW")

    def test_unknown_dimensions_are_explicit_and_excluded_from_score(self) -> None:
        report = self.analyze("AI Backend Engineer\nRequirements:\n- Python\n")
        dimensions = {item.name: item for item in report.dimensions}

        self.assertEqual(dimensions["seniority"].status, "unknown")
        self.assertIsNone(dimensions["seniority"].score)
        self.assertEqual(dimensions["salary"].status, "unknown")
        self.assertEqual(dimensions["location"].status, "unknown")

    def test_results_are_deterministic(self) -> None:
        text = "AI Backend Engineer\nRequirements:\n- Python\n- FastAPI\n"

        self.assertEqual(self.analyze(text), self.analyze(text))

    def test_configuration_rejects_unknown_skills_and_invalid_weights(self) -> None:
        data = load_yaml(ROOT / "matching.yaml")
        data = copy.deepcopy(data)
        data["skill_aliases"]["invented-skill"] = ["invented"]
        data["weights"]["technical"] = 31

        errors = validate_matching_config(data, self.skills, self.goals)

        self.assertTrue(any("unknown IDs" in error for error in errors))
        self.assertIn("weights must total 100", errors)

    def test_private_evidence_paths_are_not_exposed_in_the_report(self) -> None:
        projects = copy.deepcopy(self.projects)
        skills = copy.deepcopy(self.skills)
        python = next(item for item in skills["skills"] if item["id"] == "python")
        python["level"] = "practical"
        python["evidence"] = [python["evidence"][0]]
        contractops = next(
            item for item in projects["projects"] if item["id"] == "contractops-ai"
        )
        contractops["evidence_access"] = "private"
        for artifact in contractops["artifacts"]:
            artifact["disclosure"] = "private"

        report = analyze_vacancy(
            "AI Backend Engineer\nRequirements:\n- Python\n",
            projects_data=projects,
            skills_data=skills,
            goals_data=self.goals,
            config=self.config,
        )

        mapping = report.requirement_mappings[0]
        self.assertEqual(mapping.evidence_status, "private")
        self.assertEqual(mapping.projects, ())
        self.assertEqual(mapping.artifacts, ())

    def test_unverified_mandatory_experience_constraints_block_apply(self) -> None:
        report = self.analyze(
            "AI Backend Engineer\n"
            "Remote document processing role\n"
            "Requirements:\n"
            "- Python and FastAPI\n"
            "- 3+ years of production experience\n"
        )

        self.assertGreaterEqual(report.overall_score, 75)
        self.assertIn("minimum_years_experience:3", report.unverified_constraints)
        self.assertIn("production_experience", report.unverified_constraints)
        self.assertEqual(report.recommendation, "REVIEW")

    def test_unverified_constraint_never_causes_automatic_skip(self) -> None:
        report = self.analyze(
            "Unrelated Role\n"
            "Requirements:\n"
            "- 10+ years of production experience\n"
        )

        self.assertLess(report.overall_score, self.config.skip_score)
        self.assertTrue(report.unverified_constraints)
        self.assertEqual(report.recommendation, "REVIEW")

    def test_explicit_profile_data_can_verify_mandatory_constraints(self) -> None:
        goals = copy.deepcopy(self.goals)
        goals["career_goals"]["experience_profile"] = {
            "commercial_years": 5,
            "verified_production_experience": True,
        }
        goals["career_goals"]["work_preferences"]["current_country_codes"] = [
            "US"
        ]

        report = analyze_vacancy(
            "AI Backend Engineer\n"
            "Remote document processing role; candidate must be outside Russia.\n"
            "Requirements:\n"
            "- Python and FastAPI\n"
            "- 3+ years of production experience\n",
            projects_data=self.projects,
            skills_data=self.skills,
            goals_data=goals,
            config=self.config,
        )

        self.assertEqual(report.unverified_constraints, ())
        self.assertEqual(report.recommendation, "APPLY")

    def test_calibration_fixtures_never_apply_with_unresolved_constraints_or_gaps(self) -> None:
        fixture_directory = ROOT / "tests/fixtures/calibration"

        for fixture in sorted(fixture_directory.glob("*.txt")):
            with self.subTest(fixture=fixture.name):
                report = self.analyze(fixture.read_text())
                self.assertTrue(report.requirement_mappings)
                if report.required_gaps or report.unverified_constraints:
                    self.assertNotEqual(report.recommendation, "APPLY")


if __name__ == "__main__":
    unittest.main()
