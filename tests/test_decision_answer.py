import unittest

from scripts.build_decision_answer import build


class DecisionAnswerTests(unittest.TestCase):
    def test_answer_covers_every_site_and_identifies_actions(self):
        result = build()
        self.assertEqual({row["site_id"] for row in result["site_results"]}, {"joliet", "ohare", "kenosha"})
        self.assertTrue(all(row["base_gap_hours"] > 0 for row in result["site_results"]))
        self.assertEqual(result["actions"]["affordable_base_case"]["scheduled_workers"], 6)
        self.assertEqual(result["actions"]["lowest_risk_tested"]["scheduled_workers"], 10)
        self.assertEqual(result["actions"]["lowest_risk_tested"]["stress_cases_passed"], 36)

    def test_qwi_uses_latest_complete_quarter(self):
        context = build()["labor_market_context"]
        self.assertEqual(context["latest_api_quarter"], "2025-Q4")
        self.assertEqual(context["latest_complete_quarter"], "2025-Q3")


if __name__ == "__main__":
    unittest.main()
