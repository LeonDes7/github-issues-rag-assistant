import unittest
import uuid
from unittest.mock import MagicMock

from rag_assistant import embed_issue_chunks as embedder


def issue_row(**overrides):
    row = {
        "repository": "fastapi/fastapi",
        "issue_number": 42,
        "title": "Unexpected response",
        "body": "## Reproduction\n\n```python\nprint('preserve this')\n```",
        "github_url": "https://github.com/fastapi/fastapi/issues/42",
        "comments": [
            {
                "body": "Try this workaround.",
                "html_url": "https://github.com/fastapi/fastapi/issues/42#issuecomment-1",
            }
        ],
        "resolution_text": "Fixed in the next release.",
        "resolution_confidence": "low",
    }
    row.update(overrides)
    return row


class IssueChunkEmbeddingTests(unittest.TestCase):
    def test_builds_contextual_chunks_for_each_source_type(self):
        chunks = embedder.build_issue_chunks([issue_row()])

        self.assertEqual(
            [chunk.chunk_type for chunk in chunks],
            ["issue_body", "comment", "heuristic_resolution"],
        )
        for chunk in chunks:
            self.assertIn("Repository: fastapi/fastapi", chunk.chunk_text)
            self.assertIn("Issue: #42", chunk.chunk_text)
            self.assertIn("Title: Unexpected response", chunk.chunk_text)
            self.assertLessEqual(chunk.token_count, embedder.CHUNK_TOKENS)
        self.assertIn("print('preserve this')", chunks[0].chunk_text)
        self.assertIn("not ground truth", chunks[2].chunk_text)
        self.assertIn("#issuecomment-1", chunks[1].source_url)

    def test_chunk_identifiers_are_stable_and_skip_empty_sources(self):
        first = embedder.build_issue_chunks(
            [issue_row(comments=[], resolution_text=None)]
        )
        second = embedder.build_issue_chunks(
            [issue_row(comments=[], resolution_text=None)]
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].chunk_type, "issue_body")
        self.assertEqual(first[0].chunk_id, second[0].chunk_id)
        self.assertIsInstance(first[0].chunk_id, uuid.UUID)

    def test_chunks_long_markdown_with_overlap_and_preserves_all_text(self):
        encoder = embedder.token_encoder()
        source = (
            "Paragraph one has meaningful text.\n\n"
            + ("def function_name():\n    return 'value'\n\n" * 80)
            + "\n\nParagraph at the end."
        )

        chunks = embedder.chunk_text(source, encoder)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(count <= embedder.CHUNK_TOKENS for _, count in chunks))
        self.assertIn("Paragraph at the end.", "".join(text for text, _ in chunks))
        self.assertTrue(any("def function_name" in text for text, _ in chunks))

    def test_summary_estimates_batch_count_and_cost(self):
        chunks = embedder.build_issue_chunks(
            [issue_row(), issue_row(issue_number=43)]
        )

        summary = embedder.summarize_chunks(chunks)

        self.assertEqual(summary["chunk_count"], 6)
        self.assertEqual(
            summary["chunks_by_type"],
            {"issue_body": 2, "comment": 2, "heuristic_resolution": 2},
        )
        self.assertEqual(summary["estimated_embedding_api_calls"], 1)
        self.assertGreaterEqual(summary["estimated_cost_usd"], 0)

    def test_existing_embedding_count_batches_below_postgres_parameter_limit(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (5000, 5000, 4900, 9800),
            (1, 1, 1, 2),
        ]
        chunks = [
            embedder.IssueChunk(
                chunk_id=uuid.uuid4(),
                repository="tiangolo/fastapi",
                issue_number=index + 1,
                chunk_index=0,
                chunk_type="issue_body",
                chunk_text="Issue text",
                source_url="https://github.com/tiangolo/fastapi/issues/1",
                content_hash="hash",
                token_count=2,
            )
            for index in range(5001)
        ]

        (
            existing,
            stored_embeddings,
            reusable,
            reusable_tokens,
        ) = embedder.count_existing_embeddings(connection, chunks)

        self.assertEqual((existing, stored_embeddings, reusable), (5001, 5001, 4901))
        self.assertEqual(reusable_tokens, 9802)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertTrue(
            all(
                len(call.args[1]) <= 20000
                for call in cursor.execute.call_args_list
            )
        )
        self.assertIn(
            "existing.content_hash = desired.content_hash",
            cursor.execute.call_args.args[0],
        )

    def test_load_issue_rows_can_filter_repositories(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = []
        cursor.fetchall.return_value = []

        rows = embedder.load_issue_rows(
            connection,
            limit=10,
            changed_only=False,
            repositories=["tiangolo/fastapi", "encode/starlette"],
        )

        self.assertEqual(rows, [])
        query, parameters = cursor.execute.call_args.args
        self.assertIn("WHERE repository = ANY(%s)", query)
        self.assertEqual(
            parameters,
            [["tiangolo/fastapi", "encode/starlette"], 10],
        )

    def test_persists_chunk_rows_with_batched_executemany(self):
        connection = MagicMock()
        chunks = embedder.build_issue_chunks([issue_row()])

        embedder.persist_chunk_rows(connection, chunks)

        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.executemany.assert_called_once()
        query, parameters = cursor.executemany.call_args.args
        self.assertEqual(query, embedder.UPSERT_CHUNK_SQL)
        self.assertEqual(len(list(parameters)), len(chunks))
        connection.commit.assert_called_once()

    def test_stores_embedding_batch_with_single_update(self):
        connection = MagicMock()
        client = MagicMock()
        pending = [
            {"chunk_id": uuid.uuid4(), "chunk_text": "First issue"},
            {"chunk_id": uuid.uuid4(), "chunk_text": "Second issue"},
        ]
        response = client.embeddings.create.return_value
        response.usage.prompt_tokens = 12
        response.data = [
            MagicMock(index=0, embedding=[0.1] * embedder.VECTOR_DIMENSIONS),
            MagicMock(index=1, embedding=[0.2] * embedder.VECTOR_DIMENSIONS),
        ]

        tokens, api_calls, failed = embedder.embed_pending_chunks(
            connection,
            client,
            pending,
        )

        self.assertEqual((tokens, api_calls, failed), (12, 1, 0))
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once()
        query, parameters = cursor.execute.call_args.args
        self.assertIn("FROM (VALUES", query)
        self.assertEqual(len(parameters), 4)
        connection.commit.assert_called_once()

    def test_pending_issue_selection_includes_null_embeddings_only(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.description = []
        cursor.fetchall.return_value = []

        embedder.load_issue_rows(
            connection,
            limit=None,
            repositories=["tiangolo/fastapi"],
            pending_only=True,
        )

        query, parameters = cursor.execute.call_args.args
        self.assertIn("chunks.embedding IS NULL", query)
        self.assertIn("chunks.content_hash = issue.content_hash", query)
        self.assertEqual(parameters, [["tiangolo/fastapi"]])

    def test_similarity_results_are_cross_issue_and_do_not_return_chunk_text(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [
            (
                "fastapi/fastapi",
                42,
                "issue_body",
                "encode/starlette",
                12,
                "comment",
                "https://github.com/encode/starlette/issues/12",
                0.82,
            )
        ]

        results = embedder.similarity_search_examples(connection)

        result = results[0]
        self.assertEqual(result["similar_issue"]["similarity"], 0.82)
        self.assertNotEqual(
            (
                result["query_issue"]["repository"],
                result["query_issue"]["issue_number"],
            ),
            (
                result["similar_issue"]["repository"],
                result["similar_issue"]["issue_number"],
            ),
        )
        self.assertNotIn("chunk_text", result["similar_issue"])
        self.assertNotIn("embedding", result["similar_issue"])
        self.assertIn(
            "<> (seeds.repository, seeds.issue_number)",
            cursor.execute.call_args.args[0],
        )

    def test_create_table_uses_verified_composite_foreign_key(self):
        self.assertIn(
            "FOREIGN KEY (repository, issue_number)",
            embedder.CREATE_TABLE_SQL,
        )
        self.assertIn(
            "REFERENCES public.github_issues_clean (repository, issue_number)",
            embedder.CREATE_TABLE_SQL,
        )
        self.assertIn("embedding vector(1536)", embedder.CREATE_TABLE_SQL)
        self.assertIn("search_vector tsvector", embedder.CREATE_TABLE_SQL)
        self.assertIn("USING hnsw (embedding vector_cosine_ops)", embedder.CREATE_INDEX_SQL)
        self.assertIn("USING gin (search_vector)", embedder.CREATE_FULL_TEXT_INDEX_SQL)
        self.assertIn(
            "WHEN existing.chunk_text IS DISTINCT FROM EXCLUDED.chunk_text",
            embedder.UPSERT_CHUNK_SQL,
        )

    def test_report_summary_contains_no_credentials_or_chunk_text(self):
        chunks = embedder.build_issue_chunks([issue_row()])
        summary = embedder.summarize_chunks(chunks)
        serialized = str(summary)

        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn("PGPASSWORD", serialized)
        self.assertNotIn("preserve this", serialized)


if __name__ == "__main__":
    unittest.main()
