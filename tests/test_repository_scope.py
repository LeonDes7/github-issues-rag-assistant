import os
import unittest
from unittest.mock import MagicMock, patch

from rag_assistant import repository_scope, embed_issue_chunks, load_bronze_to_rds, ingest_github_issues


class RepositoryScopeTests(unittest.TestCase):
    def test_ingestion_rejects_alias_before_any_network_call(self):
        with patch.dict(os.environ, {"GITHUB_REPOS": "tiangolo/fastapi"}), patch.object(ingest_github_issues, "required_environment") as settings:
            with self.assertRaises(ValueError):
                ingest_github_issues.run_ingestion(["fastapi/fastapi"])
            settings.assert_not_called()

    def test_configured_scope_rejects_unconfigured_alias_and_conflicting_aliases(self):
        with patch.dict(os.environ, {"GITHUB_REPOS": "tiangolo/fastapi,encode/starlette,pydantic/pydantic"}):
            self.assertEqual(repository_scope.selected_repositories(), repository_scope.DEFAULT_REPOSITORIES)
            with self.assertRaises(ValueError):
                repository_scope.selected_repositories(["fastapi/fastapi"])
        with patch.dict(os.environ, {"GITHUB_REPOS": "fastapi/fastapi,tiangolo/fastapi"}):
            with self.assertRaises(ValueError):
                repository_scope.configured_repositories()

    def test_bronze_reads_only_selected_prefix_and_assigns_configured_storage_name(self):
        client = MagicMock()
        client.list_objects_v2.return_value = {"Contents": []}
        with patch.dict(os.environ, {"GITHUB_REPOS": "encode/starlette"}):
            _, counts, _ = load_bronze_to_rds.read_bronze_records(client, "bucket")
        self.assertEqual(list(counts), ["encode/starlette"])
        client.list_objects_v2.assert_called_once_with(Bucket="bucket", Prefix="bronze/github/repo=encode__starlette/issue=")
        self.assertEqual(client.get_object.call_count, 1)

    def test_standalone_embedding_defaults_to_configured_repositories(self):
        with patch.dict(os.environ, {"GITHUB_REPOS": "encode/starlette"}), \
             patch.object(embed_issue_chunks, "required_environment", return_value={}), \
             patch.object(embed_issue_chunks, "database_options", return_value={}), \
             patch.object(embed_issue_chunks.psycopg, "connect"), \
             patch.object(embed_issue_chunks, "load_issue_rows", return_value=[]) as load_rows:
            embed_issue_chunks.run_embedding(dry_run=True)
            self.assertEqual(load_rows.call_args.kwargs["repositories"], ["encode/starlette"])
