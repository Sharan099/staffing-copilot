import unittest

from scoring.scorer import ScoreCriteria, rank_candidates, score_candidate


class TestScorer(unittest.TestCase):
    def _candidate(self, **overrides):
        base = {
            "employee_id": 1,
            "name": "Anna Test",
            "title": "AI Engineer",
            "department": "Vehicle Motion",
            "location": "Berlin",
            "years_experience": 7,
            "current_utilization_pct": 20,
            "available_from": "2026-08-01",
            "status": "bench",
            "skills": ["Python", "LLM", "RAG"],
        }
        base.update(overrides)
        return base

    def test_score_is_reproducible(self):
        criteria = ScoreCriteria(
            required_skills=["Python", "LLM"],
            location="Berlin",
            needed_by="2026-10-01",
        )
        candidate = self._candidate()
        first = score_candidate(candidate, criteria)
        second = score_candidate(candidate, criteria)
        self.assertEqual(first["total_score"], second["total_score"])
        self.assertEqual(first["score_breakdown"], second["score_breakdown"])

    def test_breakdown_sums_to_total(self):
        criteria = ScoreCriteria(required_skills=["Python", "LLM", "RAG"])
        scored = score_candidate(self._candidate(), criteria)
        breakdown_total = round(sum(item["weighted_points"] for item in scored["score_breakdown"]), 1)
        self.assertEqual(scored["total_score"], breakdown_total)

    def test_location_mismatch_scores_zero_for_location_rule(self):
        criteria = ScoreCriteria(required_skills=["Python"], location="Munich")
        scored = score_candidate(self._candidate(location="Berlin"), criteria)
        location_rule = next(
            item for item in scored["score_breakdown"] if item["rule"] == "location"
        )
        self.assertEqual(location_rule["raw_score"], 0.0)
        self.assertEqual(location_rule["weighted_points"], 0.0)

    def test_rank_returns_top_five_with_ranks(self):
        criteria = ScoreCriteria(required_skills=["Python"])
        candidates = [
            self._candidate(employee_id=1, years_experience=3, status="billable", current_utilization_pct=80),
            self._candidate(employee_id=2, years_experience=10, status="bench", current_utilization_pct=0),
            self._candidate(employee_id=3, years_experience=6, status="bench", current_utilization_pct=10),
            self._candidate(employee_id=4, years_experience=8, status="bench", current_utilization_pct=0),
            self._candidate(employee_id=5, years_experience=5, status="billable", current_utilization_pct=60),
            self._candidate(employee_id=6, years_experience=12, status="bench", current_utilization_pct=0),
        ]
        ranked = rank_candidates(candidates, criteria, top_n=5)
        self.assertEqual(len(ranked), 5)
        self.assertEqual([item["rank"] for item in ranked], [1, 2, 3, 4, 5])
        self.assertGreater(ranked[0]["total_score"], ranked[-1]["total_score"])


if __name__ == "__main__":
    unittest.main()
