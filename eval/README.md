# Staffing Copilot Agent Evaluation Framework

Run the full evaluation:

```powershell
cd H:\staffing-copilot
.\.venv\Scripts\pip.exe install pandas
.\.venv\Scripts\python.exe eval\run_all.py
```

Or step by step:

```powershell
.\.venv\Scripts\python.exe eval\harness\generate_runs.py
.\.venv\Scripts\python.exe eval\report.py
```

Individual evaluator:

```powershell
.\.venv\Scripts\python.exe eval\ranking\evaluator.py
```

Output: `eval/final_report.json` + console production readiness report.
