"""Approved local archive only; all database operations are read-only."""

import gzip
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql

from rag_assistant import api, evaluate


def main():
    root = Path(__file__).resolve().parents[1]
    settings = api.get_settings()
    expected = {"github_issues_clean": 76, "github_issue_chunks": 632, "github_issue_classifications": 76}
    secret_names = ("OPENAI_API_KEY", "PGPASSWORD", "API_AUTH_TOKEN", "GITHUB_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")
    secrets = {settings.get(n) or os.getenv(n) for n in secret_names} - {None, ""}
    payloads, schema = {}, {}
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for table, count in expected.items():
            rows = [r[0] for r in conn.execute(sql.SQL("SELECT to_jsonb(t) FROM public.{} t WHERE repository=%s ORDER BY issue_number").format(sql.Identifier(table)), ("fastapi/fastapi",)).fetchall()]
            if len(rows) != count:
                raise RuntimeError("Archive counts changed; review required")
            payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
            if any(len(s) >= 8 and s in payload for s in secrets) or re.search(r"\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,})\b", payload):
                raise RuntimeError("Potential credential in source data; no archive files written")
            payloads[table] = payload.encode("utf-8")
            schema[table] = conn.execute("SELECT column_name,data_type,udt_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,)).fetchall()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = root / "archives" / "fastapi_alias" / stamp
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"created_at_utc": stamp, "repository": "fastapi/fastapi", "database_rows_retained": True,
                "issue_numbers": [json.loads(line)["issue_number"] for line in payloads["github_issues_clean"].decode("utf-8").splitlines()],
                "credential_scan": "No configured secret values or recognized credential patterns detected; archive includes table rows only, no environment or connection settings", "schema": schema, "files": {}}
    for table, payload in payloads.items():
        target = directory / (table + ".jsonl.gz")
        target.write_bytes(gzip.compress(payload))
        assert gzip.decompress(target.read_bytes()) == payload
        manifest["files"][target.name] = {"rows": expected[table], "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    receipt = {"archive_path": str(directory.relative_to(root)), "rows": expected, "total_rows": sum(expected.values()),
               "database_rows_retained": True, "credential_scan_passed": True, "roundtrip_verified": True, "files": manifest["files"]}
    (root / "docs/corpus/alias_archive_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
