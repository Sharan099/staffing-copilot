import unittest

from data.db import get_staffing_conn
from scoring.judgment import (
    compute_judgment_flags,
    enrich_ranked_candidates,
    format_flags_for_prompt,
)


class TestJudgment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_staffing_conn().close()

    def test_burnout_flag_on_back_to_back_projects(self):
        projects = [
            {"client_name": "BMW", "domain": "automotive", "start_date": "2022-01-01", "end_date": "2022-06-01"},
            {"client_name": "Bosch", "domain": "manufacturing", "start_date": "2022-06-01", "end_date": "2022-12-01"},
            {"client_name": "SAP", "domain": "software", "start_date": "2022-12-01", "end_date": "2023-06-01"},
        ]
        flags = compute_judgment_flags(projects, {}, "automotive", "Mercedes")
        ids = {f["id"] for f in flags}
        self.assertIn("burnout_risk", ids)

    def test_repeat_domain_pattern_flag(self):
        projects = [
            {"client_name": "BMW", "domain": "automotive", "start_date": "2022-01-01", "end_date": "2022-06-01"},
            {"client_name": "Bosch", "domain": "automotive", "start_date": "2022-07-01", "end_date": "2022-12-01"},
        ]
        flags = compute_judgment_flags(projects, {}, "automotive", "Mercedes")
        ids = {f["id"] for f in flags}
        self.assertIn("repeat_domain_pattern", ids)

    def test_prior_rejection_flag(self):
        memory = {
            "rejected_for_client": True,
            "summary": "Previously rejected for BMW",
            "similar_domain_approvals": 0,
        }
        flags = compute_judgment_flags([], memory, "automotive", "BMW")
        ids = {f["id"] for f in flags}
        self.assertIn("turned_down_before", ids)

    def test_format_flags_for_prompt(self):
        flags = [{"severity": "high", "label": "Burnout risk", "detail": "No gap between projects"}]
        text = format_flags_for_prompt(flags)
        self.assertIn("Burnout risk", text)
        self.assertIn("HIGH", text)

    def test_enrich_ranked_candidates_adds_fields(self):
        ranked = [{
            "employee_id": 7,
            "name": "Test User",
            "total_score": 80,
            "score_breakdown": [],
        }]
        enriched = enrich_ranked_candidates(ranked, "BMW automotive Python engineer")[0]
        self.assertIn("judgment_flags", enriched)
        self.assertIn("staffing_memory", enriched)
        self.assertIn("project_history", enriched)
        self.assertIsInstance(enriched["judgment_flags"], list)


if __name__ == "__main__":
    unittest.main()
