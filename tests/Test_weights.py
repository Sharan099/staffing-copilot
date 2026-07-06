import unittest

from scoring.scorer import ScoreCriteria, score_candidate
from scoring.weights import DEFAULT_SCORING_WEIGHTS, ScoringWeights, scoring_weights_from_dict


class TestScoringWeights(unittest.TestCase):
    def test_normalization_sums_to_100(self):
        weights = ScoringWeights(skills=50, availability=50, experience=0, location=0, utilization=0).normalized()
        total = sum(weights.as_dict().values())
        self.assertAlmostEqual(total, 100.0, places=1)

    def test_availability_heavy_changes_ranking(self):
        candidate_a = {
            "employee_id": 1,
            "name": "High Skills",
            "skills": ["Python", "LLM", "RAG"],
            "years_experience": 3,
            "location": "Berlin",
            "available_from": "2027-01-01",
            "status": "billable",
            "current_utilization_pct": 90,
        }
        candidate_b = {
            "employee_id": 2,
            "name": "Available Soon",
            "skills": ["Python"],
            "years_experience": 3,
            "location": "Berlin",
            "available_from": "2026-02-01",
            "status": "bench",
            "current_utilization_pct": 0,
        }
        criteria = ["Python", "LLM", "RAG"]
        skill_heavy = ScoreCriteria(
            required_skills=criteria,
            needed_by="2026-06-01",
            scoring_weights=ScoringWeights(skills=70, availability=10, experience=10, utilization=10).normalized(),
        )
        avail_heavy = ScoreCriteria(
            required_skills=criteria,
            needed_by="2026-06-01",
            scoring_weights=ScoringWeights(skills=10, availability=70, experience=10, utilization=10).normalized(),
        )
        score_a_skills = score_candidate(candidate_a, skill_heavy)["total_score"]
        score_b_skills = score_candidate(candidate_b, skill_heavy)["total_score"]
        score_a_avail = score_candidate(candidate_a, avail_heavy)["total_score"]
        score_b_avail = score_candidate(candidate_b, avail_heavy)["total_score"]

        self.assertGreater(score_a_skills, score_b_skills)
        self.assertGreater(score_b_avail, score_a_avail)

    def test_breakdown_shows_raw_weight_weighted(self):
        criteria = ScoreCriteria(required_skills=["Python"], scoring_weights=DEFAULT_SCORING_WEIGHTS)
        scored = score_candidate({
            "employee_id": 1,
            "name": "T",
            "skills": ["Python"],
            "years_experience": 5,
            "location": "Berlin",
            "available_from": "2026-01-01",
            "status": "bench",
            "current_utilization_pct": 0,
        }, criteria)
        for row in scored["score_breakdown"]:
            self.assertIn("raw_score", row)
            self.assertIn("weight_percent", row)
            self.assertIn("weighted_points", row)
        total = round(sum(r["weighted_points"] for r in scored["score_breakdown"]), 1)
        self.assertEqual(scored["total_score"], total)

    def test_scoring_weights_from_dict(self):
        weights = scoring_weights_from_dict({"skills": 80, "availability": 20})
        total = sum(weights.as_dict().values())
        self.assertAlmostEqual(total, 100.0, places=1)


if __name__ == "__main__":
    unittest.main()
