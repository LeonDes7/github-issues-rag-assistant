"""Read-only real-source preflight; never runs loaders or embedding requests."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from rag_assistant import load_bronze_to_rds as silver
from rag_assistant import embed_issue_chunks as gold
from rag_assistant.repository_scope import DEFAULT_REPOSITORIES, selected_repositories


def main(*, confirmed=False):
    if not confirmed:
        raise SystemExit('Refusing to run without --confirm-idempotency')
    settings = silver.required_environment()
    repos = selected_repositories(DEFAULT_REPOSITORIES)
    sources, source_counts, rejected = silver.read_bronze_records(
        silver.create_s3_client(settings), settings['S3_BUCKET'], repos
    )
    cleaned, validation = silver.validate_and_clean(sources, source_counts)
    chunks = gold.build_issue_chunks(cleaned)
    options = silver.database_options(settings)
    options['options'] = '-c default_transaction_read_only=on -c statement_timeout=120000'
    with psycopg.connect(**options) as conn:
        assert conn.execute('SHOW transaction_read_only').fetchone()[0] == 'on'
        existing, stored, reusable, tokens = gold.count_existing_embeddings(conn, chunks)
        counts = conn.execute('''SELECT count(*), coalesce(sum(jsonb_array_length(comments)),0),
            coalesce(sum(comment_count),0) FROM public.github_issues_clean
            WHERE repository = ANY(%s)''', (repos,)).fetchone()
        totals = gold.table_totals(conn, repos)
        changed = gold.load_issue_rows(conn, None, repositories=repos)
        pending = gold.load_issue_rows(conn, None, repositories=repos, pending_only=True)
    total_tokens = sum(c.token_count for c in chunks)
    result = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'read_only_preflight_not_replay', 'repositories': repos,
        'silver_issues': counts[0], 'silver_comments': counts[1],
        'stored_comment_count_sum': counts[2], 'gold_totals': totals,
        'bronze_source_records': len(sources), 'bronze_clean_issues': len(cleaned),
        'bronze_parse_rejections': rejected,
        'bronze_validation_rejections': validation['rejected_records'],
        'expected_chunks_from_bronze': len(chunks), 'existing_chunk_rows': existing,
        'stored_embeddings_for_desired_chunks': stored, 'reusable_embeddings': reusable,
        'estimated_pending_chunks_after_load': len(chunks) - reusable,
        'estimated_pending_tokens_after_load': total_tokens - tokens,
        'current_embedding_selected_issues': len(changed),
        'current_pending_issues': len(pending),
        'safe_zero_call_candidate': reusable == len(chunks) and not pending,
        'openai_expected_cost_usd_if_zero_call_guards_pass': 0,
        'aws_incremental_cost': 'S3 LIST/GET and possible transfer; not yet priced. Existing infrastructure billing continues.',
    }
    path = Path('docs/deployment/preflights/idempotency_preflight.json')
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-idempotency', action='store_true', required=True)
    args = parser.parse_args()
    main(confirmed=args.confirm_idempotency)
