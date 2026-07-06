"""Sample output for Step 4: judgment-layer flags in explanations."""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.db import get_staffing_conn
from scoring.judgment import enrich_ranked_candidates, format_flags_for_prompt
from scoring.scorer import ScoreCriteria, rank_candidates
from tools.tools import fetch_candidates_for_ranking

get_staffing_conn().close()

client_message = "Senior Python engineer for BMW automotive project in Munich"
criteria = ScoreCriteria(required_skills=["Python", "LLM"], location="Munich")
candidates = fetch_candidates_for_ranking(criteria.required_skills, criteria.location)
ranked = rank_candidates(candidates, criteria, top_n=3)
enriched = enrich_ranked_candidates(ranked, client_message)

print(f"Request: {client_message}\n")
for c in enriched:
    print(f"#{c['rank']} {c['name']} — {c['total_score']} pts")
    print(f"  Projects: {len(c.get('project_history', []))} on record")
    flags = c.get("judgment_flags") or []
    if flags:
        print("  Judgment flags:")
        text = format_flags_for_prompt(flags).replace("\u2192", "->")
        print("  " + text.replace("\n", "\n  "))
    else:
        print("  Judgment flags: none")
    memory = c.get("staffing_memory") or {}
    if memory.get("summary"):
        print(f"  Memory: {memory['summary']}")
    print()

print("These flags are passed into generate_search_summary / generate_fit_summary prompts")
print("so LLM explanations surface operational judgment, not just scores.")
