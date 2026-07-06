"""Sample output for Step 3: German fluency + Betriebsrat audit."""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.db import get_staffing_conn
from scoring.scorer import ScoreCriteria, rank_candidates, score_candidate
from scoring.weights import ScoringWeights
from tools.tools import fetch_candidates_for_ranking

# Ensure migration ran
get_staffing_conn().close()

skills = ["Python", "LLM"]
candidates = fetch_candidates_for_ranking(skills)[:30]

client_facing = ScoreCriteria(
    required_skills=skills,
    client_facing=True,
    required_german_level="B2",
    scoring_weights=ScoringWeights(
        skills=35, availability=20, experience=15, location=10, utilization=10, language=10,
    ).normalized(),
)

internal = ScoreCriteria(
    required_skills=skills,
    client_facing=False,
    scoring_weights=ScoringWeights(
        skills=40, availability=25, experience=15, location=10, utilization=10, language=0,
    ).normalized(),
)

print("=== Client-facing role (German B2+ required, language weighted) ===\n")
ranked_cf = rank_candidates(candidates, client_facing, top_n=3)
for c in ranked_cf:
    lang = next(r for r in c["score_breakdown"] if r["rule"] == "language")
    print(f"#{c['rank']} {c['name']} — {c['total_score']} pts | German: {c['german_fluency']}")
    print(f"   Language: raw={lang['raw_score']} × {lang['weight_percent']}% = {lang['weighted_points']} pts")
    print(f"   {lang['detail']}\n")

print("=== Same pool, internal role (German not scored) ===\n")
ranked_int = rank_candidates(candidates, internal, top_n=3)
for c in ranked_int:
    has_lang = any(r["rule"] == "language" for r in c["score_breakdown"])
    print(f"#{c['rank']} {c['name']} — {c['total_score']} pts | German: {c['german_fluency']} | language in breakdown: {has_lang}")

print("\n=== Betriebsrat audit trail (reports.db) ===")
print("On approve, POST /approve includes:")
print('  "works_council_notification": "yes" | "no" | "unsure"')
print("Stored in reports.works_council_notification and included in PDF + success screen.")
