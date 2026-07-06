import unittest

from scoring.german_fluency import german_fluency_raw, level_rank, normalize_german_level
from scoring.scorer import ScoreCriteria, score_candidate
from scoring.weights import ScoringWeights


class TestGermanFluency(unittest.TestCase):
    def test_normalize_aliases(self):
        self.assertEqual(normalize_german_level("business"), "B2")
        self.assertEqual(normalize_german_level("native"), "C2")
        self.assertEqual(normalize_german_level("basic"), "A2")

    def test_meets_requirement_full_score(self):
        raw, detail = german_fluency_raw("C1", "B2", client_facing=True)
        self.assertEqual(raw, 100.0)
        self.assertIn("meets required", detail)

    def test_gap_partial_score(self):
        raw, _ = german_fluency_raw("A2", "B2", client_facing=True)
        self.assertGreater(raw, 0)
        self.assertLess(raw, 100)

    def test_not_client_facing_neutral(self):
        raw, detail = german_fluency_raw("none", "B2", client_facing=False)
        self.assertEqual(raw, 100.0)
        self.assertIn("not required", detail)

    def test_scorer_includes_language_when_client_facing(self):
        criteria = ScoreCriteria(
            required_skills=["Python"],
            client_facing=True,
            required_german_level="B2",
            scoring_weights=ScoringWeights(language=15, skills=35, availability=20, experience=15, utilization=15).normalized(),
        )
        scored = score_candidate({
            "employee_id": 1,
            "name": "Test",
            "skills": ["Python"],
            "german_fluency": "C1",
            "years_experience": 5,
            "location": "Berlin",
            "available_from": "2026-01-01",
            "status": "bench",
            "current_utilization_pct": 0,
        }, criteria)
        lang = next(r for r in scored["score_breakdown"] if r["rule"] == "language")
        self.assertEqual(lang["raw_score"], 100.0)
        self.assertGreater(lang["weighted_points"], 0)
        self.assertEqual(scored["german_fluency"], "C1")

    def test_level_rank_ordering(self):
        self.assertGreater(level_rank("C2"), level_rank("B2"))
        self.assertGreater(level_rank("B2"), level_rank("A1"))


if __name__ == "__main__":
    unittest.main()
