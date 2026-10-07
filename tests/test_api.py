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
            "RAG_CONTEXT_MODE": "chunks",
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
        self.openai_client.chat.completions.create.assert_not_called()

    def test_ask_refuses_low_confidence_without_calling_generation(self):
        low_confidence = chunk(similarity=0.1)
        low_confidence["retrieval_score"] = 0.1
        with patch.object(api, "retrieve_chunks", return_value=[low_confidence]):
            self.openai_client.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)
            ]

            response = self.client.post(
                "/ask",
                json={"question": "How does this issue behave?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("isn't enough evidence", response.json()["answer"])
        self.assertEqual(response.json()["performance"]["llm_latency_ms"], 0)
        self.openai_client.chat.completions.create.assert_not_called()

    def test_ask_issue_mode_fetches_thirty_and_generates_with_distinct_issues(self):
        self.settings["RAG_CONTEXT_MODE"] = "issues"
        candidates = [chunk(issue_number=12), chunk(issue_number=12), chunk(issue_number=13)]
        self.openai_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)]
        with patch.object(api, "retrieve_chunks", return_value=candidates) as retrieve, patch.object(api, "generate_grounded_answer_with_usage", return_value=("Answer [1] [2]", 10, 5)) as generate:
            response = self.client.post("/ask", json={"question": "How does middleware work?"})
        self.assertEqual(response.status_code, 200)
        retrieve.assert_called_once_with(self.connection, [0.01] * api.VECTOR_DIMENSIONS, 30)
        self.assertEqual([c["issue_number"] for c in generate.call_args.args[3]], [12, 13])
        self.assertEqual(len(response.json()["citations"]), 2)

    def test_confidence_cutoff_accepts_scores_at_the_threshold(self):
        self.assertFalse(api.should_refuse([{"retrieval_score": 0.25}], 0.25))
        self.assertTrue(api.should_refuse([{"retrieval_score": 0.249}], 0.25))

    def test_estimated_request_cost_uses_configured_token_rates(self):
        settings = {
            "OPENAI_EMBEDDING_COST_PER_MILLION_TOKENS_USD": 0.02,
            "OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD": 0.15,
            "OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD": 0.60,
        }

        cost = api.estimate_request_cost(settings, 1000, 2000, 500)

        self.assertAlmostEqual(cost, 0.00062)

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

    def test_retrieval_sets_local_search_depth_inside_transaction(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        events = []
        connection.transaction.return_value.__enter__.side_effect = lambda: events.append("transaction")
        cursor.execute.side_effect = lambda sql, *args: events.append(sql)
        for depth in (100, 40):
            with self.subTest(depth=depth):
                events.clear()
                self.settings["RAG_HNSW_EF_SEARCH"] = depth
                api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5)
                self.assertEqual(events[:2], ["transaction", f"SET LOCAL hnsw.ef_search = {depth}"])
                self.assertIn("ORDER BY chunks.embedding", events[2])

    def test_retrieval_defaults_to_100_and_rejects_invalid_depth(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5)
        self.assertEqual(cursor.execute.call_args_list[0].args, ("SET LOCAL hnsw.ef_search = 100",))
        for depth in (0, 1001, True, "40"):
            with self.subTest(depth=depth), self.assertRaises(ValueError):
                api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5, hnsw_ef_search=depth)

    def test_hnsw_search_depth_environment_default_override_and_validation(self):
        environment = {key: "test-value" for key in (
            "OPENAI_API_KEY", "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD", "API_AUTH_TOKEN"
        )}
        with patch.dict(os.environ, environment, clear=True), patch.object(api, "load_dotenv"), patch.object(api, "_load_runtime_secrets", return_value={}):
            # setUp mocks load_settings for HTTP tests; exercise the actual
            # configuration loader here, without reading local credentials.
            loader = self.settings_patch.temp_original
            self.assertEqual(loader()["RAG_HNSW_EF_SEARCH"], 100)
            self.assertEqual(loader()["RAG_REPOSITORIES"], ["tiangolo/fastapi", "encode/starlette", "pydantic/pydantic"])
            os.environ["RAG_REPOSITORIES"] = "encode/starlette, pydantic/pydantic,encode/starlette"
            self.assertEqual(loader()["RAG_REPOSITORIES"], ["encode/starlette", "pydantic/pydantic"])
            os.environ["RAG_REPOSITORIES"] = " , "
            with self.assertRaisesRegex(RuntimeError, "RAG_REPOSITORIES"):
                loader()
            del os.environ["RAG_REPOSITORIES"]
            os.environ["RAG_HNSW_EF_SEARCH"] = "40"
            self.assertEqual(loader()["RAG_HNSW_EF_SEARCH"], 40)
            for value in ("bad", "0", "1001"):
                os.environ["RAG_HNSW_EF_SEARCH"] = value
                with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "RAG_HNSW_EF_SEARCH"):
                    loader()

    def test_repository_scope_filters_vector_and_both_hybrid_branches(self):
        repositories = ["tiangolo/fastapi", "encode/starlette", "pydantic/pydantic"]
        for mode, expected_count in (("vector", 1), ("hybrid", 2)):
            with self.subTest(mode=mode):
                connection = MagicMock()
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchall.return_value = []
                api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5,
                                    retrieval_mode=mode, query_text="middleware")
                sql, parameters = cursor.execute.call_args.args
                self.assertEqual(sql.count("chunks.repository = ANY(%s)"), expected_count)
                # Every candidate branch applies the scope before its own LIMIT.
                candidate_queries = sql.split("LIMIT %s")[:expected_count]
                for candidate_query in candidate_queries:
                    self.assertIn("chunks.repository = ANY(%s)", candidate_query)
                self.assertEqual(sum(p == repositories for p in parameters), expected_count)
                self.assertNotIn("fastapi/fastapi", repositories)

    def test_repository_scope_configuration_and_empty_scope_rejection(self):
        self.settings["RAG_REPOSITORIES"] = ["encode/starlette"]
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5)
        self.assertIn(["encode/starlette"], cursor.execute.call_args.args[1])
        with self.assertRaises(ValueError):
            api.retrieve_chunks(connection, [0.01] * api.VECTOR_DIMENSIONS, 5, repositories=[])

    def test_issue_context_keeps_best_chunk_per_issue_and_old_mode_is_selectable(self):
        candidates = [chunk(issue_number=1), chunk(issue_number=1, similarity=0.7),
                      chunk(issue_number=2), chunk(issue_number=3), chunk(issue_number=4), chunk(issue_number=5)]
        with patch.object(api, "retrieve_chunks", return_value=candidates) as retrieve:
            selected = api.retrieve_context(self.connection, [0.01], 5, context_mode="issues")
            self.assertEqual([c["issue_number"] for c in selected], [1, 2, 3, 4, 5])
            self.assertIs(selected[0], candidates[0])
            self.assertEqual(retrieve.call_args.args[2], 30)
            old = api.retrieve_context(self.connection, [0.01], 5, context_mode="chunks")
            self.assertEqual(retrieve.call_args.args[2], 5)
            self.assertEqual(old, candidates)
        with self.assertRaises(ValueError):
            api.retrieve_context(self.connection, [0.01], 5, context_mode="invalid")

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
