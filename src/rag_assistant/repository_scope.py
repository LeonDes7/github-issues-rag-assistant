"""One configured storage-name scope for ingestion, loading, embedding, quality."""

import os

DEFAULT_REPOSITORIES = ["tiangolo/fastapi", "encode/starlette", "pydantic/pydantic"]


def configured_repositories():
    repos = list(dict.fromkeys(r.strip() for r in os.getenv(
        "GITHUB_REPOS", ",".join(DEFAULT_REPOSITORIES)).split(",") if r.strip()))
    if not repos:
        raise ValueError("GITHUB_REPOS must contain at least one repository")
    if "fastapi/fastapi" in repos and "tiangolo/fastapi" in repos:
        raise ValueError("Configure only one FastAPI repository alias")
    return repos


def selected_repositories(repositories=None):
    configured = configured_repositories()
    if repositories is None:
        return configured
    if not repositories or any(r not in configured for r in repositories):
        raise ValueError("repositories must be a non-empty subset of GITHUB_REPOS")
    return list(dict.fromkeys(repositories))
