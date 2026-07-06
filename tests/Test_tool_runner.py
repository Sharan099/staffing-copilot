import unittest
from unittest.mock import MagicMock, patch

from tool_runner import (
    PUBLIC_TOOL_ERROR,
    TOOL_PERMISSION_DENIED,
    run_tool_call,
)


class _FakeCall:
    def __init__(self, name: str, input_data: dict):
        self.name = name
        self.input = input_data


class TestToolRunner(unittest.TestCase):
    @patch("tool_runner.search_people", side_effect=RuntimeError("secret path /tmp/db.sqlite"))
    def test_tool_errors_are_generic_outward(self, _mock_search):
        call = MagicMock()
        call.name = "search_people"
        call.input = {"required_skills": ["Python"]}

        result, status, _duration = run_tool_call(call)

        self.assertEqual(status, "failed")
        self.assertEqual(result, {"error": PUBLIC_TOOL_ERROR})
        self.assertNotIn("secret path", result["error"])

    def test_viewer_blocked_search_people(self):
        result, status, duration = run_tool_call(
            _FakeCall("search_people", {"required_skills": ["Python"]}),
            caller_role="viewer",
        )
        self.assertEqual(status, "forbidden")
        self.assertEqual(result["error"], TOOL_PERMISSION_DENIED)
        self.assertEqual(duration, 0.0)

    def test_viewer_blocked_get_availability(self):
        result, status, _ = run_tool_call(
            _FakeCall("get_availability", {"required_availability": "2026-10-01"}),
            caller_role="viewer",
        )
        self.assertEqual(status, "forbidden")
        self.assertEqual(result["error"], TOOL_PERMISSION_DENIED)

    def test_viewer_blocked_check_project_history(self):
        result, status, _ = run_tool_call(
            _FakeCall("check_project_history", {"employee_name": "Anna Test"}),
            caller_role="viewer",
        )
        self.assertEqual(status, "forbidden")
        self.assertEqual(result["error"], TOOL_PERMISSION_DENIED)

    def test_manager_can_call_tools(self):
        result, status, _ = run_tool_call(
            _FakeCall("search_people", {"required_skills": ["Python"]}),
            caller_role="manager",
        )
        self.assertEqual(status, "success")
        self.assertNotIn("error", result)


if __name__ == "__main__":
    unittest.main()
