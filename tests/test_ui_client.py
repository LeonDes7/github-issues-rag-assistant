import unittest
from unittest.mock import MagicMock, patch

import requests

from rag_assistant.ui_client import RagApiError, ask_api


class UiClientTests(unittest.TestCase):
    @patch("rag_assistant.ui_client.requests.post")
    def test_sends_bearer_token_and_returns_api_response(self, post):
        response = MagicMock()
        response.json.return_value = {"answer": "Grounded answer", "citations": []}
        post.return_value = response

        result = ask_api(
            "https://rag.example.test/",
            "test-token",
            "How does this work?",
            4,
        )

        self.assertEqual(result["answer"], "Grounded answer")
        post.assert_called_once_with(
            "https://rag.example.test/ask",
            json={"question": "How does this work?", "top_k": 4},
            headers={"Authorization": "Bearer test-token"},
            timeout=(5, 90),
        )
        response.raise_for_status.assert_called_once()

    @patch("rag_assistant.ui_client.requests.post")
    def test_http_failures_are_not_suppressed(self, post):
        response = MagicMock()
        response.status_code = 401
        response.raise_for_status.side_effect = requests.HTTPError("unauthorized")
        post.return_value = response

        with self.assertRaises(RagApiError) as raised:
            ask_api("http://localhost:8000", "token", "question", 5)
        self.assertEqual(raised.exception.status_code, 401)

    @patch("rag_assistant.ui_client.requests.post")
    def test_rejects_invalid_api_response_shape(self, post):
        response = MagicMock()
        response.json.return_value = {"answer": "missing citations"}
        post.return_value = response

        with self.assertRaisesRegex(ValueError, "invalid response"):
            ask_api("http://localhost:8000", "token", "question", 5)
