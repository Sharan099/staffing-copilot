"""Aggregate all evaluators and print production readiness report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
_SRC = PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from eval.shared.grading import letter_grade
from eval.shared.io import save_json

from eval.task_success.evaluator import evaluate as eval_task_success
from eval.tool_accuracy.evaluator import evaluate as eval_tool_accuracy
from eval.planning.evaluator import evaluate as eval_planning
from eval.reasoning.evaluator import evaluate as eval_reasoning
from eval.grounding.evaluator import evaluate as eval_grounding
from eval.safety.evaluator import evaluate as eval_safety
from eval.hallucination.evaluator import evaluate as eval_hallucination
from eval.permissions.evaluator import evaluate as eval_permissions
from eval.robustness.evaluator import evaluate as eval_robustness
from eval.latency.evaluator import evaluate as eval_latency
from eval.ranking.evaluator import evaluate as eval_ranking
from eval.memory.evaluator import evaluate as eval_memory
from eval.hitl.evaluator import evaluate as eval_hitl
from eval.production.evaluator import evaluate as eval_production
from eval.observability.evaluator import evaluate as eval_observability


EVALUATORS = [
    ("task_success", eval_task_success),
    ("tool_accuracy", eval_tool_accuracy),
    ("planning", eval_planning),
    ("reasoning", eval_reasoning),
    ("grounding", eval_grounding),
    ("safety", eval_safety),
    ("hallucination", eval_hallucination),
    ("permissions", eval_permissions),
    ("robustness", eval_robustness),
    ("latency", eval_latency),
    ("ranking", eval_ranking),
    ("memory", eval_memory),
    ("hitl", eval_hitl),
    ("production", eval_production),
    ("observability", eval_observability),
]


def run_all_evaluations() -> dict:
    results = {}
    for name, fn in EVALUATORS:
        results[name] = fn().to_dict()
    return results


def overall_score(results: dict) -> float:
    weights = {
        "task_success": 0.12,
        "tool_accuracy": 0.08,
        "planning": 0.08,
        "reasoning": 0.06,
        "grounding": 0.08,
        "safety": 0.10,
        "hallucination": 0.08,
        "permissions": 0.08,
        "robustness": 0.08,
        "latency": 0.06,
        "ranking": 0.10,
        "memory": 0.04,
        "hitl": 0.04,
        "production": 0.06,
        "observability": 0.04,
    }
    total = 0.0
    for key, weight in weights.items():
        total += results[key]["score"] * weight
    return round(total, 2)


def production_ready(results: dict, overall: float) -> bool:
    critical = ["task_success", "safety", "permissions", "production"]
    if overall < 80:
        return False
    return all(results[k]["passed"] for k in critical)


def print_report(results: dict) -> None:
    overall = overall_score(results)
    grade = letter_grade(overall)
    ready = production_ready(results, overall)

    task = results["task_success"]["details"]
    rank = results["ranking"]["details"].get("metrics", {})
    safety = results["safety"]["details"]
    latency = results["latency"]["details"]
    hall = results["hallucination"]["details"]

    print("====================================")
    print("AI AGENT PRODUCTION READINESS REPORT")
    print("====================================\n")
    print(f"Task Success\n{task.get('task_success_rate', 0)*100:.0f}%\n")
    print(f"Tool Accuracy\n{results['tool_accuracy']['score']:.0f}%\n")
    print(f"Planning\n{results['planning']['score']:.0f}%\n")
    print(f"Groundedness\n{results['grounding']['score']:.0f}%\n")
    print(f"Hallucination\n{hall.get('hallucination_rate', 0)*100:.0f}%\n")
    print(f"Safety\n{results['safety']['score']:.0f}%\n")
    print(f"Latency\n{latency.get('end_to_end_latency_ms', 0)/1000:.1f} sec\n")
    print(f"Ranking NDCG\n{rank.get('ndcg_at_5', 0):.2f}\n")
    print(f"MRR\n{rank.get('mrr', 0):.2f}\n")
    print(f"Permission Accuracy\n{results['permissions']['score']:.0f}%\n")
    print(f"Reliability\n{results['production']['details'].get('reliability', 0)*100:.1f}%\n")
    print(f"Overall Grade\n\n{grade}\n")
    print("Production Ready\n" if ready else "NOT Production Ready\n")
    print("====================================")

    print("\nDetailed suite results:")
    for name, res in results.items():
        status = "PASS" if res["passed"] else "FAIL"
        print(f"  [{status}] {name}: {res['score']:.1f} — {res['reason']}")


def main() -> None:
    results = run_all_evaluations()
    overall = overall_score(results)
    payload = {
        "overall_score": overall,
        "overall_grade": letter_grade(overall),
        "production_ready": production_ready(results, overall),
        "suites": results,
    }
    save_json(ROOT / "final_report.json", payload)
    print_report(results)
    print(f"\nJSON report saved to {ROOT / 'final_report.json'}")


if __name__ == "__main__":
    main()
