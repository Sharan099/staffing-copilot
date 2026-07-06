"""Sample output for Step 5: staffing memory from reports.db (read-only)."""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.db import get_reports_conn, get_staffing_conn
from data.staffing_memory import get_staffing_memory, log_rejection
from scoring.judgment import enrich_ranked_candidates
from scoring.scorer import ScoreCriteria, rank_candidates
from tools.tools import fetch_candidates_for_ranking

get_staffing_conn().close()
get_reports_conn().close()

client_message = "BMW automotive Python consultant needed ASAP"
criteria = ScoreCriteria(required_skills=["Python"], location=None)
candidates = fetch_candidates_for_ranking(criteria.required_skills, criteria.location)
ranked = rank_candidates(candidates, criteria, top_n=1)
top = ranked[0]

# Simulate a prior rejection for demo
log_rejection(
    top["employee_id"],
    top["name"],
    "demo_manager",
    client_message,
    "Client preferred more automotive OEM experience",
)

enriched = enrich_ranked_candidates(ranked, client_message)[0]
memory = enriched["staffing_memory"]

print(f"Candidate: {top['name']} (#{top['employee_id']})")
print(f"Domain: {memory.get('domain')} | Client: {memory.get('client_name')}")
print(f"Summary: {memory.get('summary') or '(none)'}")
print("\nMemory items:")
for item in memory.get("items") or []:
    print(f"  [{item['type']}] {item['label']}")
    print(f"    {item['detail'][:120]}")

print("\nMemory is read-only — candidates are NOT auto-excluded.")
print("Managers see 'Previously rejected for this client' on the card and in LLM summary.")
