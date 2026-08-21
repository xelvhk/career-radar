import copy
import unittest

from career_radar.validation import load_yaml
from career_radar.search_profiles import (
    compile_search_queries,
    parse_search_profiles,
    validate_search_profiles,
)

from tests.test_repository_data import ROOT


class SearchProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skills = load_yaml(ROOT / "skills.yaml")
        cls.goals = load_yaml(ROOT / "career_goals.yaml")
        cls.matching = load_yaml(ROOT / "matching.yaml")

    def test_checked_in_profiles_compile_to_evidence_backed_queries(self) -> None:
        data = load_yaml(ROOT / "search_profiles.yaml")
        profiles = parse_search_profiles(data, self.skills, self.goals, self.matching)
        queries = compile_search_queries(profiles, self.matching)

        self.assertEqual(len(profiles), 4)
        self.assertGreaterEqual(len(queries), 8)
        self.assertEqual(
            tuple(profile.id for profile in profiles),
            ("ai-backend", "rag-llm", "python-fastapi", "document-ai"),
        )
        self.assertTrue(all(query.skill_terms for query in queries))
        self.assertTrue(all(query.exclude_terms for query in queries))
        self.assertEqual(queries, compile_search_queries(profiles, self.matching))

    def test_rejects_knowledge_only_skill_as_search_strength(self) -> None:
        data = copy.deepcopy(load_yaml(ROOT / "search_profiles.yaml"))
        data["search_profiles"][0]["variants"][0]["skill_ids"].append("aws")

        errors = validate_search_profiles(data, self.skills, self.goals, self.matching)

        self.assertTrue(
            any("aws" in error and "verified evidence" in error for error in errors)
        )

    def test_rejects_unknown_roles_skills_and_duplicate_profile_ids(self) -> None:
        data = copy.deepcopy(load_yaml(ROOT / "search_profiles.yaml"))
        data["search_profiles"][1]["id"] = data["search_profiles"][0]["id"]
        data["search_profiles"][0]["target_role_id"] = "unknown-role"
        data["search_profiles"][0]["variants"][0]["skill_ids"] = ["unknown-skill"]

        errors = validate_search_profiles(data, self.skills, self.goals, self.matching)

        self.assertTrue(any("duplicate profile id" in error for error in errors))
        self.assertTrue(any("unknown target role" in error for error in errors))
        self.assertTrue(any("unknown skill" in error for error in errors))

    def test_rejects_duplicate_variants_and_untrimmed_terms(self) -> None:
        data = copy.deepcopy(load_yaml(ROOT / "search_profiles.yaml"))
        first = data["search_profiles"][0]
        first["variants"].append(copy.deepcopy(first["variants"][0]))
        first["exclude_terms"][0] = " php "

        errors = validate_search_profiles(data, self.skills, self.goals, self.matching)

        self.assertTrue(any("duplicate query variant" in error for error in errors))
        self.assertTrue(any("exclude_terms" in error for error in errors))

    def test_malformed_dependency_data_returns_errors_instead_of_crashing(self) -> None:
        data = load_yaml(ROOT / "search_profiles.yaml")

        errors = validate_search_profiles(
            data,
            {"skills": None},
            {"career_goals": None},
            {"skill_aliases": None},
        )

        self.assertTrue(any("unknown target role" in error for error in errors))
        self.assertTrue(any("unknown skill" in error for error in errors))

if __name__ == "__main__":
    unittest.main()
