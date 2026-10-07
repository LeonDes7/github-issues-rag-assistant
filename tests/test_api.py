import json
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from openai import OpenAI

from rag_assistant import api


def chunk(
    repository="fastapi/fastapi",
    issue_number=12,
    chunk_type="comment",
    text="Configure middleware with app.add_middleware(...).",
    similarity=0.83,
):
    return {
        "repository": repository,
        "issue_number": issue_number,
        "issue_url": f"https://github.com/{repository}/issues/{issue_number}",
        "source_url": (
            f"https://github.com/{repository}/issues/{issue_number}#issuecomment-1"
        ),
        "chunk_type": chunk_type,
        "chunk_text": text,
        "similarity_score": similarity,
        "predicted_category": "usage",
        "classification_confidence": "low",
    }


class ApiTests(unittest.TestCase):
    def setUp(self):
        api.get_settings.cache_clear()
        self.settings = {
            "OPENAI_API_KEY": "test-api-key",
            "PGHOST": "db-host",
            "PGDATABASE": "db-name",
            "PGUSER": "db-user",
            "PGPASSWORD": "db-password",
            "API_AUTH_TOKEN": "test-bearer-token",
            "PGPORT": 5432,
            "PGSSLMODE": "require",
            "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
            "OPENAI_GENERATION_MODEL": "test-generation-model",
            "CORS_ALLOWED_ORIGINS": ["http://localhost:8501"],
        }
        self.settings_patch = patch.object(api, "load_settings", return_value=self.settings)
        self.settings_patch.start()
        api.get_settings.cache_clear()
        self.app = api.create_app()
        self.client = TestClient(self.app)
        self.client.headers.update(
            {"Authorization": "Bearer test-bearer-token"}
        )
        self.connection = MagicMock()
        self.database_dependency = MagicMock()

        def provide_database_connection():
            self.database_dependency()
            return self.connection

        self.openai_client = MagicMock(spec=OpenAI)
        self.app.dependency_overrides[api.get_db_connection] = (
            provide_database_connection
        )
        self.app.dependency_overrides[api.get_openai_client] = (
            lambda: self.openai_client
        )

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()
        self.settings_patch.stop()
        api.get_settings.cache_clear()

    def test_health_checks_postgresql(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "database": "reachable"},
        )
        self.connection.cursor.assert_called_once()

    def test_ask_embeds_retrieves_and_returns_trusted_citations(self):
        result_chunk = chunk()
        with patch.object(api, "retrieve_chunks", return_value=[result_chunk]) as retrieve:
            self.openai_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)
            ]
            self.openai_client.chat.completions.create.return_value.choices = [
                MagicMock(
                    message=MagicMock(
                        content="Add middleware with `app.add_middleware(...)`. [1]"
                    )
                )
            ]

            response = self.client.post(
                "/ask",
                json={"question": "How do I configure middleware?", "top_k": 3},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], "Add middleware with `app.add_middleware(...)`. [1]")
        self.assertEqual(body["retrieval_metadata"]["top_k"], 3)
        self.assertEqual(body["retrieval_metadata"]["retrieved_count"], 1)
        self.assertEqual(body["citations"][0]["repository"], "fastapi/fastapi")
        self.assertEqual(body["citations"][0]["issue_number"], 12)
        self.assertEqual(body["citations"][0]["issue_url"], result_chunk["issue_url"])
        self.assertEqual(body["citations"][0]["source_url"], result_chunk["source_url"])
        self.assertEqual(body["citations"][0]["chunk_type"], "comment")
        self.assertEqual(body["citations"][0]["similarity_score"], 0.83)
        self.assertEqual(body["citations"][0]["predicted_category"], "usage")
        self.assertEqual(body["citations"][0]["classification_confidence"], "low")
        retrieve.assert_called_once_with(
            self.connection,
            [0.01] * api.VECTOR_DIMENSIONS,
            3,
        )
        self.openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input="How do I configure middleware?",
            dimensions=api.VECTOR_DIMENSIONS,
        )
        generation_request = self.openai_client.chat.completions.create.call_args.kwargs
        self.assertEqual(generation_request["model"], "test-generation-model")
        self.assertIn(result_chunk["chunk_text"], generation_request["messages"][0]["content"])
        self.assertEqual(
            generation_request["messages"][1],
            {"role": "user", "content": "How do I configure middleware?"},
        )

    def test_ask_validates_question_and_top_k(self):
        blank = self.client.post("/ask", json={"question": "   "})
        oversized_top_k = self.client.post(
            "/ask",
            json={"question": "valid", "top_k": 21},
        )

        self.assertEqual(blank.status_code, 422)
        self.assertEqual(oversized_top_k.status_code, 422)
        self.openai_client.embeddings.create.assert_not_called()

    def test_ask_requires_matching_bearer_token(self):
        self.client.headers.pop("Authorization")

        response = self.client.post(
            "/ask",
            json={"question": "How do I configure middleware?"},
        )

        self.assertEqual(response.status_code, 401)
        self.database_dependency.assert_not_called()
        self.openai_client.embeddings.create.assert_not_called()

    def test_runtime_settings_load_secrets_manager_json(self):
        secret_values = {
            "OPENAI_API_KEY": "test-openai-key",
            "PGPASSWORD": "test-db-password",
            "API_AUTH_TOKEN": "test-bearer-token",
        }
        with patch.dict(os.environ, {"RAG_SECRETS_ARN": "test-secret-arn"}):
            with patch.object(api.boto3, "client") as client:
                client.return_value.get_secret_value.return_value = {
                    "SecretString": json.dumps(secret_values)
                }

                result = api._load_runtime_secrets()

        self.assertEqual(result, secret_values)
        client.assert_called_once_with("secretsmanager")
        client.return_value.get_secret_value.assert_called_once_with(
            SecretId="test-secret-arn"
        )

    def test_runtime_settings_reject_non_json_secret_shape(self):
        with patch.dict(os.environ, {"RAG_SECRETS_ARN": "test-secret-arn"}):
            with patch.object(api.boto3, "client") as client:
                client.return_value.get_secret_value.return_value = {
                    "SecretString": json.dumps({"API_AUTH_TOKEN": 123})
                }

                with self.assertRaisesRegex(RuntimeError, "JSON object"):
                    api._load_runtime_secrets()

    def test_ask_handles_empty_retrieval_without_citations(self):
        with patch.object(api, "retrieve_chunks", return_value=[]):
            self.openai_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)
            ]
            self.openai_client.chat.completions.create.return_value.choices = [
                MagicMock(
                    message=MagicMock(
                        content="The retrieved evidence is insufficient to answer."
                    )
                )
            ]

            response = self.client.post(
                "/ask",
                json={"question": "What does an unrelated project do?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["citations"], [])
        self.assertEqual(
            response.json()["retrieval_metadata"]["retrieved_count"],
            0,
        )

    def test_hybrid_retrieval_uses_full_text_ranking_and_reciprocal_rank_fusion(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            (
                "encode/starlette",
                42,
                "https://github.com/encode/starlette/issues/42",
                "https://github.com/encode/starlette/issues/42#issuecomment-1",
                "comment",
                "middleware startup order",
                0.73,
                0.04,
                "bug",
                "medium",
            )
        ]

        retrieved = api.retrieve_chunks(
            connection,
            [0.01] * api.VECTOR_DIMENSIONS,
            5,
            retrieval_mode="hybrid",
            query_text="middleware startup order",
        )

        sql = cursor.execute.call_args.args[0]
        parameters = cursor.execute.call_args.args[1]
        self.assertIn("plainto_tsquery('english'", sql)
        self.assertIn("chunks.search_vector @@ search_query.query", sql)
        self.assertIn("SUM(1.0 / (60 + rank))", sql)
        self.assertEqual(parameters[0], "middleware startup order")
        self.assertEqual(retrieved[0]["retrieval_score"], 0.04)
        self.assertEqual(retrieved[0]["similarity_score"], 0.73)

    def test_hybrid_retrieval_requires_question_text(self):
        with self.assertRaisesRegex(ValueError, "query_text is required"):
            api.retrieve_chunks(
                MagicMock(),
                [0.01] * api.VECTOR_DIMENSIONS,
                5,
                retrieval_mode="hybrid",
            )

    def test_ask_uses_hybrid_retrieval_when_configured(self):
        self.settings["RAG_RETRIEVAL_MODE"] = "hybrid"
        with patch.object(
            api,
            "retrieve_chunks",
            return_value=[chunk()],
        ) as retrieve:
            self.openai_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)
            ]
            self.openai_client.chat.completions.create.return_value.choices = [
                MagicMock(message=MagicMock(content="Evidence supports this. [1]"))
            ]

            response = self.client.post(
                "/ask",
                json={"question": "How does middleware start?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["retrieval_metadata"]["retrieval_mode"],
            "hybrid",
        )
        retrieve.assert_called_once_with(
            self.connection,
            [0.01] * api.VECTOR_DIMENSIONS,
            5,
            retrieval_mode="hybrid",
            query_text="How does middleware start?",
        )

    def test_generated_answer_removes_empty_markdown_and_unsupported_code(self):
        malformed = (
            "Findings:\n"
            "- \n"
            "*   \n"
            "1. \n"
            "```python\n"
            "```"
        )

        cleaned = api.clean_generated_answer(malformed, ["Evidence text only."])

        self.assertEqual(cleaned, "Findings:")
        self.assertNotRegex(cleaned, r"(?m)^\s*(?:[-+*]|\d+[.)])\s*$")
        self.assertNotIn("```", cleaned)

    def test_generated_empty_list_answer_uses_clear_evidence_fallback(self):
        malformed = "- \n* \n```python\n```"

        cleaned = api.clean_generated_answer(malformed, [])

        self.assertEqual(
            cleaned,
            "The retrieved evidence does not support a usable answer.",
        )

    def test_generated_answer_keeps_code_only_when_exact_text_is_evidenced(self):
        supported = "Use:\n```python\napp.add_middleware(MyMiddleware)\n```"
        unsupported = "Use:\n```python\napp.add_middleware(UnknownMiddleware)\n```"
        evidence = ["Example uses app.add_middleware(MyMiddleware) for setup."]

        self.assertIn(
            "app.add_middleware(MyMiddleware)",
            api.clean_generated_answer(supported, evidence),
        )
        self.assertNotIn(
            "UnknownMiddleware",
            api.clean_generated_answer(unsupported, evidence),
        )

    def test_cors_allows_configured_local_streamlit_origin(self):
        response = self.client.options(
            "/ask",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://localhost:8501",
        )


if __name__ == "__main__":
    unittest.main()
