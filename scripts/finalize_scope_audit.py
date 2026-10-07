"""Read-only AWS/DB checks and local manifest metadata completion."""
import gzip
import json
from pathlib import Path
import boto3
import psycopg
from psycopg import sql
from rag_assistant import api, evaluate

ROOT = Path(__file__).resolve().parents[1]


def main():
    receipt = json.loads((ROOT / "alias_archive_receipt.json").read_text())
    directory = ROOT / receipt["archive_path"]
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["issue_numbers"] = [json.loads(line)["issue_number"] for line in gzip.decompress((directory / "github_issues_clean.jsonl.gz").read_bytes()).decode("utf-8").splitlines()]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with psycopg.connect(**evaluate.database_options(api.get_settings())) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        counts = {table: conn.execute(sql.SQL("SELECT count(*) FROM public.{} WHERE repository=%s").format(sql.Identifier(table)), ("fastapi/fastapi",)).fetchone()[0] for table in receipt["rows"]}
    assert counts == receipt["rows"]
    receipt["database_counts_verified_after_archive"] = counts
    (ROOT / "alias_archive_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    audit_path = ROOT / "pipeline_scope_audit.json"
    audit = json.loads(audit_path.read_text())
    events = boto3.client("events", region_name="us-east-2")
    scheduled = []
    for page in events.get_paginator("list_rules").paginate():
        for rule in page["Rules"]:
            if rule.get("ScheduleExpression"):
                targets = events.list_targets_by_rule(Rule=rule["Name"])["Targets"]
                scheduled.append({"name": rule["Name"], "state": rule["State"], "target_services": [t["Arn"].split(":")[2] for t in targets]})
    audit["legacy_eventbridge_scheduled_rules"] = scheduled
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"retained_alias_counts": counts, "legacy_scheduled_rules": scheduled}, indent=2))


if __name__ == "__main__":
    main()
