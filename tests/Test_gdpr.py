import json
import os
import unittest

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-gdpr-tests")
os.environ.setdefault("MASTER_KEY", "aa" * 32)

from data.llm_audit import (  # noqa: E402
    clear_pii_index_cache,
    delete_llm_logs_for_candidate,
    ensure_llm_audit_schema,
    log_llm_request,
    redact_payload_for_audit,
)
from data.db import get_reports_conn, get_staffing_conn  # noqa: E402
from api.llm_data_minimization import (  # noqa: E402
    minimize_candidate_for_llm,
    resolve_candidate_labels,
)
from api.gdpr import gdpr_delete_candidate  # noqa: E402


class TestLlmAuditRedaction(unittest.TestCase):
    def setUp(self):
        clear_pii_index_cache()
        conn = get_staffing_conn()
        try:
            row = conn.execute(
                "SELECT employee_id, email, first_name, last_name FROM employees LIMIT 1"
            ).fetchone()
            self.employee_id, self.email, self.first_name, self.last_name = row
            self.full_name = f"{self.first_name} {self.last_name}"
        finally:
            conn.close()

    def test_redact_replaces_name_and_email(self):
        payload = {
            "messages": [{
                "role": "user",
                "content": f"Candidate {self.full_name} email {self.email}",
            }]
        }
        redacted, ids = redact_payload_for_audit(
            payload,
            extra_candidate_ids=[self.employee_id],
        )
        self.assertIn(f"candidate#{self.employee_id}", redacted)
        self.assertIn(f"[candidate#{self.employee_id}]", redacted)
        self.assertNotIn(self.full_name, redacted)
        self.assertNotIn(self.email, redacted)
        self.assertIn(self.employee_id, ids)

    def test_log_llm_request_persists_redacted_payload(self):
        log_id = log_llm_request(
            manager_id="test-mgr",
            endpoint="test_endpoint",
            provider="anthropic",
            system="system prompt",
            messages=[{"role": "user", "content": f"Contact {self.full_name} at {self.email}"}],
            model="claude-test",
            max_tokens=100,
            referenced_candidate_ids=[self.employee_id],
        )
        conn = get_reports_conn()
        ensure_llm_audit_schema(conn)
        row = conn.execute(
            "SELECT endpoint, redacted_payload, referenced_candidate_ids FROM llm_request_log WHERE id = ?",
            (log_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(row[0], "test_endpoint")
        self.assertNotIn(self.email, row[1])
        self.assertIn(str(self.employee_id), row[2])


class TestDataMinimization(unittest.TestCase):
    def test_minimize_candidate_excludes_pii_fields(self):
        slim = minimize_candidate_for_llm({
            "employee_id": 42,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "title": "Engineer",
            "skills": ["Python"],
            "cost_center": "CC-99",
        })
        self.assertEqual(slim["candidate_id"], 42)
        self.assertNotIn("name", slim)
        self.assertNotIn("email", slim)
        self.assertNotIn("cost_center", slim)

    def test_resolve_candidate_labels(self):
        text = "Recommend candidate#42 for the role."
        resolved = resolve_candidate_labels(text, {42: "Jane Doe"})
        self.assertIn("Jane Doe", resolved)
        self.assertNotIn("candidate#42", resolved)


class TestGdprDelete(unittest.TestCase):
    def test_gdpr_delete_removes_employee_and_logs(self):
        conn = get_staffing_conn()
        try:
            conn.execute(
                """
                INSERT INTO employees (
                    employee_id, first_name, last_name, email, title, seniority_level,
                    department, location, country, employment_type, hire_date,
                    years_experience, status, current_utilization_pct, available_from
                ) VALUES (
                    999999, 'GDPR', 'TestUser', 'gdpr.test@example.com', 'Tester', 'Mid',
                    'Test', 'Berlin', 'Germany', 'Permanent', '2020-01-01',
                    3, 'bench', 0, '2026-01-01'
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        log_llm_request(
            manager_id="mgr",
            endpoint="fit_summary",
            provider="anthropic",
            system=None,
            messages=[{"role": "user", "content": "candidate#999999"}],
            referenced_candidate_ids=[999999],
        )

        result = gdpr_delete_candidate(999999, performed_by="test-mgr")
        self.assertEqual(result["status"], "completed")
        self.assertIn("deleted_employee_row", result["actions_taken"])

        conn = get_staffing_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM employees WHERE employee_id = 999999"
            ).fetchone()
            self.assertIsNone(row)
        finally:
            conn.close()

        deleted_logs = delete_llm_logs_for_candidate(999999)
        self.assertEqual(deleted_logs, 0)


if __name__ == "__main__":
    unittest.main()
