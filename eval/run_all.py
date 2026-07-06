"""Run full Staffing Copilot evaluation pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent


def main() -> int:
    steps = [
        [sys.executable, "-m", "pip", "install", "pandas", "-q"],
        [sys.executable, str(ROOT / "harness" / "generate_runs.py")],
        [sys.executable, str(ROOT / "report.py")],
    ]
    for cmd in steps:
        print(f"\n>>> {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
        if result.returncode != 0:
            return result.returncode
    # Run evaluator unit tests
    print("\n>>> Running evaluator tests")
    test_cmd = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "eval",
        "-p",
        "evaluator.py",
        "-q",
    ]
    return subprocess.run(test_cmd, cwd=str(PROJECT_ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
