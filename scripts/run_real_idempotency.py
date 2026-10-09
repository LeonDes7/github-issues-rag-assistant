"""Authorized step-1 replay. Metadata preflight, pinned reads, atomic guarded DB replay."""
import argparse
import hashlib
import io
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import boto3
import psycopg
from botocore.config import Config
from rag_assistant import load_bronze_to_rds as silver
from rag_assistant import embed_issue_chunks as gold
from rag_assistant.repository_scope import DEFAULT_REPOSITORIES, selected_repositories

OUT = Path('docs/deployment/live/idempotency_live_results.json')
REPORT = OUT.with_name('idempotency_live_report.md')
STATE = {'status': 'running', 'phase': 'startup', 'snapshots': {}, 'passes': [],
         'openai_requests': 0, 'openai_cost_usd': 0, 'delete_attempts': 0}
STOP = threading.Event()
DONE = threading.Event()
PREFLIGHT_DONE = threading.Event()
START = time.monotonic()


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(STATE, indent=2, default=str) + '\n', encoding='utf-8')


def progress(phase):
    STATE['phase'] = phase
    print(f"{datetime.now(timezone.utc).isoformat()} {phase}", flush=True)


def check():
    if STOP.is_set():
        raise RuntimeError(STATE.get('abort_reason', 'Safety guard triggered'))


def heartbeat():
    while not DONE.wait(60):
        print(f"PROGRESS elapsed={int(time.monotonic()-START)}s phase={STATE['phase']} "
              f"downloaded={STATE.get('downloaded_objects', 0)}", flush=True)
        if STATE['phase'].startswith('preflight') and time.monotonic()-START >= 600:
            STATE['abort_reason'] = '10-minute preflight cap exceeded'
            STOP.set()


def preflight_deadline():
    if not PREFLIGHT_DONE.wait(600):
        STATE.update(status='blocked', committed=False,
                     abort_reason='10-minute preflight cap exceeded')
        save()
        REPORT.write_text('# Real-database idempotency replay\n\nBLOCKED: 10-minute preflight cap exceeded. No replay runs or database writes.\n', encoding='utf-8')
        print('BLOCKED: 10-minute preflight cap exceeded', flush=True)
        os._exit(1)


def inventory(client, bucket, repos):
    items = {}
    counts = {}
    for repo in repos:
        check()
        prefix = 'bronze/github/repo=' + re.sub(r'[^A-Za-z0-9_.-]', '__', repo) + '/issue='
        count = 0
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix):
            check()
            for item in page.get('Contents', []):
                if item['Key'].endswith('.json'):
                    items[item['Key']] = (item['ETag'], item['Size'], str(item['LastModified']))
                    count += 1
        legacy = dict(silver.BRONZE_SOURCES)[repo] + 'issues.jsonl'
        head = client.head_object(Bucket=bucket, Key=legacy)
        items[legacy] = (head['ETag'], head['ContentLength'], str(head['LastModified']))
        counts[repo] = {'issue_objects': count, 'legacy_objects': 1}
    return items, counts


class FrozenS3:
    def __init__(self, objects, manifest):
        self.objects, self.manifest = objects, manifest

    def list_objects_v2(self, **kwargs):
        check()
        return {'Contents': [{'Key': k} for k in sorted(self.manifest)
                             if k.startswith(kwargs['Prefix'])], 'IsTruncated': False}

    def get_object(self, **kwargs):
        check()
        return {'Body': io.BytesIO(self.objects[kwargs['Key']])}


class GuardCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, parameters=None):
        check()
        if sql in (silver.CREATE_TABLE_SQL, silver.ALTER_TABLE_SQL):
            # Schema is validated up front; do not execute even IF NOT EXISTS DDL.
            return self
        if sql != silver.UPSERT_SQL and not str(sql).lstrip().upper().startswith(('SELECT ', 'SHOW ')):
            if re.search(r'\b(DELETE|DROP|TRUNCATE)\b', str(sql), re.I):
                STATE['delete_attempts'] += 1
            raise RuntimeError('SQL rejected by replay allowlist')
        self.cursor.execute(sql, parameters)
        return self

    def executemany(self, *args, **kwargs):
        raise RuntimeError('Unexpected bulk write rejected')


class SharedConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return GuardCursor(self.connection.cursor())

    def execute(self, sql, parameters=None):
        return self.cursor().execute(sql, parameters)

    def commit(self):
        # Keep both passes atomic; only the runner may commit after assertions.
        check()


def snapshot(conn):
    check()
    with conn.cursor() as cur:
        cur.execute('''SELECT repository, count(*), coalesce(sum(jsonb_array_length(comments)),0),
            coalesce(sum(comment_count),0) FROM public.github_issues_clean GROUP BY repository ORDER BY repository''')
        rows = {r[0]: {'issues': r[1], 'comments': r[2], 'stored_comment_count': r[3],
                       'chunks': 0, 'embeddings': 0} for r in cur.fetchall()}
        cur.execute('''SELECT repository, count(*), count(embedding),
            md5(string_agg(md5(chunk_id::text || '|' || chunk_text || '|' || content_hash || '|' ||
                coalesce(embedding::text,'NULL')), '' ORDER BY chunk_id))
            FROM public.github_issue_chunks GROUP BY repository ORDER BY repository''')
        fingerprints = {}
        for repo, chunks, embeddings, fingerprint in cur.fetchall():
            rows.setdefault(repo, {'issues': 0, 'comments': 0, 'stored_comment_count': 0})
            rows[repo].update(chunks=chunks, embeddings=embeddings)
            fingerprints[repo] = fingerprint
    selected = {k: sum(rows.get(repo, {}).get(k, 0) for repo in DEFAULT_REPOSITORIES)
                for k in ('issues', 'comments', 'chunks', 'embeddings')}
    return {'selected_counts': selected, 'by_repository': rows, 'embedding_fingerprints': fingerprints}


def no_delete(conn, rows):
    if rows:
        STATE['delete_attempts'] += 1
        raise RuntimeError('Nonempty chunk deletion request blocked')


def no_openai(*args, **kwargs):
    STATE['openai_requests'] += 1
    raise RuntimeError('Unexpected OpenAI request blocked before network access')


def main(*, confirmed=False):
    if not confirmed:
        raise SystemExit('Refusing to run without --confirm-idempotency')
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=preflight_deadline, daemon=True).start()
    conn = None
    try:
        progress('preflight: verify RDS')
        settings = silver.required_environment()
        repos = selected_repositories(DEFAULT_REPOSITORIES)
        STATE['repositories'] = repos
        session = boto3.Session(region_name=settings['AWS_DEFAULT_REGION'])
        config = Config(connect_timeout=10, read_timeout=30, retries={'total_max_attempts': 1}, max_pool_connections=16)
        rds = session.client('rds', config=config)
        instances = [db for page in rds.get_paginator('describe_db_instances').paginate()
                     for db in page['DBInstances']
                     if db.get('Endpoint', {}).get('Address') == settings['PGHOST']]
        if len(instances) != 1:
            raise RuntimeError('Configured database endpoint does not uniquely match an RDS instance')
        db = instances[0]
        STATE['rds_status'] = db['DBInstanceStatus']
        if db['DBInstanceStatus'] != 'available' or db['Endpoint']['Address'] != settings['PGHOST']:
            raise RuntimeError('RDS is not available or configured endpoint does not match')
        s3 = session.client('s3', config=config)
        bucket = settings['S3_BUCKET']
        progress('preflight: per-prefix object metadata inventory')
        manifest, counts = inventory(s3, bucket, repos)
        STATE['source_object_counts'] = counts
        STATE['manifest_sha256'] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        STATE['source_bytes'] = sum(v[1] for v in manifest.values())
        if time.monotonic() - START >= 600:
            raise RuntimeError('10-minute preflight cap exceeded')
        options = silver.database_options(settings)
        options['options'] = '-c statement_timeout=120000 -c lock_timeout=10000'
        conn = psycopg.connect(**options)
        # Validate required schema without changing it.
        conn.execute('SELECT repository, issue_number, updated_at, content_hash, comments, comment_count FROM public.github_issues_clean LIMIT 0')
        conn.execute('SELECT chunk_id, repository, issue_number, content_hash, chunk_text, embedding, search_vector FROM public.github_issue_chunks LIMIT 0')
        pending = conn.execute('SELECT count(*) FROM public.github_issue_chunks WHERE repository = ANY(%s) AND embedding IS NULL', (repos,)).fetchone()[0]
        if pending:
            raise RuntimeError(f'Unexpected pending embeddings: {pending}')
        conn.commit()
        STATE['preflight_seconds'] = round(time.monotonic()-START, 3)
        check()
        PREFLIGHT_DONE.set()
        save()
        progress('replay: download pinned source objects once (not preflight)')
        objects = {}

        def download(key):
            check()
            response = s3.get_object(Bucket=bucket, Key=key, IfMatch=manifest[key][0])
            if response['ETag'] != manifest[key][0]:
                raise RuntimeError('Source ETag changed during download')
            with response['Body'] as body:
                payload = body.read()
            if len(payload) != manifest[key][1]:
                raise RuntimeError('Source size changed during download')
            return key, payload

        with ThreadPoolExecutor(max_workers=16) as pool:
            for key, payload in pool.map(download, manifest):
                check()
                objects[key] = payload
                STATE['downloaded_objects'] = len(objects)
        frozen = FrozenS3(objects, manifest)

        def verify_sources():
            current, _ = inventory(s3, bucket, repos)
            if current != manifest:
                STATE['abort_reason'] = 'Source metadata changed'
                STOP.set()
                check()

        def monitor():
            while not DONE.wait(60):
                try:
                    verify_sources()
                except Exception:
                    STATE['abort_reason'] = 'Source changed or source monitor failed'
                    STOP.set()
                    return

        verify_sources()
        threading.Thread(target=monitor, daemon=True).start()
        progress('replay: lock existing tables and capture baseline')
        conn.execute('LOCK TABLE public.github_issues_clean, public.github_issue_chunks IN SHARE ROW EXCLUSIVE MODE')
        shared = SharedConnection(conn)
        STATE['snapshots']['baseline'] = snapshot(conn)
        with ExitStack() as stack:
            stack.enter_context(patch.object(psycopg, 'connect', return_value=shared))
            stack.enter_context(patch.object(silver, 'create_s3_client', return_value=frozen))
            stack.enter_context(patch.object(gold, 'prepare_chunk_table', lambda connection: check()))
            stack.enter_context(patch.object(gold, 'delete_issue_chunks', no_delete))
            stack.enter_context(patch.object(gold, 'OpenAI', no_openai))
            for number in (1, 2):
                verify_sources()
                progress(f'pass {number}: Bronze to Silver loader')
                loaded = silver.run_load(repositories=repos)
                STATE['passes'].append({'pass': number, 'loader': loaded})
                pending = conn.execute('SELECT count(*) FROM public.github_issue_chunks WHERE repository = ANY(%s) AND embedding IS NULL', (repos,)).fetchone()[0]
                if pending:
                    raise RuntimeError('Unexpected pending embeddings after loader')
                changed = gold.load_issue_rows(shared, None, repositories=repos)
                if gold.build_issue_chunks(changed):
                    raise RuntimeError('Changed chunkable issues would require deletion or regeneration')
                progress(f'pass {number}: production embedding step')
                embedded = gold.run_embedding(limit=None, repositories=repos)
                STATE['passes'][-1]['embedding'] = embedded
                if embedded['actual_embedding_api_calls'] or embedded['embeddings_stored']:
                    raise RuntimeError('Unexpected regenerated embeddings')
                STATE['snapshots'][f'pass_{number}'] = snapshot(conn)
                verify_sources()
                save()
        baseline, first, second = (STATE['snapshots'][name] for name in ('baseline', 'pass_1', 'pass_2'))
        if first != second:
            raise RuntimeError('Counts or fingerprints differ between pass 1 and pass 2')
        if baseline['embedding_fingerprints'] != second['embedding_fingerprints']:
            raise RuntimeError('Baseline embedding fingerprint changed')
        if baseline['by_repository'].get('fastapi/fastapi') != second['by_repository'].get('fastapi/fastapi'):
            raise RuntimeError('Retained alias counts changed')
        if any(r['comments'] != r['stored_comment_count'] for r in second['by_repository'].values()):
            raise RuntimeError('Stored comment counts disagree with JSON arrays')
        check()
        conn.commit()
        STATE.update(status='pass', committed=True, embedding_fingerprint_comparison='baseline = pass 1 = pass 2',
                     baseline_counts_unchanged=baseline['selected_counts'] == second['selected_counts'])
        progress('complete: step 1 PASS')
    except Exception as exc:
        if conn is not None:
            conn.rollback()
        # No credentials, URLs, source bodies or raw exception text in the report.
        STATE.update(status='blocked', committed=False, error_type=type(exc).__name__)
        if isinstance(exc, RuntimeError):
            STATE['abort_reason'] = str(exc)
        else:
            STATE.setdefault('abort_reason', 'Service or database operation failed; no pass claimed')
        progress('complete: step 1 BLOCKED')
    finally:
        DONE.set()
        PREFLIGHT_DONE.set()
        if conn is not None:
            conn.close()
        STATE['elapsed_seconds'] = round(time.monotonic()-START, 3)
        save()
        lines = ['# Real-database idempotency replay', '', f"Status: **{STATE['status'].upper()}**. OpenAI cost: $0. No deletes, AWS resource changes, pushes or deployment.", '',
                 '| Checkpoint | Issues | Comments | Chunks | Embeddings |', '|---|---:|---:|---:|---:|']
        for label, snap in STATE['snapshots'].items():
            c = snap['selected_counts']
            lines.append(f"| {label} | {c['issues']} | {c['comments']} | {c['chunks']} | {c['embeddings']} |")
        for item in STATE['passes']:
            lines.append(f"\nPass {item['pass']}: inserted {item['loader']['rows_inserted']}, updated {item['loader']['rows_updated']}.")
        lines.append('\nEmbedding fingerprint comparison: ' + STATE.get('embedding_fingerprint_comparison', 'not established'))
        lines.append('\n' + STATE.get('abort_reason', 'Both production entrypoints completed twice against the real database.'))
        lines.append('\nSource bodies downloaded once using pinned ETags, cached for both passes; metadata inventories rechecked. Schema preparation bypassed after validation; production upsert and embedding selection retained. Both passes held in one transaction with write locks; concurrent-writer behavior and crash recovery are not tested. Guards enforce a SQL allowlist in the client, not a server-installed policy. S3/transfer costs are unquantified.')
        REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return 0 if STATE['status'] == 'pass' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-idempotency', action='store_true', required=True)
    args = parser.parse_args()
    raise SystemExit(main(confirmed=args.confirm_idempotency))
