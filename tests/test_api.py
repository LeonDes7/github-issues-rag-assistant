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
        original_encoder = api.tiktoken.encoding_for_model
        encoder_patch = patch.object(api.tiktoken, "encoding_for_model", side_effect=lambda model: original_encoder(
            "gpt-4o-mini" if model == "test-generation-model" else model
        ))
        encoder_patch.start()
        self.addCleanup(encoder_patch.stop)
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
        self.assertEqual(generation_request["max_completion_tokens"], 512)
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

    def test_generation_passes_configured_output_token_limit(self):
        self.settings["OPENAI_GENERATION_MAX_OUTPUT_TOKENS"] = 128
        self.openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Supported answer. [1]"))
        ]
        api.generate_grounded_answer_with_usage(
            self.openai_client, "test-generation-model", "question", [chunk()]
        )
        self.assertEqual(
            self.openai_client.chat.completions.create.call_args.kwargs["max_completion_tokens"], 128
        )

    def test_openai_client_passes_zero_or_configured_retry_limit(self):
        for retries in (None, 0, 2):
            with self.subTest(retries=retries):
                self.settings.pop("OPENAI_MAX_RETRIES", None)
                if retries is not None:
                    self.settings["OPENAI_MAX_RETRIES"] = retries
                with patch.object(api, "OpenAI") as constructor:
                    api.get_openai_client()
                constructor.assert_called_once_with(
                    api_key="test-api-key", max_retries=0 if retries is None else retries
                )

    def test_output_and_retry_environment_defaults_overrides_and_validation(self):
        environment = {key: "test-value" for key in (
            "OPENAI_API_KEY", "PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD", "API_AUTH_TOKEN"
        )}
        with patch.dict(os.environ, environment, clear=True), patch.object(api, "load_dotenv"), patch.object(api, "_load_runtime_secrets", return_value={}):
            loader = self.settings_patch.temp_original
            self.assertEqual(loader()["OPENAI_GENERATION_MAX_OUTPUT_TOKENS"], 512)
            self.assertEqual(loader()["OPENAI_MAX_RETRIES"], 0)
            for name, valid, invalid in (
                ("OPENAI_GENERATION_MAX_OUTPUT_TOKENS", "128", ("0", "-1", "16385", "1.5", "true", "")),
                ("OPENAI_MAX_RETRIES", "2", ("-1", "11", "1.5", "true", "")),
                ("RAG_MAX_GENERATION_INPUT_TOKENS", "12000", ("0", "-1", "120001", "1.5", "true", "")),
            ):
                os.environ[name] = valid
                self.assertEqual(loader()[name], int(valid))
                for value in invalid:
                    with self.subTest(name=name, value=value), self.assertRaisesRegex(RuntimeError, name):
                        os.environ[name] = value
                        loader()
                del os.environ[name]

    def test_generation_budget_trims_excerpts_preserving_all_source_ids(self):
        sources = [chunk(issue_number=i, text="Unicode Ω 漢字 and JSON \"quotes\". " * 1000) for i in (1, 2, 3)]
        prepared = api.prepare_generation_messages("gpt-4o-mini", "question", sources, 1500)
        self.assertIsNotNone(prepared)
        messages, sent_texts = prepared
        self.assertLessEqual(api.generation_input_token_count("gpt-4o-mini", messages), 1500)
        supplied = json.loads(messages[0]["content"].split("Retrieved evidence:\n", 1)[1])
        self.assertEqual([s["citation"] for s in supplied], ["[1]", "[2]", "[3]"])
        for actual, original in zip(supplied, sources):
            self.assertEqual(actual["source_url"], original["source_url"])
            self.assertEqual(actual["issue_number"], original["issue_number"])
            self.assertTrue(original["chunk_text"].startswith(actual["excerpt"]))
            self.assertTrue(actual["excerpt_truncated"])
        self.assertEqual(sent_texts, [s["excerpt"] for s in supplied])
        self.assertGreater(len(sources[0]["chunk_text"]), len(sent_texts[0]))

    def test_generation_budget_preserves_full_prompt_when_it_fits(self):
        source = chunk()
        messages, texts = api.prepare_generation_messages("gpt-4o-mini", "question", [source], 12000)
        supplied = json.loads(messages[0]["content"].split("Retrieved evidence:\n", 1)[1])
        self.assertEqual(texts, [source["chunk_text"]])
        self.assertNotIn("excerpt_truncated", supplied[0])

    def test_impossible_prompt_budget_abstains_without_generation_and_keeps_api_sources(self):
        self.settings["RAG_MAX_GENERATION_INPUT_TOKENS"] = 1
        self.openai_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)]
        with patch.object(api, "retrieve_chunks", return_value=[chunk()]):
            response = self.client.post("/ask", json={"question": "question"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], api.MODEL_ABSTENTION_ANSWER)
        self.assertEqual(response.json()["citations"][0]["source_url"], chunk()["source_url"])
        self.openai_client.chat.completions.create.assert_not_called()

    def test_generation_sdk_receives_bounded_prompt_and_cleanup_uses_only_sent_text(self):
        self.settings["RAG_MAX_GENERATION_INPUT_TOKENS"] = 1200
        source = chunk(text="related text " * 2000 + "\nsecret_tail_command()")
        self.openai_client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(
            content="Example:\n```python\nsecret_tail_command()\n```\n[1]"
        ))]
        answer, _, _ = api.generate_grounded_answer_with_usage(self.openai_client, "test-generation-model", "question", [source])
        messages = self.openai_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertLessEqual(api.generation_input_token_count("gpt-4o-mini", messages), 1200)
        self.assertNotIn("secret_tail_command", messages[0]["content"])
        self.assertNotIn("secret_tail_command", answer)

    def test_truncated_generation_context_keeps_structured_api_sources_in_order(self):
        self.settings["RAG_MAX_GENERATION_INPUT_TOKENS"] = 1500
        sources = [chunk(issue_number=i, text="evidence " * 3000) for i in (12, 13)]
        self.openai_client.embeddings.create.return_value.data = [MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)]
        self.openai_client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content=api.ABSTENTION_MARKER))]
        with patch.object(api, "retrieve_chunks", return_value=sources):
            response = self.client.post("/ask", json={"question": "question"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["answer"], api.MODEL_ABSTENTION_ANSWER)
        self.assertEqual([s["issue_number"] for s in body["citations"]], [12, 13])
        self.assertEqual([s["source_url"] for s in body["citations"]], [s["source_url"] for s in sources])
        messages = self.openai_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertLessEqual(api.generation_input_token_count("gpt-4o-mini", messages), 1500)

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
        self.assertEqual(response.json()["answer"], api.LOW_EVIDENCE_ANSWER)
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
        self.assertEqual(response.json()["answer"], api.LOW_EVIDENCE_ANSWER)
        self.assertEqual(response.json()["performance"]["llm_latency_ms"], 0)
        self.openai_client.chat.completions.create.assert_not_called()

    def test_generation_prompt_requires_concise_abstention_and_exact_citation_support(self):
        sources = [
            chunk(issue_number=2074, text="Do you have any resource that can be accessed by only one process?"),
            chunk(issue_number=3008, chunk_type="heuristic_resolution",
                  text="Subclass the UvicornWorker and pass the configuration yourself."),
        ]
        answer = "The retrieved excerpts do not establish cross-worker OAuth2 revocation within 30 seconds."
        self.openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=answer))
        ]
        self.openai_client.chat.completions.create.return_value.usage = None

        result, input_tokens, output_tokens = api.generate_grounded_answer_with_usage(
            self.openai_client, "test-generation-model",
            "How can OAuth2 revoke a WebSocket across four workers within 30 seconds?",
            sources,
        )

        prompt = self.openai_client.chat.completions.create.call_args.kwargs["messages"][0]["content"]
        for requirement in (
            "output only [INSUFFICIENT_EVIDENCE]",
            "do not write any optional factual claim or evidence summary",
            "not an exhaustive absence of evidence in the corpus",
            "Verify each claim against its exact cited excerpt",
            "neighboring source is not support",
            "Split claims when different excerpts support different parts",
            "omit any unsupported part",
            "A plain statement of insufficient retrieved evidence does not need a citation",
            "Treat heuristic resolution chunks as low-confidence evidence",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, prompt)
        supplied = json.loads(prompt.split("Retrieved evidence:\n", 1)[1])
        self.assertEqual([source["citation"] for source in supplied], ["[1]", "[2]"])
        for source, original in zip(supplied, sources):
            self.assertEqual(source["excerpt"], original["chunk_text"])
            self.assertEqual(source["source_url"], original["source_url"])
            self.assertEqual(source["issue_number"], original["issue_number"])
        self.assertEqual(result, api.MODEL_ABSTENTION_ANSWER)
        self.assertEqual((input_tokens, output_tokens), (0, 0))

    def test_ask_preserves_model_abstention_after_cutoff_pass_without_adding_claims(self):
        answer = "The retrieved excerpts do not establish cross-worker OAuth2 revocation within 30 seconds."
        self.openai_client.embeddings.create.return_value.data = [
            MagicMock(embedding=[0.01] * api.VECTOR_DIMENSIONS)
        ]
        self.openai_client.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content=answer))
        ]
        with patch.object(api, "retrieve_chunks", return_value=[chunk(similarity=0.63)]):
            response = self.client.post("/ask", json={"question": "How can OAuth2 revoke a WebSocket across four workers within 30 seconds?"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], api.MODEL_ABSTENTION_ANSWER)
        self.assertEqual(len(response.json()["citations"]), 1)
        self.assertEqual(response.json()["citations"][0]["source_url"], chunk()["source_url"])
        self.openai_client.chat.completions.create.assert_called_once()

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

    def test_explicit_abstention_discards_all_model_prose_and_keeps_usage(self):
        for answer in (
            api.ABSTENTION_MARKER,
            "  " + api.ABSTENTION_MARKER + "\nRelated workers guarantee durability [1].",
            api.ABSTENTION_MARKER + "\n```python\napp.add_middleware(MyMiddleware)\n``` [2]",
        ):
            with self.subTest(answer=answer):
                self.openai_client.chat.completions.create.return_value.choices = [
                    MagicMock(message=MagicMock(content=answer))
                ]
                self.openai_client.chat.completions.create.return_value.usage = MagicMock(
                    prompt_tokens=123, completion_tokens=45
                )
                result = api.generate_grounded_answer_with_usage(
                    self.openai_client, "test-generation-model", "question", [chunk()]
                )
                self.assertEqual(result, (api.MODEL_ABSTENTION_ANSWER, 123, 45))
                self.assertNotIn("[", result[0])

    def test_legacy_abstention_discards_auxiliary_claims(self):
        for opening in (
            "Insufficient retrieved evidence to answer.",
            "I cannot determine a supported method.",
            "I can’t provide the requested guarantee.",
            "- There is no evidence in the retrieved issues of this configuration.",
            "The retrieved excerpts do not establish this guarantee.",
        ):
            with self.subTest(opening=opening):
                self.assertEqual(
                    api.finalize_generated_answer(opening + "\nUnrelated claim [1].", []),
                    api.MODEL_ABSTENTION_ANSWER,
                )

    def test_supported_answers_keep_existing_cleanup_and_citations(self):
        evidence = ["app.add_middleware(MyMiddleware)"]
        for answer in (
            "Add middleware. [1]",
            "No, this excerpt says custom validations are not encoded. [1]",
            "Use the documented setup. [1] Additional evidence is insufficient for other workloads.",
            "The issue quotes 'I cannot determine the cause' and documents the fix. [1]",
            "Use:\n```python\napp.add_middleware(MyMiddleware)\n```\n[1]",
            "Use:\n```python\nunknown()\n```\n[1]",
        ):
            with self.subTest(answer=answer):
                self.assertEqual(
                    api.finalize_generated_answer(answer, evidence),
                    api.clean_generated_answer(answer, evidence),
                )

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
