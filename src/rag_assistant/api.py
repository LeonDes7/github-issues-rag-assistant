"""Local FastAPI retrieval-and-generation API for GitHub issue chunks."""

import json
import logging
import math
import os
import re
import secrets
import time
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
import psycopg
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, Field, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_GENERATION_MODEL = "gpt-4o-mini"
DEFAULT_CORS_ORIGINS = "http://localhost:8501,http://127.0.0.1:8501"
VECTOR_DIMENSIONS = 1536
DEFAULT_CONFIDENCE_THRESHOLD = 0.5370554072220923
DEFAULT_EMBEDDING_COST_PER_MILLION_TOKENS_USD = 0.02
DEFAULT_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD = 0.15
DEFAULT_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD = 0.60
LOW_EVIDENCE_ANSWER = (
    "There isn't enough evidence in the indexed issues to answer this question."
)
LOGGER = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)

GROUNDED_ANSWER_PROMPT = """You are a trustworthy assistant for GitHub issues. Answer the user’s question only using the retrieved issue excerpts below.

Rules:
- Do not invent facts, fixes, commands, or citations.
- If the retrieved evidence is insufficient, say that clearly.
- Treat heuristic resolution chunks as low-confidence evidence.
- Cite every factual claim with [1], [2], and so on, matching the supplied sources.
- Keep the answer concise and technical.

Retrieved evidence:
{retrieved_chunks}"""


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class Citation(BaseModel):
    repository: str
    issue_number: int
    issue_url: str
    source_url: str
    chunk_type: str
    similarity_score: float
    retrieval_score: float
    predicted_category: str | None = None
    classification_confidence: str | None = None


class RetrievalMetadata(BaseModel):
    top_k: int
    retrieved_count: int
    embedding_model: str
    generation_model: str
    retrieval_mode: str
    confidence_threshold: float


class PerformanceMetadata(BaseModel):
    retrieval_latency_ms: float
    llm_latency_ms: float
    total_latency_ms: float
    embedding_tokens: int
    generation_prompt_tokens: int
    generation_completion_tokens: int
    estimated_cost_usd: float


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieval_metadata: RetrievalMetadata
    performance: PerformanceMetadata


def load_settings() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    runtime_secrets = _load_runtime_secrets()
    required = (
        "OPENAI_API_KEY",
        "PGHOST",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
        "API_AUTH_TOKEN",
    )
    values = {
        key: runtime_secrets.get(key, os.getenv(key))
        for key in required
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required settings: {', '.join(missing)}")

    port_text = os.getenv("PGPORT", "5432")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("PGPORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("PGPORT must be between 1 and 65535")

    embedding_model = os.getenv(
        "OPENAI_EMBEDDING_MODEL",
        DEFAULT_EMBEDDING_MODEL,
    ).strip()
    generation_model = os.getenv(
        "OPENAI_GENERATION_MODEL",
        DEFAULT_GENERATION_MODEL,
    ).strip()
    if not embedding_model or not generation_model:
        raise RuntimeError("OpenAI model settings must not be empty")

    origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            DEFAULT_CORS_ORIGINS,
        ).split(",")
        if origin.strip()
    ]
    if not origins:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must contain at least one origin")
    retrieval_mode = os.getenv("RAG_RETRIEVAL_MODE", "vector").strip().lower()
    if retrieval_mode not in {"vector", "hybrid"}:
        raise RuntimeError("RAG_RETRIEVAL_MODE must be 'vector' or 'hybrid'")
    confidence_threshold = _float_setting(
        "RAG_CONFIDENCE_THRESHOLD",
        DEFAULT_CONFIDENCE_THRESHOLD,
    )
    if not 0 <= confidence_threshold <= 1:
        raise RuntimeError("RAG_CONFIDENCE_THRESHOLD must be between 0 and 1")

    return {
        **values,
        "PGPORT": port,
        "PGSSLMODE": os.getenv("PGSSLMODE", "require"),
        "OPENAI_EMBEDDING_MODEL": embedding_model,
        "OPENAI_GENERATION_MODEL": generation_model,
        "CORS_ALLOWED_ORIGINS": origins,
        "RAG_RETRIEVAL_MODE": retrieval_mode,
        "RAG_CONFIDENCE_THRESHOLD": confidence_threshold,
        "OPENAI_EMBEDDING_COST_PER_MILLION_TOKENS_USD": _float_setting(
            "OPENAI_EMBEDDING_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_EMBEDDING_COST_PER_MILLION_TOKENS_USD,
        ),
        "OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD": _float_setting(
            "OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD,
        ),
        "OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD": _float_setting(
            "OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD,
        ),
    }


def _float_setting(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise RuntimeError(f"{name} must be a finite non-negative number")
    return parsed


def retrieval_score(retrieved: list[dict[str, Any]]) -> float:
    if not retrieved:
        return 0.0
    score = retrieved[0].get(
        "retrieval_score",
        retrieved[0].get("similarity_score", 0.0),
    )
    if not isinstance(score, (float, int)) or not math.isfinite(score):
        return 0.0
    return min(1.0, max(0.0, float(score)))


def should_refuse(
    retrieved: list[dict[str, Any]],
    confidence_threshold: float,
) -> bool:
    return not retrieved or retrieval_score(retrieved) < confidence_threshold


def estimate_request_cost(
    settings: dict[str, Any],
    embedding_tokens: int,
    generation_prompt_tokens: int,
    generation_completion_tokens: int,
) -> float:
    embedding_cost = (
        embedding_tokens
        * settings.get(
            "OPENAI_EMBEDDING_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_EMBEDDING_COST_PER_MILLION_TOKENS_USD,
        )
        / 1_000_000
    )
    generation_cost = (
        generation_prompt_tokens
        * settings.get(
            "OPENAI_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_GENERATION_INPUT_COST_PER_MILLION_TOKENS_USD,
        )
        + generation_completion_tokens
        * settings.get(
            "OPENAI_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD",
            DEFAULT_GENERATION_OUTPUT_COST_PER_MILLION_TOKENS_USD,
        )
    ) / 1_000_000
    return round(embedding_cost + generation_cost, 10)


def _load_runtime_secrets() -> dict[str, str]:
    secret_arn = os.getenv("RAG_SECRETS_ARN")
    if not secret_arn:
        return {}
    response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("RAG_SECRETS_ARN must reference a text JSON secret")
    secret_values = json.loads(secret_string)
    if not isinstance(secret_values, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in secret_values.items()
    ):
        raise RuntimeError("RAG secret must be a JSON object containing string values")
    return secret_values


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    return load_settings()


def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings["OPENAI_API_KEY"], max_retries=2)


def require_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected_token = get_settings()["API_AUTH_TOKEN"]
    if credentials is None or not secrets.compare_digest(
        credentials.credentials,
        expected_token,
    ):
        raise HTTPException(
            status_code=401,
            detail="Valid bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_db_connection() -> Generator[psycopg.Connection[Any], None, None]:
    settings = get_settings()
    connection = psycopg.connect(
        host=settings["PGHOST"],
        port=settings["PGPORT"],
        dbname=settings["PGDATABASE"],
        user=settings["PGUSER"],
        password=settings["PGPASSWORD"],
        sslmode=settings["PGSSLMODE"],
        connect_timeout=10,
    )
    try:
        yield connection
    finally:
        connection.close()


def retrieve_chunks(
    connection: psycopg.Connection[Any],
    embedding: list[float],
    top_k: int,
    retrieval_mode: str = "vector",
    query_text: str | None = None,
) -> list[dict[str, Any]]:
    vector_literal = "[" + ",".join(str(value) for value in embedding) + "]"
    if retrieval_mode == "vector":
        query = """
            SELECT chunks.repository, chunks.issue_number, issues.github_url,
                   chunks.source_url, chunks.chunk_type, chunks.chunk_text,
                   1 - (chunks.embedding <=> %s::vector) AS similarity_score,
                   1 - (chunks.embedding <=> %s::vector) AS retrieval_score,
                   classifications.label, classifications.confidence
            FROM public.github_issue_chunks AS chunks
            JOIN public.github_issues_clean AS issues
              ON issues.repository = chunks.repository
             AND issues.issue_number = chunks.issue_number
            LEFT JOIN public.github_issue_classifications AS classifications
              ON classifications.repository = chunks.repository
             AND classifications.issue_number = chunks.issue_number
             AND classifications.classification_method = 'heuristic'
             AND classifications.classifier_version = 'heuristic-v1'
            WHERE chunks.embedding IS NOT NULL
            ORDER BY chunks.embedding <=> %s::vector
            LIMIT %s
        """
        parameters = (vector_literal, vector_literal, vector_literal, top_k)
    elif retrieval_mode == "hybrid":
        if not query_text or not query_text.strip():
            raise ValueError("query_text is required for hybrid retrieval")
        query = """
            WITH search_query AS (
                SELECT plainto_tsquery('english', %s) AS query
            ),
            vector_results AS (
                SELECT chunks.chunk_id,
                       1 - (chunks.embedding <=> %s::vector) AS similarity_score,
                       ROW_NUMBER() OVER (
                           ORDER BY chunks.embedding <=> %s::vector,
                                    chunks.chunk_id
                       ) AS rank
                FROM public.github_issue_chunks AS chunks
                WHERE chunks.embedding IS NOT NULL
                ORDER BY chunks.embedding <=> %s::vector
                LIMIT %s
            ),
            text_results AS (
                SELECT chunks.chunk_id,
                       ROW_NUMBER() OVER (
                           ORDER BY ts_rank_cd(chunks.search_vector, search_query.query)
                                    DESC,
                                    chunks.chunk_id
                       ) AS rank
                FROM public.github_issue_chunks AS chunks
                CROSS JOIN search_query
                WHERE chunks.search_vector @@ search_query.query
                ORDER BY ts_rank_cd(chunks.search_vector, search_query.query) DESC,
                         chunks.chunk_id
                LIMIT %s
            ),
            ranked_candidates AS (
                SELECT chunk_id, rank, similarity_score, 1 AS source_rank
                FROM vector_results
                UNION ALL
                SELECT chunk_id, rank, NULL::double precision, 2 AS source_rank
                FROM text_results
            ),
            fused AS (
                SELECT chunk_id,
                       MAX(similarity_score) AS similarity_score,
                       LEAST(
                           1.0,
                           SUM(1.0 / (60 + rank)) / (2.0 / 61.0)
                       ) AS retrieval_score
                FROM ranked_candidates
                GROUP BY chunk_id
            )
            SELECT chunks.repository, chunks.issue_number, issues.github_url,
                   chunks.source_url, chunks.chunk_type, chunks.chunk_text,
                   COALESCE(fused.similarity_score, 0) AS similarity_score,
                   fused.retrieval_score,
                   classifications.label, classifications.confidence
            FROM fused
            JOIN public.github_issue_chunks AS chunks USING (chunk_id)
            JOIN public.github_issues_clean AS issues
              ON issues.repository = chunks.repository
             AND issues.issue_number = chunks.issue_number
            LEFT JOIN public.github_issue_classifications AS classifications
              ON classifications.repository = chunks.repository
             AND classifications.issue_number = chunks.issue_number
             AND classifications.classification_method = 'heuristic'
             AND classifications.classifier_version = 'heuristic-v1'
            ORDER BY fused.retrieval_score DESC, chunks.chunk_id
            LIMIT %s
        """
        parameters = (
            query_text,
            vector_literal,
            vector_literal,
            vector_literal,
            top_k,
            top_k,
            top_k,
        )
    else:
        raise ValueError("retrieval_mode must be 'vector' or 'hybrid'")
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        rows = cursor.fetchall()
    return [
        {
            "repository": row[0],
            "issue_number": row[1],
            "issue_url": row[2],
            "source_url": row[3],
            "chunk_type": row[4],
            "chunk_text": row[5],
            "similarity_score": float(row[6]),
            "retrieval_score": float(row[7]),
            "predicted_category": row[8],
            "classification_confidence": row[9],
        }
        for row in rows
    ]


def generate_grounded_answer(
    client: OpenAI,
    model: str,
    question: str,
    retrieved: list[dict[str, Any]],
) -> str:
    answer, _, _ = generate_grounded_answer_with_usage(
        client,
        model,
        question,
        retrieved,
    )
    return answer


def generate_grounded_answer_with_usage(
    client: OpenAI,
    model: str,
    question: str,
    retrieved: list[dict[str, Any]],
) -> tuple[str, int, int]:
    evidence = [
        {
            "citation": f"[{index}]",
            "repository": chunk["repository"],
            "issue_number": chunk["issue_number"],
            "issue_url": chunk["issue_url"],
            "source_url": chunk["source_url"],
            "chunk_type": chunk["chunk_type"],
            "similarity_score": chunk["similarity_score"],
            "excerpt": chunk["chunk_text"],
        }
        for index, chunk in enumerate(retrieved, start=1)
    ]
    system_prompt = GROUNDED_ANSWER_PROMPT.format(
        retrieved_chunks=json.dumps(evidence, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    answer = response.choices[0].message.content
    if not answer or not answer.strip():
        raise RuntimeError("Generation model returned an empty answer")
    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    return (
        clean_generated_answer(
            answer.strip(),
            [chunk["chunk_text"] for chunk in retrieved],
        ),
        prompt_tokens if isinstance(prompt_tokens, int) else 0,
        completion_tokens if isinstance(completion_tokens, int) else 0,
    )


def _normalized_code(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_generated_answer(answer: str, evidence: list[str]) -> str:
    """Remove empty Markdown constructs and unsupported fenced code."""
    supported_evidence = [_normalized_code(excerpt) for excerpt in evidence]

    cleaned_lines: list[str] = []
    lines = answer.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        fence_match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_match:
            fence = fence_match.group(1)
            fence_char = fence[0]
            closing_index = index + 1
            while closing_index < len(lines) and not re.match(
                rf"^\s*{re.escape(fence_char)}{{{len(fence)},}}\s*$",
                lines[closing_index],
            ):
                closing_index += 1
            if closing_index == len(lines):
                index += 1
                continue
            code = "\n".join(lines[index + 1 : closing_index])
            normalized = _normalized_code(code)
            if normalized and any(
                normalized in excerpt for excerpt in supported_evidence
            ):
                cleaned_lines.extend(lines[index : closing_index + 1])
            index = closing_index + 1
            continue

        if re.match(r"^\s*(?:[-+*]|\d+[.)])\s*(?:\[[ xX]\]\s*)?$", line):
            index += 1
            continue
        cleaned_lines.append(line.rstrip())
        index += 1

    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()
    if not result:
        return "The retrieved evidence does not support a usable answer."
    return result


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Trustworthy GitHub Issues RAG API",
        version="0.1.0",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings["CORS_ALLOWED_ORIGINS"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.get("/health")
    def health(
        connection: psycopg.Connection[Any] = Depends(get_db_connection),
    ) -> dict[str, str]:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=503,
                detail="PostgreSQL is unavailable",
            ) from exc
        return {"status": "ok", "database": "reachable"}

    @application.post("/ask", response_model=AskResponse)
    def ask(
        request: AskRequest,
        _: None = Depends(require_bearer_token),
        connection: psycopg.Connection[Any] = Depends(get_db_connection),
        client: OpenAI = Depends(get_openai_client),
    ) -> AskResponse:
        request_started = time.perf_counter()
        retrieval_latency_ms = 0.0
        llm_latency_ms = 0.0
        embedding_tokens = 0
        generation_prompt_tokens = 0
        generation_completion_tokens = 0
        retrieved: list[dict[str, Any]] = []
        retrieval_mode = "vector"
        refused = False
        settings = get_settings()
        try:
            retrieval_started = time.perf_counter()
            embedding_response = client.embeddings.create(
                model=settings["OPENAI_EMBEDDING_MODEL"],
                input=request.question,
                dimensions=VECTOR_DIMENSIONS,
            )
            embedding_usage = getattr(embedding_response, "usage", None)
            embedding_tokens_value = getattr(embedding_usage, "prompt_tokens", 0)
            embedding_tokens = (
                embedding_tokens_value
                if isinstance(embedding_tokens_value, int)
                else 0
            )
            query_embedding = embedding_response.data[0].embedding
            if len(query_embedding) != VECTOR_DIMENSIONS:
                raise RuntimeError("Query embedding has an unexpected vector size")
            retrieval_mode = settings.get("RAG_RETRIEVAL_MODE", "vector")
            if retrieval_mode == "hybrid":
                retrieved = retrieve_chunks(
                    connection,
                    query_embedding,
                    request.top_k,
                    retrieval_mode="hybrid",
                    query_text=request.question,
                )
            else:
                retrieved = retrieve_chunks(
                    connection,
                    query_embedding,
                    request.top_k,
                )
            retrieval_latency_ms = (
                time.perf_counter() - retrieval_started
            ) * 1000
            confidence_threshold = settings.get(
                "RAG_CONFIDENCE_THRESHOLD",
                DEFAULT_CONFIDENCE_THRESHOLD,
            )
            refused = should_refuse(retrieved, confidence_threshold)
            if refused:
                answer = LOW_EVIDENCE_ANSWER
            else:
                llm_started = time.perf_counter()
                (
                    answer,
                    generation_prompt_tokens,
                    generation_completion_tokens,
                ) = generate_grounded_answer_with_usage(
                    client,
                    settings["OPENAI_GENERATION_MODEL"],
                    request.question,
                    retrieved,
                )
                llm_latency_ms = (time.perf_counter() - llm_started) * 1000
        except HTTPException:
            raise
        except (OpenAIError, psycopg.Error, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Retrieval or generation failed",
            ) from exc
        finally:
            total_latency_ms = (time.perf_counter() - request_started) * 1000
            estimated_cost_usd = estimate_request_cost(
                settings,
                embedding_tokens,
                generation_prompt_tokens,
                generation_completion_tokens,
            )
            LOGGER.info(
                "rag_request_metrics %s",
                json.dumps(
                    {
                        "retrieval_latency_ms": round(retrieval_latency_ms, 3),
                        "llm_latency_ms": round(llm_latency_ms, 3),
                        "total_latency_ms": round(total_latency_ms, 3),
                        "embedding_tokens": embedding_tokens,
                        "generation_prompt_tokens": generation_prompt_tokens,
                        "generation_completion_tokens": generation_completion_tokens,
                        "estimated_cost_usd": estimated_cost_usd,
                        "retrieval_mode": retrieval_mode,
                        "retrieval_score": retrieval_score(retrieved),
                        "refused": refused,
                    }
                ),
            )

        citations = [
            Citation(
                repository=chunk["repository"],
                issue_number=chunk["issue_number"],
                issue_url=chunk["issue_url"],
                source_url=chunk["source_url"],
                chunk_type=chunk["chunk_type"],
                similarity_score=chunk["similarity_score"],
                retrieval_score=chunk.get(
                    "retrieval_score",
                    chunk["similarity_score"],
                ),
                predicted_category=chunk.get("predicted_category"),
                classification_confidence=chunk.get("classification_confidence"),
            )
            for chunk in retrieved
        ]
        return AskResponse(
            answer=answer,
            citations=citations,
            retrieval_metadata=RetrievalMetadata(
                top_k=request.top_k,
                retrieved_count=len(retrieved),
                embedding_model=settings["OPENAI_EMBEDDING_MODEL"],
                generation_model=settings["OPENAI_GENERATION_MODEL"],
                retrieval_mode=retrieval_mode,
                confidence_threshold=settings.get(
                    "RAG_CONFIDENCE_THRESHOLD",
                    DEFAULT_CONFIDENCE_THRESHOLD,
                ),
            ),
            performance=PerformanceMetadata(
                retrieval_latency_ms=round(retrieval_latency_ms, 3),
                llm_latency_ms=round(llm_latency_ms, 3),
                total_latency_ms=round(total_latency_ms, 3),
                embedding_tokens=embedding_tokens,
                generation_prompt_tokens=generation_prompt_tokens,
                generation_completion_tokens=generation_completion_tokens,
                estimated_cost_usd=estimated_cost_usd,
            ),
        )

    return application


app = create_app()
