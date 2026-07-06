import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("MASTER_KEY", "aa" * 32)

from api.llm_client import _call_groq, _groq_error_detail  # noqa: E402


class TestGroqClient(unittest.TestCase):
    def test_groq_error_detail_parses_json(self):
        body = '{"error":{"message":"Invalid API Key"}}'
        self.assertIn("Invalid API Key", _groq_error_detail(401, body))

    def test_groq_error_detail_1010(self):
        self.assertIn("blocked", _groq_error_detail(403, "error code: 1010").lower())

    @patch("api.llm_client.urllib.request.urlopen")
    def test_groq_request_includes_user_agent(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"choices":[{"message":{"content":"hello"}}]}'
        )
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = _call_groq(
            "gsk_testkey12345678",
            "llama-3.1-8b-instant",
            "system prompt",
            [{"role": "user", "content": "hi"}],
            100,
        )
        self.assertEqual(result, "hello")

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_header("User-agent"), "StaffingCopilot/1.0")
        self.assertIn("Bearer gsk_testkey12345678", request.get_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
