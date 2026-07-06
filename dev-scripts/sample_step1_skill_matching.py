"""Sample output for Step 1: partial skill matching."""
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scoring.scorer import ScoreCriteria, rank_candidates
from tools.tools import fetch_candidates_for_ranking

criteria = ScoreCriteria(
    required_skills=["Python", "LangGraph", "RAG"],
    location="Berlin",
    needed_by="2026-06-01",
    skill_weights={"Python": 2, "LangGraph": 2, "RAG": 1},
)

candidates = fetch_candidates_for_ranking(criteria.required_skills, criteria.location)
ranked = rank_candidates(candidates, criteria, top_n=5)

print(f"Pool size (partial matchers included): {len(candidates)}")
print(f"Top {len(ranked)} ranked:\n")

for c in ranked:
    sm = c["skill_match"]
    print(f"#{c['rank']} {c['name']} — {c['total_score']} pts total")
    print(f"  Skill fit: {sm['match_percent']}% ({sm['points_earned']}/{sm['points_possible']} pts)")
    print(f"  Matched:    {sm['matched_skills'] or '—'}")
    adj = sm["adjacent_credits"]
    adj_str = ", ".join(f"{a['required']} via {a['via']} (+{a['points']})" for a in adj) if adj else "—"
    print(f"  Adjacent:   {adj_str}")
    print(f"  Missing:    {sm['missing_skills'] or '—'}")
    print()

print("--- JSON sample (top candidate skill_match) ---")
if ranked:
    print(json.dumps(ranked[0]["skill_match"], indent=2))
