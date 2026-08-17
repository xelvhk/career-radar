import unittest

from career_radar.matching_config import load_matching_config
from career_radar.validation import load_yaml
from career_radar.vacancy import parse_vacancy

from tests.test_repository_data import ROOT


class VacancyParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_matching_config(
            ROOT / "matching.yaml",
            load_yaml(ROOT / "skills.yaml"),
            load_yaml(ROOT / "career_goals.yaml"),
        )

    def test_extracts_required_and_preferred_skills_from_english_text(self) -> None:
        vacancy = parse_vacancy(
            (ROOT / "tests/fixtures/vacancy_ai_backend.txt").read_text(),
            self.config,
        )

        importance = {item.skill_id: item.importance for item in vacancy.requirements}
        self.assertEqual(vacancy.title, "AI Backend Engineer")
        self.assertEqual(importance["python"], "required")
        self.assertEqual(importance["fastapi"], "required")
        self.assertEqual(importance["rag"], "required")
        self.assertEqual(importance["qdrant"], "required")
        self.assertEqual(importance["aws"], "required")
        self.assertEqual(importance["kubernetes"], "preferred")
        self.assertTrue(vacancy.is_remote)
        self.assertIn("document_ai", vacancy.domains)
        self.assertIn("ai-backend-engineer", vacancy.target_roles)

    def test_supports_russian_aliases_and_negation(self) -> None:
        vacancy = parse_vacancy(
            (ROOT / "tests/fixtures/vacancy_rag_ru.txt").read_text(),
            self.config,
        )

        skill_ids = {item.skill_id for item in vacancy.requirements}
        self.assertIn("hybrid-search", skill_ids)
        self.assertIn("qdrant", skill_ids)
        self.assertIn("kubernetes", skill_ids)
        self.assertNotIn("aws", skill_ids)
        self.assertIn("rag-engineer", vacancy.target_roles)

    def test_aliases_use_token_boundaries_and_are_deduplicated(self) -> None:
        vacancy = parse_vacancy(
            "Backend Engineer\nRequirements:\n- Python, pythonic design, and Python\n",
            self.config,
        )

        python_items = [item for item in vacancy.requirements if item.skill_id == "python"]
        self.assertEqual(len(python_items), 1)

        pythonic_only = parse_vacancy(
            "Backend Engineer\nRequirements:\n- Pythonic design\n", self.config
        )
        self.assertNotIn(
            "python", {item.skill_id for item in pythonic_only.requirements}
        )

    def test_rejects_empty_and_oversized_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            parse_vacancy("  \n", self.config)
        with self.assertRaisesRegex(ValueError, "200000"):
            parse_vacancy("x" * 200_001, self.config)

    def test_keeps_unmapped_requirement_lines_visible(self) -> None:
        vacancy = parse_vacancy(
            "AI Engineer\nRequirements:\n- Five years of distributed systems experience\n",
            self.config,
        )

        self.assertEqual(
            vacancy.unmapped_requirement_lines,
            ("Five years of distributed systems experience",),
        )

    def test_does_not_treat_benefits_as_requirements(self) -> None:
        vacancy = parse_vacancy(
            "AI Engineer\nBenefits include Docker training and Python conference tickets.\n",
            self.config,
        )

        self.assertEqual(vacancy.requirements, ())

    def test_role_aliases_are_matched_against_title_only(self) -> None:
        vacancy = parse_vacancy(
            "Generic Platform Role\nRequirements:\n- Work with an AI Backend Engineer\n",
            self.config,
        )

        self.assertEqual(vacancy.target_roles, ())

    def test_ignores_leading_blank_lines_before_the_title(self) -> None:
        vacancy = parse_vacancy(
            "\n\nAI Backend Engineer\nRequirements:\n- Python\n",
            self.config,
        )

        self.assertEqual(vacancy.title, "AI Backend Engineer")
        self.assertEqual(
            tuple(item.skill_id for item in vacancy.requirements),
            ("python",),
        )

    def test_calibration_titles_and_natural_work_modes_are_recognized(self) -> None:
        expected = {
            "01-lead-ai-ml.txt": (("ai-backend-engineer",), False),
            "02-ml-platform.txt": ((), True),
            "03-backend-platform.txt": (("ai-backend-engineer",), True),
            "04-ai-architect.txt": (("ai-solutions-engineer",), True),
            "05-senior-fullstack.txt": ((), True),
            "06-ml-devops.txt": ((), False),
            "07-junior-python.txt": ((), True),
            "08-python-llm-rag.txt": (("rag-engineer",), True),
        }

        for filename, (roles, is_remote) in expected.items():
            with self.subTest(filename=filename):
                vacancy = parse_vacancy(
                    (ROOT / "tests/fixtures/calibration" / filename).read_text(),
                    self.config,
                )
                self.assertEqual(vacancy.target_roles, roles)
                self.assertEqual(vacancy.is_remote, is_remote)
                self.assertTrue(vacancy.requirements)

    def test_extracts_mandatory_experience_and_location_constraints(self) -> None:
        vacancy = parse_vacancy(
            "AI Architect\n"
            "Candidate must be outside Russia and Belarus.\n"
            "Requirements:\n"
            "- 5+ years building production applications with Python.\n",
            self.config,
        )

        self.assertEqual(vacancy.minimum_years_experience, 5)
        self.assertTrue(vacancy.requires_production_experience)
        self.assertCountEqual(
            vacancy.location_constraints,
            ("outside:RU", "outside:BY"),
        )

    def test_does_not_treat_company_geography_as_candidate_constraint(self) -> None:
        vacancy = parse_vacancy(
            "AI Architect\n"
            "The company operates outside Russia and Belarus.\n"
            "Requirements:\n"
            "- Python.\n",
            self.config,
        )

        self.assertEqual(vacancy.location_constraints, ())


if __name__ == "__main__":
    unittest.main()
