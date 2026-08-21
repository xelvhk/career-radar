import json
import subprocess
import sys
import unittest

from tests.test_repository_data import ROOT


class SearchQueryCliTests(unittest.TestCase):
    def test_json_cli_exposes_stable_source_neutral_query_plans(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/list_search_queries.py", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["queryPlanVersion"], 1)
        self.assertEqual(payload["profileCount"], 4)
        self.assertGreaterEqual(payload["queryCount"], 8)
        first = payload["queries"][0]
        self.assertEqual(first["profileId"], "ai-backend")
        self.assertIn("targetRoleId", first)
        self.assertIn("titlePhrase", first)
        self.assertIn("skillIds", first)
        self.assertIn("skillTerms", first)
        self.assertIn("excludeTerms", first)
        self.assertNotIn("queryString", first)

    def test_markdown_cli_lists_profiles_without_network_access(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/list_search_queries.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Saved Search Queries", result.stdout)
        self.assertIn("AI Backend", result.stdout)
        self.assertIn("RAG / LLM Engineer", result.stdout)


if __name__ == "__main__":
    unittest.main()
