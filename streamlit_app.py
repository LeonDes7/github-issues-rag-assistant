"""Streamlit UI for the authenticated GitHub issues RAG API."""

import os
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from requests import RequestException
from streamlit.errors import StreamlitSecretNotFoundError

from rag_assistant.ui_client import RagApiError, ask_api
from rag_assistant.redaction import safe_display_payload
from rag_assistant.demo_guard import reserve_question
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_API_URL = "https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com"


def _setting(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, os.getenv(name, default))
    except StreamlitSecretNotFoundError:
        value = os.getenv(name, default)
    return str(value).strip()


def _show_result(result: dict[str, Any]) -> None:
    result = safe_display_payload(result)
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        st.warning("The API returned no answer.")
    else:
        st.markdown(answer)

    citations = result.get("citations", [])
    retrieval_metadata = result.get("retrieval_metadata", {})
    retrieval_mode = (
        retrieval_metadata.get("retrieval_mode")
        if isinstance(retrieval_metadata, dict)
        else "vector"
    )
    if not isinstance(citations, list):
        citations = []
    citations = [
        {key: value for key, value in citation.items()
         if key not in {"predicted_category", "classification_confidence"}}
        if isinstance(citation, dict) else citation
        for citation in citations
    ]
    if citations:
        st.subheader("Retrieved GitHub sources")
        st.caption(
            "These sources were retrieved for your question. Their presence does "
            "not establish an answer when the evidence is insufficient."
        )
        for index, citation in enumerate(citations, start=1):
            if not isinstance(citation, dict):
                continue
            repository = citation.get("repository", "unknown repository")
            issue_number = citation.get("issue_number", "unknown")
            url = citation.get("source_url") or citation.get("issue_url")
            chunk_type = citation.get("chunk_type", "evidence")
            score = (
                citation.get("retrieval_score")
                if retrieval_mode == "hybrid"
                else citation.get("similarity_score")
            )
            label = f"[{index}] {repository}#{issue_number} — {chunk_type}"
            if isinstance(score, (int, float)):
                score_label = "RRF" if retrieval_mode == "hybrid" else "similarity"
                label += f" · {score_label} {score:.3f}"
            if isinstance(url, str) and url.startswith("https://github.com/"):
                st.markdown(f"- [{label}]({url})")
            else:
                st.markdown(f"- {label}")
    else:
        st.info("No issue citations were retrieved for this answer.")

    with st.expander("Retrieval details and debug information"):
        st.json(
            {
                "retrieval_metadata": result.get("retrieval_metadata", {}),
                "performance": result.get("performance", {}),
                "citations": citations,
            }
        )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    st.set_page_config(page_title="GitHub Issues Assistant", page_icon="🔎")
    st.title("GitHub Issues Assistant")
    st.caption(
        "Ask about FastAPI, Starlette, and Pydantic issues. Answers use retrieved "
        "issue evidence and include source links."
    )

    api_url = _setting("RAG_API_URL", DEFAULT_API_URL)
    api_token = _setting("API_AUTH_TOKEN")
    if not api_token:
        st.error(
            "The app is missing its server-side API_AUTH_TOKEN secret. "
            "Configure it in Streamlit Community Cloud settings."
        )
        return
    if not api_url.startswith("https://"):
        st.error("RAG_API_URL must use HTTPS.")
        return

    with st.form("ask-form", clear_on_submit=False):
        question = st.text_area(
            "Your question",
            max_chars=4000,
            placeholder="For example: How do I configure middleware?",
        )
        top_k = st.slider("Evidence chunks to retrieve", min_value=1, max_value=20, value=5)
        submitted = st.form_submit_button("Ask", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Enter a question before selecting Ask.")
            return
        try:
            limit_message = reserve_question(st.session_state, PROJECT_ROOT / "artifacts/demo_quota.sqlite3")
        except (sqlite3.Error, OSError):
            st.warning("The demo is temporarily unavailable. Please try again later.")
            return
        if limit_message:
            st.info(limit_message)
            return
        try:
            with st.spinner("Searching GitHub issue evidence and drafting an answer…"):
                st.session_state["rag_result"] = ask_api(
                    api_url,
                    api_token,
                    question.strip(),
                    top_k,
                )
        except RagApiError as exc:
            if exc.status_code == 401:
                st.error(
                    "The API rejected its bearer token (401). Check the "
                    "server-side API_AUTH_TOKEN in Streamlit Cloud secrets."
                )
            elif exc.status_code >= 500:
                st.error(
                    f"The RAG backend returned HTTP {exc.status_code}. "
                    "Please try again later."
                )
            else:
                st.error(f"The RAG API returned HTTP {exc.status_code}.")
            st.session_state.pop("rag_result", None)
            return
        except RequestException:
            st.error(
                "Could not reach the RAG backend. Check the API URL or try again "
                "when the service is available."
            )
            st.session_state.pop("rag_result", None)
            return
        except ValueError:
            st.error("The RAG backend returned a response the app could not read.")
            st.session_state.pop("rag_result", None)
            return

    result: Any = st.session_state.get("rag_result")
    if isinstance(result, dict):
        _show_result(result)


if __name__ == "__main__":
    main()
