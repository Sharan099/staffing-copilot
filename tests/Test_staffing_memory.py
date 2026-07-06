import unittest

from data.db import get_reports_conn, get_staffing_conn
from data.staffing_context import extract_staffing_context
from data.staffing_memory import get_staffing_memory, log_rejection


class TestStaffingMemory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        get_staffing_conn().close()
        get_reports_conn().close()

    def test_extract_staffing_context(self):
        ctx = extract_staffing_context("Need a Python dev for BMW automotive project")
        self.assertEqual(ctx["client_name"], "BMW")
        self.assertEqual(ctx["domain"], "automotive")

    def test_log_and_recall_rejection(self):
        employee_id = 1
        conn = get_staffing_conn()
        try:
            row = conn.execute(
                "SELECT (first_name || ' ' || last_name) AS name FROM employees WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        name = row[0]

        log_rejection(
            employee_id,
            name,
            "test_manager",
            "BMW automotive staffing need",
            "Not enough domain depth",
        )

        memory = get_staffing_memory(employee_id, name, "BMW automotive Python role")
        self.assertTrue(memory["rejected_for_client"])
        self.assertTrue(any(i["type"] == "prior_rejection" for i in memory["items"]))

    def test_memory_read_only_no_auto_exclude(self):
        """Memory is informational — get_staffing_memory never raises or blocks."""
        memory = get_staffing_memory(99999, "Nobody", "generic staffing request")
        self.assertEqual(memory["similar_domain_approvals"], 0)
        self.assertFalse(memory["rejected_for_client"])


if __name__ == "__main__":
    unittest.main()
