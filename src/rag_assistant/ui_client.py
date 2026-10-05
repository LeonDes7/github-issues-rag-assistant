"""HTTP client for the Streamlit interface."""

from typing import Any

import requests


class RagApiError(RuntimeError):
    """An HTTP error response returned by the RAG API."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"RAG API returned HTTP {status_code}")


def ask_api(
    api_url: str,
    api_auth_token: str,
    question: str,
    top_k: int,
) -> dict[str, Any]:
    response = requests.post(
        f"{api_url.rstrip('/')}/ask",
        json={"question": question, "top_k": top_k},
        headers={"Authorization": f"Bearer {api_auth_token}"},
        timeout=(5, 90),
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RagApiError(response.status_code) from exc
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("citations"), list):
        raise ValueError("RAG API returned an invalid response")
    return payload
