"""Create idempotent text chunks and OpenAI embeddings for issue retrieval."""

import argparse
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
import tiktoken
from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TABLE_NAME = "public.github_issue_chunks"
MODEL = "text-embedding-3-small"
VECTOR_DIMENSIONS = 1536
CHUNK_TOKENS = 700
CHUNK_OVERLAP_TOKENS = 100
EMBEDDING_BATCH_SIZE = 100
MAX_RETRIES = 5
EMBEDDING_COST_PER_MILLION_TOKENS_USD = 0.02
CHUNK_NAMESPACE = uuid.UUID("816415d9-0263-4ba5-b33a-8f786794bd5e")
FENCED_BLOCK_PATTERN = re.compile(
    r"(?P<fenced>^[ \t]*(?:```|~~~)[^\n]*\n.*?^[ \t]*(?:```|~~~)[ \t]*$)",
    re.MULTILINE | re.DOTALL,
)

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    chunk_id UUID PRIMARY KEY,
    repository TEXT NOT NULL,
    issue_number BIGINT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL CHECK (
        chunk_type IN ('issue_body', 'comment', 'heuristic_resolution')
    ),
    chunk_text TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english'::regconfig, chunk_text)
    ) STORED,
    embedding vector({VECTOR_DIMENSIONS}),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT github_issue_chunks_issue_fk
        FOREIGN KEY (repository, issue_number)
        REFERENCES public.github_issues_clean (repository, issue_number)
        ON DELETE CASCADE,
    CONSTRAINT github_issue_chunks_identity_unique
        UNIQUE (repository, issue_number, chunk_type, chunk_index)
)
"""

ALTER_TABLE_SQL = f"""
ALTER TABLE {TABLE_NAME}
    ADD COLUMN IF NOT EXISTS content_hash TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english'::regconfig, chunk_text)
    ) STORED
"""

CREATE_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS github_issue_chunks_embedding_hnsw_idx
ON {TABLE_NAME} USING hnsw (embedding vector_cosine_ops)
"""

CREATE_FULL_TEXT_INDEX_SQL = f"""
CREATE INDEX IF NOT EXISTS github_issue_chunks_search_vector_gin_idx
ON {TABLE_NAME} USING gin (search_vector)
"""

ISSUES_QUERY = """
SELECT repository, issue_number, title, body, github_url, comments,
       resolution_text, resolution_confidence, content_hash
FROM public.github_issues_clean
WHERE NOT EXISTS (
    SELECT 1
    FROM public.github_issue_chunks AS chunks
    WHERE chunks.repository = github_issues_clean.repository
      AND chunks.issue_number = github_issues_clean.issue_number
)
OR EXISTS (
    SELECT 1
    FROM public.github_issue_chunks AS chunks
    WHERE chunks.repository = github_issues_clean.repository
      AND chunks.issue_number = github_issues_clean.issue_number
      AND chunks.content_hash IS DISTINCT FROM github_issues_clean.content_hash
)
ORDER BY repository, issue_number
"""
ALL_ISSUES_QUERY = """
SELECT repository, issue_number, title, body, github_url, comments,
       resolution_text, resolution_confidence, content_hash
FROM public.github_issues_clean
ORDER BY repository, issue_number
"""

UPSERT_CHUNK_SQL = f"""
INSERT INTO {TABLE_NAME} AS existing (
    chunk_id, repository, issue_number, chunk_index, chunk_type, chunk_text,
    source_url, content_hash, embedding
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL)
ON CONFLICT (repository, issue_number, chunk_type, chunk_index) DO UPDATE SET
    chunk_id = EXCLUDED.chunk_id,
    chunk_text = EXCLUDED.chunk_text,
    source_url = EXCLUDED.source_url,
    content_hash = EXCLUDED.content_hash,
    embedding = CASE
        WHEN existing.chunk_text IS DISTINCT FROM EXCLUDED.chunk_text
          OR existing.content_hash IS DISTINCT FROM EXCLUDED.content_hash
        THEN NULL
        ELSE existing.embedding
    END
"""


@dataclass(frozen=True)
class IssueChunk:
    chunk_id: uuid.UUID
    repository: str
    issue_number: int
    chunk_index: int
    chunk_type: str
    chunk_text: str
    source_url: str
    content_hash: str
    token_count: int


def required_environment() -> dict[str, str]:
    load_dotenv(PROJECT_ROOT / ".env")
    required = (
        "OPENAI_API_KEY",
        "PGHOST",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required .env settings: {', '.join(missing)}")
    try:
        port = int(os.getenv("PGPORT", "5432"))
    except ValueError as exc:
        raise ValueError("PGPORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PGPORT must be between 1 and 65535")
    return {
        **{name: os.environ[name] for name in required},
        "PGPORT": str(port),
        "PGSSLMODE": os.getenv("PGSSLMODE", "require"),
    }


def database_options(settings: dict[str, str]) -> dict[str, Any]:
    return {
        "host": settings["PGHOST"],
        "port": int(settings["PGPORT"]),
        "dbname": settings["PGDATABASE"],
        "user": settings["PGUSER"],
        "password": settings["PGPASSWORD"],
        "sslmode": settings["PGSSLMODE"],
        "connect_timeout": 10,
    }


def token_encoder():
    return tiktoken.encoding_for_model(MODEL)


def text_atoms(text: str) -> list[str]:
    atoms: list[str] = []
    position = 0
    for match in FENCED_BLOCK_PATTERN.finditer(text):
        if match.start() > position:
            atoms.extend(
                paragraph
                for paragraph in re.split(r"(?<=\n\n)", text[position : match.start()])
                if paragraph
            )
        atoms.append(match.group("fenced"))
        position = match.end()
    if position < len(text):
        atoms.extend(
            paragraph
            for paragraph in re.split(r"(?<=\n\n)", text[position:])
            if paragraph
        )
    return atoms or [text]


def split_long_atom(atom: str, encoder: Any) -> list[str]:
    token_ids = encoder.encode(atom)
    if len(token_ids) <= CHUNK_TOKENS:
        return [atom]
    pieces: list[str] = []
    start = 0
    while start < len(token_ids):
        end = min(start + CHUNK_TOKENS, len(token_ids))
        pieces.append(encoder.decode(token_ids[start:end]))
        if end == len(token_ids):
            break
        start = end - CHUNK_OVERLAP_TOKENS
    return pieces


def chunk_text(text: str, encoder: Any) -> list[tuple[str, int]]:
    atoms: list[str] = []
    for atom in text_atoms(text):
        atoms.extend(split_long_atom(atom, encoder))

    chunks: list[tuple[str, int]] = []
    buffer = ""
    for atom in atoms:
        candidate = f"{buffer}{atom}" if buffer else atom
        if buffer and len(encoder.encode(candidate)) > CHUNK_TOKENS:
            buffer_ids = encoder.encode(buffer)
            chunks.append((buffer, len(buffer_ids)))
            atom_ids = encoder.encode(atom)
            overlap_size = min(
                CHUNK_OVERLAP_TOKENS,
                max(0, CHUNK_TOKENS - len(atom_ids)),
            )
            overlap = encoder.decode(buffer_ids[-overlap_size:]) if overlap_size else ""
            buffer = f"{overlap}{atom}"
        else:
            buffer = candidate
    if buffer.strip():
        chunks.append((buffer, len(encoder.encode(buffer))))
    return chunks


def build_issue_chunks(rows: list[dict[str, Any]]) -> list[IssueChunk]:
    encoder = token_encoder()
    chunks: list[IssueChunk] = []
    for row in rows:
        repository = row["repository"]
        issue_number = int(row["issue_number"])
        title = row["title"] or "(untitled issue)"
        prefix = f"Repository: {repository}\nIssue: #{issue_number}\nTitle: {title}\n\n"
        indices = {"issue_body": 0, "comment": 0, "heuristic_resolution": 0}
        sources: list[tuple[str, str, str]] = []

        if isinstance(row["body"], str) and row["body"].strip():
            sources.append(("issue_body", row["body"], row["github_url"]))

        comments = row["comments"] or []
        if not isinstance(comments, list):
            raise ValueError(
                f"Comments for {repository}#{issue_number} are not a JSON array"
            )
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            body = comment.get("body")
            if not isinstance(body, str) or not body.strip():
                continue
            sources.append(
                (
                    "comment",
                    body,
                    comment.get("html_url") or row["github_url"],
                )
            )

        resolution = row["resolution_text"]
        if isinstance(resolution, str) and resolution.strip():
            confidence = row["resolution_confidence"] or "unspecified"
            sources.append(
                (
                    "heuristic_resolution",
                    f"[Low-confidence heuristic resolution; not ground truth. "
                    f"Stored confidence: {confidence}]\n{resolution}",
                    row["github_url"],
                )
            )

        for chunk_type, source_text, source_url in sources:
            contextual_text = prefix + source_text.strip()
            for text, count in chunk_text(contextual_text, encoder):
                chunk_index = indices[chunk_type]
                indices[chunk_type] += 1
                identity = (
                    f"{repository}\0{issue_number}\0{chunk_type}\0{chunk_index}"
                )
                chunk_id = uuid.uuid5(CHUNK_NAMESPACE, identity)
                chunks.append(
                    IssueChunk(
                        chunk_id=chunk_id,
                        repository=repository,
                        issue_number=issue_number,
                        chunk_index=chunk_index,
                        chunk_type=chunk_type,
                        chunk_text=text,
                        source_url=source_url,
                        content_hash=row.get("content_hash", ""),
                        token_count=count,
                    )
                )
    return chunks


def load_issue_rows(
    connection: psycopg.Connection[Any],
    limit: int | None,
    changed_only: bool = True,
) -> list[dict[str, Any]]:
    query = ISSUES_QUERY if changed_only else ALL_ISSUES_QUERY
    parameters: tuple[int, ...] = ()
    if limit is not None:
        query += "\nLIMIT %s"
        parameters = (limit,)
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        columns = [description.name for description in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def prepare_chunk_table(connection: psycopg.Connection[Any]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(CREATE_TABLE_SQL)
        cursor.execute(ALTER_TABLE_SQL)
        cursor.execute(CREATE_INDEX_SQL)
        cursor.execute(CREATE_FULL_TEXT_INDEX_SQL)
    connection.commit()


def delete_issue_chunks(
    connection: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
) -> None:
    identities = list(
        dict.fromkeys((row["repository"], row["issue_number"]) for row in rows)
    )
    if not identities:
        return
    values_sql = ", ".join(["(%s, %s)"] * len(identities))
    parameters = [value for identity in identities for value in identity]
    with connection.cursor() as cursor:
        cursor.execute(
            f"DELETE FROM {TABLE_NAME} "
            f"WHERE (repository, issue_number) IN ({values_sql})",
            parameters,
        )


def persist_chunk_rows(
    connection: psycopg.Connection[Any],
    chunks: list[IssueChunk],
) -> None:
    with connection.cursor() as cursor:
        for chunk in chunks:
            cursor.execute(
                UPSERT_CHUNK_SQL,
                (
                    chunk.chunk_id,
                    chunk.repository,
                    chunk.issue_number,
                    chunk.chunk_index,
                    chunk.chunk_type,
                    chunk.chunk_text,
                    chunk.source_url,
                    chunk.content_hash,
                ),
            )
    connection.commit()


def get_pending_chunks(
    connection: psycopg.Connection[Any],
    chunks: list[IssueChunk],
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    chunk_ids = list(dict.fromkeys(chunk.chunk_id for chunk in chunks))
    values_sql = ", ".join(["%s"] * len(chunk_ids))
    query = f"""
        SELECT chunk_id, chunk_text
        FROM {TABLE_NAME}
        WHERE embedding IS NULL
          AND chunk_id IN ({values_sql})
        ORDER BY repository, issue_number, chunk_type, chunk_index
    """
    with connection.cursor() as cursor:
        cursor.execute(query, chunk_ids)
        return [
            {"chunk_id": row[0], "chunk_text": row[1]}
            for row in cursor.fetchall()
        ]


def embed_pending_chunks(
    connection: psycopg.Connection[Any],
    client: OpenAI,
    pending: list[dict[str, Any]],
) -> tuple[int, int, int]:
    tokens_used = 0
    api_calls = 0
    failed_chunks = 0
    for batch_start in range(0, len(pending), EMBEDDING_BATCH_SIZE):
        batch = pending[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
        response = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = client.embeddings.create(
                    model=MODEL,
                    input=[item["chunk_text"] for item in batch],
                    dimensions=VECTOR_DIMENSIONS,
                )
                break
            except (RateLimitError, APIConnectionError) as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(
                        f"Embedding batch failed after {MAX_RETRIES + 1} attempts"
                    ) from exc
                time.sleep(min(60.0, 2.0**attempt))
            except APIStatusError as exc:
                if exc.status_code < 500 or attempt == MAX_RETRIES:
                    raise RuntimeError(
                        f"OpenAI embeddings request failed with HTTP "
                        f"{exc.status_code}"
                    ) from exc
                time.sleep(min(60.0, 2.0**attempt))

        if response is None:
            raise RuntimeError("OpenAI embeddings request returned no response")
        api_calls += 1
        tokens_used += response.usage.prompt_tokens
        if len(response.data) != len(batch):
            raise RuntimeError(
                "OpenAI returned a different number of embeddings than inputs"
            )
        with connection.cursor() as cursor:
            for item in response.data:
                vector = item.embedding
                if len(vector) != VECTOR_DIMENSIONS:
                    raise RuntimeError(
                        f"Expected {VECTOR_DIMENSIONS} embedding dimensions, "
                        f"received {len(vector)}"
                    )
                vector_literal = "[" + ",".join(str(value) for value in vector) + "]"
                cursor.execute(
                    f"UPDATE {TABLE_NAME} SET embedding = %s::vector "
                    "WHERE chunk_id = %s AND embedding IS NULL",
                    (vector_literal, batch[item.index]["chunk_id"]),
                )
        connection.commit()
    return tokens_used, api_calls, failed_chunks


def count_existing_embeddings(
    connection: psycopg.Connection[Any],
    chunks: list[IssueChunk],
) -> tuple[int, int]:
    if not chunks:
        return 0, 0
    unique_chunks = list({chunk.chunk_id: chunk for chunk in chunks}.values())
    values_sql = ", ".join(["(%s, %s)"] * len(unique_chunks))
    parameters = [
        value
        for chunk in unique_chunks
        for value in (chunk.chunk_id, chunk.chunk_text)
    ]
    query = f"""
        WITH desired(chunk_id, chunk_text) AS (VALUES {values_sql})
        SELECT COUNT(existing.chunk_id),
               COUNT(existing.chunk_id) FILTER (
                   WHERE existing.embedding IS NOT NULL
                     AND existing.chunk_text = desired.chunk_text
               )
        FROM desired
        LEFT JOIN {TABLE_NAME} AS existing USING (chunk_id)
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            existing_rows, embedded_rows = cursor.fetchone()
            return existing_rows, embedded_rows
    except psycopg.errors.UndefinedTable:
        connection.rollback()
        return 0, 0


def summarize_chunks(chunks: list[IssueChunk]) -> dict[str, Any]:
    by_type: dict[str, int] = {
        "issue_body": 0,
        "comment": 0,
        "heuristic_resolution": 0,
    }
    for chunk in chunks:
        by_type[chunk.chunk_type] += 1
    token_count = sum(chunk.token_count for chunk in chunks)
    return {
        "chunk_count": len(chunks),
        "chunks_by_type": by_type,
        "estimated_input_tokens": token_count,
        "estimated_embedding_api_calls": (
            (len(chunks) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE
        ),
        "estimated_cost_usd": round(
            token_count * EMBEDDING_COST_PER_MILLION_TOKENS_USD / 1_000_000,
            8,
        ),
    }


def similarity_search_examples(
    connection: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    query = f"""
        WITH seeds AS (
            SELECT DISTINCT ON (repository, issue_number)
                   chunk_id, repository, issue_number, chunk_type, embedding
            FROM {TABLE_NAME}
            WHERE embedding IS NOT NULL
            ORDER BY repository, issue_number, chunk_type, chunk_index
            LIMIT 3
        )
        SELECT seeds.repository, seeds.issue_number, seeds.chunk_type,
               nearest.repository, nearest.issue_number, nearest.chunk_type,
               nearest.source_url, nearest.cosine_similarity
        FROM seeds
        CROSS JOIN LATERAL (
            SELECT chunk.repository, chunk.issue_number, chunk.chunk_type,
                   chunk.source_url,
                   1 - (chunk.embedding <=> seeds.embedding) AS cosine_similarity
            FROM {TABLE_NAME} AS chunk
            WHERE chunk.embedding IS NOT NULL
              AND (chunk.repository, chunk.issue_number)
                  <> (seeds.repository, seeds.issue_number)
            ORDER BY chunk.embedding <=> seeds.embedding
            LIMIT 1
        ) AS nearest
        ORDER BY seeds.repository, seeds.issue_number
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()
    return [
        {
            "query_issue": {
                "repository": row[0],
                "issue_number": row[1],
                "chunk_type": row[2],
            },
            "similar_issue": {
                "repository": row[3],
                "issue_number": row[4],
                "chunk_type": row[5],
                "source_url": row[6],
                "similarity": float(row[7]),
            },
        }
        for row in rows
    ]


def table_totals(connection: psycopg.Connection[Any]) -> dict[str, Any]:
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT COUNT(DISTINCT (repository, issue_number)),
                   COUNT(*),
                   COUNT(embedding)
            FROM {TABLE_NAME}
            """
        )
        issues, chunks, embeddings = cursor.fetchone()
        cursor.execute(
            f"""
            SELECT chunk_type, COUNT(*), COUNT(embedding)
            FROM {TABLE_NAME}
            GROUP BY chunk_type
            ORDER BY chunk_type
            """
        )
        by_type = {
            chunk_type: {"chunks": chunk_count, "embeddings": embedding_count}
            for chunk_type, chunk_count, embedding_count in cursor.fetchall()
        }
    return {
        "issues_with_chunks": issues,
        "total_chunks": chunks,
        "total_embeddings": embeddings,
        "chunks_and_embeddings_by_type": by_type,
    }


def run_embedding(
    limit: int | None = 25,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = required_environment()
    with psycopg.connect(**database_options(settings)) as connection:
        if dry_run:
            rows = load_issue_rows(connection, limit, changed_only=False)
        else:
            prepare_chunk_table(connection)
            rows = load_issue_rows(connection, limit, changed_only=True)
        chunks = build_issue_chunks(rows)
        estimate = summarize_chunks(chunks)
        result: dict[str, Any] = {
            "issues_processed": len(rows),
            "issues_selected": len(rows),
            "model": MODEL,
            **estimate,
        }
        if dry_run:
            if connection.execute(
                "SELECT to_regclass(%s)",
                (TABLE_NAME,),
            ).fetchone()[0]:
                existing_rows, embedded_rows = count_existing_embeddings(
                    connection,
                    chunks,
                )
                result["existing_chunk_rows"] = existing_rows
                result["existing_embeddings"] = embedded_rows
                result["estimated_pending_chunks"] = max(
                    0,
                    estimate["chunk_count"] - embedded_rows,
                )
                result["estimated_embedding_api_calls"] = (
                    result["estimated_pending_chunks"] + EMBEDDING_BATCH_SIZE - 1
                ) // EMBEDDING_BATCH_SIZE
            result["dry_run"] = True
            return result

        if not chunks:
            if dry_run:
                return result
            result.update(
                {
                    "embeddings_stored": 0,
                    "failed_or_skipped_chunks": 0,
                    "failed_chunks": 0,
                    "skipped_chunks_already_embedded": 0,
                    "input_tokens_used": 0,
                    "actual_embedding_api_calls": 0,
                    "table_totals": table_totals(connection),
                    "similarity_search_examples": [],
                }
            )
            return result

        delete_issue_chunks(connection, rows)
        persist_chunk_rows(connection, chunks)
        pending = get_pending_chunks(connection, chunks)
        client = OpenAI(api_key=settings["OPENAI_API_KEY"], max_retries=0)
        tokens_used, api_calls, failed_chunks = embed_pending_chunks(
            connection,
            client,
            pending,
        )
        result.update(
            {
                "chunks_by_type": estimate["chunks_by_type"],
                "embeddings_stored": len(pending) - failed_chunks,
                "failed_or_skipped_chunks": failed_chunks,
                "failed_chunks": failed_chunks,
                "skipped_chunks_already_embedded": len(chunks) - len(pending),
                "input_tokens_used": tokens_used,
                "actual_embedding_api_calls": api_calls,
                "estimated_cost_usd": round(
                    tokens_used
                    * EMBEDDING_COST_PER_MILLION_TOKENS_USD
                    / 1_000_000,
                    8,
                ),
                "cost_rate_usd_per_million_tokens": (
                    EMBEDDING_COST_PER_MILLION_TOKENS_USD
                ),
                "table_totals": table_totals(connection),
                "similarity_search_examples": similarity_search_examples(
                    connection
                ),
            }
        )
        return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chunk clean GitHub issues and store OpenAI embeddings in RDS."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum clean issues to process (default: 25)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate chunk counts/tokens without writes or OpenAI requests",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be a positive integer")
    try:
        print(json.dumps(run_embedding(args.limit, args.dry_run), indent=2))
    except (psycopg.Error, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Chunking/embedding failed: {exc}") from exc


if __name__ == "__main__":
    main()
