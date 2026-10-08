"""Offline preparation only: freeze the fourteen prior passes and estimate cost."""
import hashlib
import argparse
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import tiktoken
from rag_assistant import api

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_CAP = 1200


def main(final=False):
    source = ROOT / "docs/experiments/abstention/heldout_unanswerable_results.json"
    raw = source.read_bytes()
    prior = json.loads(raw)
    cases = [case for case in prior["cases"] if not case["cutoff_refused"]]
    if len(cases) != 14 or prior["cutoff"] != 0.537 or prior["retuned"]:
        raise RuntimeError("Unexpected frozen baseline")
    encoding = tiktoken.encoding_for_model("gpt-5-nano")
    prepared = []
    for case in cases:
        capture = MagicMock()
        capture.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Offline capture"))
        ]
        api.generate_grounded_answer_with_usage(
            capture, "gpt-5-nano", case["question"], case["evidence"]
        )
        messages = capture.chat.completions.create.call_args.kwargs["messages"]
        # Local text token count plus estimated Chat Completions framing.
        estimated_input = sum(len(encoding.encode(m["content"])) for m in messages) + 11
        conservative_input = sum(len(m["content"].encode("utf-8")) for m in messages) + 512
        prepared.append({
            "case_id": case["case_id"], "question": case["question"],
            "score": case["score"], "evidence": case["evidence"],
            "prior_answer": case["generated_answer"],
            "prior_review_notes": case["review_notes"],
            "prior_unsupported_answer": case["unsupported_answer"],
            "label_ambiguous": case["label_ambiguous"],
            "messages": messages, "estimated_input_tokens": estimated_input,
            "conservative_input_token_bound": conservative_input,
        })
    input_tokens = sum(c["estimated_input_tokens"] for c in prepared)
    input_bound = sum(c["conservative_input_token_bound"] for c in prepared)
    prior_output = sum(c["generation_usage"]["completion_tokens"] for c in cases)
    def cost(inputs, outputs):
        return str((Decimal(inputs) * Decimal("0.05") + Decimal(outputs) * Decimal("0.40")) / Decimal(1000000))
    result = {
        "status": "prepared_only_awaiting_user_cost_approval",
        "purpose": "Targeted auxiliary-claim and citation regression; no new headline metric",
        "baseline_sha256": hashlib.sha256(raw).hexdigest(),
        "prompt_sha256": hashlib.sha256(api.GROUNDED_ANSWER_PROMPT.encode()).hexdigest(),
        "model": "gpt-5-nano", "reasoning_effort": "minimal",
        "max_completion_tokens_per_call": OUTPUT_CAP,
        "planned_generation_calls": 14, "embedding_calls": 0, "database_calls": 0,
        "automatic_retries": 0, "cutoff": prior["cutoff"], "retuned": False,
        "retrieval_settings": prior["retrieval_settings"],
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5-nano",
        "input_usd_per_million": "0.05", "output_usd_per_million": "0.40",
        "estimated_input_tokens": input_tokens,
        "assumed_output_tokens_from_prior_run": prior_output,
        "estimated_cost_usd": cost(input_tokens, prior_output),
        "estimated_cost_at_full_output_cap_usd": cost(input_tokens, 14 * OUTPUT_CAP),
        "conservative_input_token_bound": input_bound,
        "conservative_budget_usd": cost(input_bound, 14 * OUTPUT_CAP),
        "cost_note": "Local input/framing estimate; actual usage is unknown before generation. Full output cap includes reasoning tokens. No cached-input discounts assumed. UTF-8 byte bound plus 512 framing tokens per call supplies a conservative reservation.",
        "results_path": "docs/experiments/abstention/abstention_regression_results.json",
        "comparison_report_path": "docs/experiments/abstention/abstention_regression_comparison.md",
        "review_plan": "Compare each new raw and cleaned answer with the prior answer and frozen numbered excerpts. Review abstention, each auxiliary factual claim, exact citation support, unsupported guarantees, and truncation. Preserve ambiguous labels. No paid judge calls.",
        "cases": prepared,
    }
    filename = "docs/experiments/abstention/abstention_regression_preflight.json"
    if final:
        filename = "docs/experiments/abstention/final_abstention_regression_preflight.json"
        marker_tokens = len(encoding.encode(api.ABSTENTION_MARKER)) * 14
        result.update(
            purpose="Final deterministic abstention API regression; no new headline metric",
            fixed_api_abstention_message=api.MODEL_ABSTENTION_ANSWER,
            abstention_marker=api.ABSTENTION_MARKER,
            api_source_sha256=hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest(),
            estimated_marker_only_output_tokens=marker_tokens,
            estimated_marker_only_cost_usd=cost(input_tokens, marker_tokens),
            results_path="docs/experiments/abstention/final_abstention_regression_results.json",
            comparison_report_path="docs/experiments/abstention/final_abstention_regression_comparison.md",
            review_plan=(
                "Make exactly fourteen generation calls using these frozen messages, with no retries. "
                "Save raw model responses and actual token usage. Replay each returned response through "
                "the actual local /ask endpoint using mocked OpenAI and database dependencies, "
                "a stub embedding response, and frozen retrieve_context output (no embedding or RDS calls). "
                "Verify each abstaining API answer equals the fixed message exactly, contains no inline "
                "citations or appended prose, and returns all expected structured sources separately "
                "with matching order, URLs and metadata. Flag non-abstaining or incomplete responses "
                "instead of counting them as successful abstentions. Preserve ambiguity labels. "
                "No paid judge, retrieval execution, new metrics, or latency testing; stop after report."
            ),
        )
    with (ROOT / filename).open("x" if final else "w", encoding="utf-8") as output:
        output.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true", help="Prepare a separate deterministic API regression")
    main(final=parser.parse_args().final)
