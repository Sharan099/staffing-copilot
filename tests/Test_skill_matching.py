import unittest

from scoring.skill_matching import (
    ADJACENT_CREDIT_FRACTION,
    CORE_SKILL_WEIGHT,
    NICE_TO_HAVE_WEIGHT,
    POINTS_PER_WEIGHT_UNIT,
    compute_skill_match,
    expand_skills_for_pool,
)
from scoring.scorer import ScoreCriteria, score_candidate
from tools.tools import fetch_candidates_for_ranking


class TestSkillMatching(unittest.TestCase):
    def test_direct_match_full_credit(self):
        result = compute_skill_match(
            ["Python", "LLM", "RAG"],
            ["Python", "LLM"],
        )
        self.assertEqual(result.matched_skills, ["Python", "LLM"])
        self.assertEqual(result.missing_skills, [])
        self.assertEqual(result.adjacent_credits, [])
        self.assertEqual(result.match_percent, 100.0)
        expected = 2 * CORE_SKILL_WEIGHT * POINTS_PER_WEIGHT_UNIT
        self.assertEqual(result.points_earned, expected)

    def test_partial_match_with_missing(self):
        result = compute_skill_match(
            ["Python"],
            ["Python", "LLM", "RAG"],
        )
        self.assertEqual(result.matched_skills, ["Python"])
        self.assertEqual(set(result.missing_skills), {"LLM", "RAG"})
        self.assertLess(result.match_percent, 100.0)

    def test_adjacent_credit_for_langgraph_via_rag(self):
        result = compute_skill_match(
            ["Python", "RAG"],
            ["Python", "LangGraph"],
        )
        self.assertEqual(result.matched_skills, ["Python"])
        self.assertEqual(len(result.adjacent_credits), 1)
        self.assertEqual(result.adjacent_credits[0].required, "LangGraph")
        self.assertEqual(result.adjacent_credits[0].via, "RAG")
        partial = CORE_SKILL_WEIGHT * POINTS_PER_WEIGHT_UNIT * ADJACENT_CREDIT_FRACTION
        self.assertEqual(result.adjacent_credits[0].points, partial)

    def test_nice_to_have_weight(self):
        result = compute_skill_match(
            ["Python"],
            ["Python", "Docker"],
            skill_weights={"Python": CORE_SKILL_WEIGHT, "Docker": NICE_TO_HAVE_WEIGHT},
        )
        self.assertEqual(result.matched_skills, ["Python"])
        self.assertIn("Docker", result.missing_skills)
        max_possible = CORE_SKILL_WEIGHT * POINTS_PER_WEIGHT_UNIT + NICE_TO_HAVE_WEIGHT * POINTS_PER_WEIGHT_UNIT
        self.assertEqual(result.points_possible, max_possible)

    def test_expand_pool_includes_adjacent(self):
        pool = expand_skills_for_pool(["LangGraph"])
        self.assertIn("LangGraph", pool)
        self.assertIn("RAG", pool)
        self.assertIn("LLM", pool)

    def test_fetch_includes_partial_matchers(self):
        strict_count = fetch_candidates_for_ranking(["Python", "LLM", "RAG", "LangGraph"])
        partial_count = fetch_candidates_for_ranking(["Python", "LLM"])
        self.assertGreater(len(partial_count), 0)
        self.assertGreaterEqual(len(partial_count), len(strict_count))

    def test_scored_candidate_includes_skill_match_dict(self):
        candidate = {
            "employee_id": 1,
            "name": "Test",
            "skills": ["Python", "RAG"],
            "years_experience": 5,
            "location": "Berlin",
            "available_from": "2026-01-01",
            "status": "bench",
            "current_utilization_pct": 0,
        }
        criteria = ScoreCriteria(required_skills=["Python", "LangGraph"])
        scored = score_candidate(candidate, criteria)
        self.assertIn("skill_match", scored)
        self.assertIn("matched_skills", scored["skill_match"])
        self.assertIn("missing_skills", scored["skill_match"])
        self.assertIn("adjacent_credits", scored["skill_match"])
        skill_rule = next(r for r in scored["score_breakdown"] if r["rule"] == "skills")
        self.assertIn("skill_match", skill_rule)


if __name__ == "__main__":
    unittest.main()
