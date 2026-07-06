import datetime
import os
import unittest
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-api-tests")
os.environ.setdefault("MASTER_KEY", "aa" * 32)

from api.auth import JWT_SECRET  # noqa: E402
from main import app  # noqa: E402
from scoring.scorer import ScoreCriteria  # noqa: E402


def _token(username: str, role: str) -> str:
    return jwt.encode(
        {
            "username": username,
            "role": role,
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


class TestApiSecurity(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_approve_rejects_non_manager(self):
        headers = {"Authorization": f"Bearer {_token('viewer', 'viewer')}"}
        response = self.client.post(
            "/approve",
            json={
                "employee_id": 1,
                "client_message": "Python engineer in Berlin",
                "works_council_notification": "no",
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)

    @patch("main.ensure_manager_credentials")
    @patch("main.generate_fit_summary", return_value="Strong fit.")
    @patch(
        "main.extract_criteria",
        return_value=ScoreCriteria(required_skills=["Python", "LLM"], location="Berlin"),
    )
    @patch("main._server_ranked_top_five")
    def test_approve_rejects_employee_not_in_top_five(
        self, mock_rank, _mock_extract, _mock_summary, _mock_creds
    ):
        mock_rank.return_value = [{"employee_id": 10, "name": "Real", "total_score": 90, "score_breakdown": []}]
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.post(
            "/approve",
            json={
                "employee_id": 999999,
                "client_message": "Python and LLM in Berlin",
                "works_council_notification": "no",
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_agent_search_rejects_overlong_message(self):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.post(
            "/agent-search",
            json={"client_message": "x" * 1001},
            headers=headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_reject_rejects_non_manager(self):
        headers = {"Authorization": f"Bearer {_token('viewer', 'viewer')}"}
        response = self.client.post(
            "/reject",
            json={"employee_id": 1, "client_message": "BMW Python role"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_reject_logs_manager_decision(self):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.post(
            "/reject",
            json={
                "employee_id": 1,
                "client_message": "BMW automotive Python",
                "manager_notes": "Not enough OEM depth",
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("rejection_id", body)
        self.assertEqual(body["employee_id"], 1)

    def test_settings_providers_requires_auth(self):
        response = self.client.get("/api/settings/providers")
        self.assertEqual(response.status_code, 401)

    def test_save_credentials_masks_key(self):
        headers = {"Authorization": f"Bearer {_token('settings_mgr', 'manager')}"}
        response = self.client.post(
            "/api/settings/credentials",
            json={
                "provider": "groq",
                "model_name": "llama-3.1-8b-instant",
                "api_key": "gsk_testkey12345678",
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["key_last4"], "5678")
        self.assertNotIn("api_key", body)

        get_resp = self.client.get("/api/settings/credentials", headers=headers)
        self.assertEqual(get_resp.status_code, 200)
        saved = get_resp.json()
        self.assertTrue(saved["configured"])
        self.assertEqual(saved["key_last4"], "5678")

    @patch("main.ensure_manager_credentials")
    @patch(
        "main.extract_request_for_form",
        return_value={
            "required_skills": ["Python", "LangGraph"],
            "core_skills": ["Python", "LangGraph"],
            "location": "Munich",
            "needed_by": "2026-08-01",
            "role_count": 2,
            "client_facing": True,
            "required_german_level": "business",
        },
    )
    def test_extract_request_returns_form_fields(self, _mock_extract, _mock_creds):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.post(
            "/api/extract-request",
            json={"client_message": "Two senior AI engineers in Munich next month"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["role_count"], 2)
        self.assertEqual(body["location"], "Munich")
        self.assertIn("LangGraph", body["required_skills"])

    def test_employee_profile_requires_auth(self):
        response = self.client.get("/api/employees/1/profile")
        self.assertEqual(response.status_code, 401)

    def test_employee_profile_returns_details(self):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.get("/api/employees/1/profile", headers=headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["employee_id"], 1)
        self.assertIn("email", body)
        self.assertIn("skills", body)
        self.assertIn("project_history", body)

    def test_report_pdf_download(self):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        listing = self.client.get("/reports", headers=headers)
        self.assertEqual(listing.status_code, 200)
        reports = listing.json().get("reports", [])
        if not reports:
            self.skipTest("No reports in database")
        report_id = reports[0]["report_id"]
        response = self.client.get(f"/reports/{report_id}/pdf", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")
        self.assertGreater(len(response.content), 500)
        self.assertIn("attachment", response.headers.get("content-disposition", ""))

    def test_gdpr_delete_requires_manager(self):
        headers = {"Authorization": f"Bearer {_token('viewer', 'viewer')}"}
        response = self.client.delete("/api/candidates/1/gdpr-delete", headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_compliance_endpoint_returns_data_flow(self):
        headers = {"Authorization": f"Bearer {_token('mgr', 'manager')}"}
        response = self.client.get("/api/settings/compliance", headers=headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("zdr", body)
        self.assertIn("data_flow", body)
        self.assertIn("workflow", body["data_flow"])


if __name__ == "__main__":
    unittest.main()
