"""AWS Lambda entry point for the scheduled incremental ingestion pipeline."""

from typing import Any

from rag_assistant.incremental_pipeline import run_pipeline


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return run_pipeline()
