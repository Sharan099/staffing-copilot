"""Sample output for Step 2: adjustable per-search weighting."""
import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scoring.scorer import ScoreCriteria, rank_candidates, score_candidate
from scoring.weights import ScoringWeights
from tools.tools import fetch_candidates_for_ranking

# Same candidates, two different manager weight profiles
skills = ["Python", "LangGraph", "RAG"]
candidates = fetch_candidates_for_ranking(skills)[:20]  # top of pool for demo

profiles = {
    "skill_focused": ScoringWeights(skills=60, availability=15, experience=15, utilization=10),
    "availability_focused": ScoringWeights(skills=15, availability=60, experience=15, utilization=10),
}

for name, weights in profiles.items():
    criteria = ScoreCriteria(
        required_skills=skills,
        needed_by="2026-06-01",
        scoring_weights=weights.normalized(),
    )
    ranked = rank_candidates(candidates, criteria, top_n=3)
    print(f"\n=== Profile: {name} ===")
    print(f"Weights: {criteria.scoring_weights.as_dict()}")
    for c in ranked:
        print(f"\n#{c['rank']} {c['name']} — {c['total_score']} total")
        for row in c["score_breakdown"]:
            print(
                f"  {row['rule']:14} raw={row['raw_score']:5.1f} "
                f"× weight {row['weight_percent']:4.1f}% "
                f"= {row['weighted_points']:5.1f} pts"
            )

# Head-to-head: why A beats B under skill-focused weights
print("\n=== Why Priya beats Marco (skill-focused) ===")
criteria = ScoreCriteria(
    required_skills=skills,
    needed_by="2026-06-01",
    scoring_weights=profiles["skill_focused"].normalized(),
)
ranked = rank_candidates(candidates, criteria, top_n=2)
if len(ranked) >= 2:
    a, b = ranked[0], ranked[1]
    print(f"{a['name']} ({a['total_score']}) vs {b['name']} ({b['total_score']})")
    for rule in ["skills", "availability", "experience", "utilization"]:
        ra = next(r for r in a["score_breakdown"] if r["rule"] == rule)
        rb = next(r for r in b["score_breakdown"] if r["rule"] == rule)
        diff = ra["weighted_points"] - rb["weighted_points"]
        if abs(diff) >= 0.5:
            print(f"  {rule}: {a['name']} +{diff:.1f} pts ({ra['weighted_points']} vs {rb['weighted_points']})")

print("\n--- JSON breakdown sample ---")
if ranked:
    print(json.dumps(ranked[0]["score_breakdown"], indent=2))
