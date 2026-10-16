"""Streamlit UI for the authenticated GitHub issues RAG API."""

import os
from contextlib import nullcontext
import re
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from requests import RequestException
from streamlit.errors import StreamlitSecretNotFoundError

from rag_assistant.ui_client import RagApiError, ask_api
from rag_assistant.redaction import UNSAFE_SETTINGS_ANSWER, safe_display_payload
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


EXAMPLES = (
    ("WebSocket video frames", "What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?"),
    ("Dependency conflicts", "What is the recommended workaround for the dependency issue between graphene and aniso8601 when installing starlette[full]?"),
    ("Pydantic parsing", "What unexpected behavior occurred when the reporter called `.parse_obj()` in an async loop?"),
)
ABSTENTIONS = {
    "There isn't enough evidence in the indexed issues to answer this question.",
    "The retrieved excerpts do not provide enough evidence to answer this question.",
}


def _choose_example(question: str) -> None:
    st.session_state["question"] = question
    st.session_state.pop("rag_result", None)
    st.session_state.pop("rag_result_question", None)


def _answer_state(result: dict[str, Any]) -> str:
    answer = result.get("answer", "")
    if answer == UNSAFE_SETTINGS_ANSWER:
        return "blocked"
    if isinstance(answer, str) and answer in ABSTENTIONS:
        return "abstained"
    sources = result.get("citations", [])
    refs = [int(n) for n in re.findall(r"\[(\d+)\]", answer)] if isinstance(answer, str) else []
    if isinstance(sources, list) and refs and all(
        1 <= n <= len(sources) and isinstance(sources[n - 1], dict) for n in refs
    ):
        return "cited"
    return "uncited"


def _show_result(result: dict[str, Any]) -> None:
    result = safe_display_payload(result)
    answer = result.get("answer")
    state = _answer_state(result)
    with st.container(border=True):
        st.subheader("Answer")
        if state == "blocked":
            st.error("Response withheld for safety")
        elif state == "abstained":
            st.warning("Insufficient evidence")
        elif state == "cited":
            st.success("Answer with citations")
        else:
            st.warning("Answer has no valid inline citations; check the sources before relying on it.")
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
    if state == "abstained":
        st.caption("Try asking about closed FastAPI, Starlette, or Pydantic issues.")
    elif citations:
        if state == "blocked":
            source_area = st.expander("Retrieved matches - response withheld", expanded=False)
        else:
            source_area = nullcontext()
        with source_area:
            if state not in {"abstained", "blocked"}:
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
                with st.container(border=True):
                    st.markdown(f"**[{index}] {repository} #{issue_number}**")
                    details = f"{chunk_type.replace('_', ' ')}"
                    if isinstance(score, (int, float)):
                        score_label = "RRF" if retrieval_mode == "hybrid" else "Similarity"
                        details += f" | {score_label}: {score:.3f}"
                    st.text(details)
                    if isinstance(url, str) and url.startswith("https://github.com/"):
                        st.markdown(f"[Open on GitHub]({url})")
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
    st.set_page_config(page_title="GitHub Issues Assistant", page_icon="🔎", layout="centered")
    st.markdown("""
<style>
.block-container { max-width: 880px; padding-top: 3rem; padding-bottom: 3rem; }
[data-testid="stForm"] { border-radius: 16px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
h1 { letter-spacing: -0.035em; }
</style>
""", unsafe_allow_html=True)
    with st.sidebar:
        st.title("Demo guide")
        st.markdown("**Scope**\n\nClosed FastAPI, Starlette, and Pydantic issues only.")
        st.markdown("**Evidence first**\n\nAnswers require citations. Open the linked discussions to check the evidence.")
        st.markdown("**May abstain**\n\nIf the indexed excerpts cannot support an answer, the assistant may decline.")
        st.divider()
        st.caption("Five questions per session. A shared daily demo limit also applies.")
    st.caption("GITHUB ISSUES / EVIDENCE-GROUNDED SEARCH")
    st.title("GitHub Issues Assistant")
    st.markdown("Ask about closed FastAPI, Starlette, and Pydantic issues.")
    st.caption("Explore real discussions, understand reported behavior, and follow the sources.")

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

    st.markdown("**Try an example**")
    for column, (label, prompt) in zip(st.columns(3), EXAMPLES):
        with column:
            st.button(label, on_click=_choose_example, args=(prompt,), use_container_width=True)

    with st.form("ask-form", clear_on_submit=False):
        question = st.text_area(
            "Your question", key="question", height=120,
            max_chars=4000,
            placeholder="What issue are you trying to understand?",
        )
        with st.expander("Search options"):
            top_k = st.slider("Sources to retrieve", min_value=1, max_value=20, value=5)
        submitted = st.form_submit_button("Search issues", type="primary", use_container_width=True)

    # Replace the whole previous result, including source cards, as one unit.
    result_area = st.empty()
    if submitted:
        result_area.empty()
        st.session_state.pop("rag_result", None)
        st.session_state.pop("rag_result_question", None)
        if not question.strip():
            st.warning("Enter a question before selecting Search issues.")
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
            with st.spinner("Searching indexed issues and preparing an evidence-based response..."):
                st.session_state["rag_result"] = ask_api(
                    api_url,
                    api_token,
                    question.strip(),
                    top_k,
                )
                st.session_state["rag_result_question"] = question.strip()
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
        with result_area.container():
            result_question = st.session_state.get("rag_result_question")
            if result_question:
                st.text(f"Results for: {result_question}")
            _show_result(result)

    st.divider()
    st.markdown("**About this demo**")
    st.caption(
        "Recorded corpus: 9,555 closed issues / 43,535 comments / 63,002 chunks. "
        "This is a fixed issue corpus, not live documentation. Answers may be incomplete "
        "or incorrect; check the cited discussions. Similarity is a retrieval score, "
        "not confidence that an answer is correct."
    )


if __name__ == "__main__":
    main()
