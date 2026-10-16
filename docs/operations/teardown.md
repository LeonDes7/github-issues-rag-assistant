# AWS teardown and recreation

## Completed teardown: October 16, 2026

The approved teardown completed and was verified: RDS `github-rag-db` and the
specified NAT gateway were deleted, and the NAT Elastic IP was released. The
live demo backend is **offline to save AWS costs**. Use the
[recorded demo video](../videos/github-issues-assistant-demo.mp4) instead.
S3 Bronze and the verified manual snapshot were preserved. The private execution
receipt records the actual snapshot identifier and final verification. Other
services were retained and can still incur charges; this was not a zero-cost
account cleanup. The commands below are reference instructions, not a request
to repeat teardown against already deleted resources.

Both scripts default to read-only previews. No script calls S3: the Bronze bucket
and all its contents are preserved. Private plans/receipts belong in ignored
`artifacts/`; they contain infrastructure identifiers, not secret values.

## Teardown preview

```powershell
.\.venv\Scripts\python.exe scripts/teardown_aws.py --dry-run --output artifacts/teardown_preview_new.json
```

This queries us-east-2 only. It validates the exact RDS/NAT/EIP relationship,
records account identity and restore parameters, and inventories Secrets Manager
(names only), ECR images, CloudWatch logs, Lambda, HTTP APIs, RDS/snapshots and
public IPv4 interfaces/allocations. An incomplete inventory blocks real execution.
It is not an account-wide billing audit; other regions/services can incur costs.

## Real teardown, only after separate approval

```powershell
.\.venv\Scripts\python.exe scripts/teardown_aws.py --execute --expected-account <AWS_ACCOUNT_ID> --output artifacts/teardown_execution_receipt.json
```

The script prints the complete fresh plan, verifies the account, then requires
this exact interactive input immediately before the first AWS mutation:

```text
TEARDOWN github-rag-db
```

Actions are strictly limited to:

1. Create a uniquely named **fresh manual snapshot** of `github-rag-db`. Wait for
   availability and verify the snapshot identifier, source instance, manual type,
   and available status. Existing automated backups are not a substitute.
2. Delete NAT `nat-097cf07818b8577a9` and wait until deletion completes.
3. Check allocation `eipalloc-0634590d08739cedc` is unassociated, then release it.
4. Reverify the new snapshot; delete `github-rag-db` and wait for deletion.
   The already verified manual snapshot is used instead of an additional final
   snapshot (`SkipFinalSnapshot=True`). Automated backups are explicitly retained.
   The database is deleted, not stopped.

No other resources are deleted or changed. Routes may be left pointing at the
deleted NAT. Lambda/API Gateway and Streamlit may remain present but the RAG
backend will be unavailable. To avoid additional incoming traffic or writes during
snapshot creation, arrange a separately approved maintenance window first. A
snapshot is point-in-time; writes after it are not captured by this script.

Snapshot failures stop before NAT/RDS deletion. If a later step fails, AWS actions
already completed are not rolled back. Retain the receipt and inspect live state
before any retry; the script intentionally refuses partially deleted target states
and existing output files. Snapshot/database waiters allow up to approximately one
hour each; NAT deletion up to thirty minutes. A timeout is not proof of failure.

Preserved resources can still cost money: S3, manual snapshots and retained backups,
Secrets Manager, ECR images, CloudWatch logs, Lambda/API Gateway usage, and other
public IPv4 resources. The inventory is not a bill or a zero-cost guarantee.
AWS-managed RDS network interfaces/addresses may disappear as part of RDS deletion;
this script does not explicitly release any allocation other than the listed NAT EIP.

## Recreate RDS

Keep the manual snapshot, its KMS key, subnet group, security groups, IAM role,
ECR image, and private receipt accessible. Preview using the **execution receipt**:

```powershell
.\.venv\Scripts\python.exe scripts/recreate_aws.py --dry-run --receipt artifacts/teardown_execution_receipt.json --expected-account <AWS_ACCOUNT_ID>
```

The restore preview requires the manual snapshot to exist and be available, and
requires the target DB identifier to be absent. It cannot validate a future restore
from a dry-run teardown plan because that snapshot has not been created.

After separate approval, add `--execute` and type exactly `RESTORE github-rag-db`.
The script restores only RDS from the manual snapshot and waits for availability.
It reports the new endpoint. It never creates a NAT/EIP or changes Lambda/secrets.

Before enabling the demo again, separately review and approve:

- Restored data, engine/version, encryption/KMS access, storage, backup retention,
  maintenance windows, parameter groups, monitoring and security configuration.
  The receipt records original settings; restoring RDS does not promise every
  runtime setting is identical. Inspect these before accepting new writes.
- A **new NAT gateway and EIP** for private-subnet outbound access. Released IDs
  and public IPs cannot be assumed reusable. Replace the old NAT default route.
- Lambda subnet/security-group configuration if the existing networking is no
  longer suitable. Check database ingress from the Lambda security group.
- The new RDS endpoint and any necessary API environment/secret updates. Do not
  print credentials. Verify health and cited/refusal/safety behavior before use.

The manual snapshot preserves PostgreSQL data and embeddings, so restoration does
not require re-embedding merely to recover those stored vectors. S3 Bronze remains
an independent preserved raw-data copy.
