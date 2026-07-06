"""Load/save evaluation datasets and run logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

METRICS_ROOT = Path(__file__).resolve().parents[1]
SHARED_RUNS_PATH = METRICS_ROOT / "shared" / "runs.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def load_runs(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or SHARED_RUNS_PATH
    if not path.exists():
        return []
    payload = load_json(path)
    return payload.get("runs", [])


def suite_path(suite: str, filename: str) -> Path:
    return METRICS_ROOT / suite / filename
