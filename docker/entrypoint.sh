#!/bin/sh
set -e

if [ ! -f "${STAFFING_DATA_DIR}/staffing_bosch_style.db" ]; then
  echo "No staffing database found - seeding demo data (first run only)..."
  PYTHONPATH=/app/src python /app/dev-scripts/seed_employees.py
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000 --app-dir /app/src
