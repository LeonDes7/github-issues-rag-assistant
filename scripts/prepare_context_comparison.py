"""Freeze ten old/new API contexts and estimate generation cost. No paid calls."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import psycopg
import tiktoken
from openai import OpenAI
from rag_assistant import api, evaluate

ROOT = Path(__file__).resolve().parents[1]


def main():
    settings = api.get_settings()
    cases = evaluate.load_cases(ROOT / "evaluation/evaluation_cases.generated.jsonl")
    cache = json.loads((ROOT / ".question_embeddings.json").read_text())
    wanted = {("tiangolo/fastapi", n) for n in (5108, 2071, 618)} | {("encode/starlette", n) for n in (408, 542, 383)} | {("pydantic/pydantic", n) for n in (4999, 4108, 7461, 8499)}
    chosen = [c for c in cases if c["expected_issues"] and (c["expected_issues"][0]["repository"], c["expected_issues"][0]["issue_number"]) in wanted]
    if len(chosen) != 10:
        available = [(c["case_id"], c["expected_issues"]) for c in cases if not c["expected_abstain"]]
        raise RuntimeError(f"Need exactly ten selected cases: {available}")
    report = {"model": "gpt-5-nano", "reasoning_effort": "minimal", "max_completion_tokens": 1200, "input_usd_per_million": 0.05, "output_usd_per_million": 0.4, "generation_calls": 20, "openai_paid_calls": 0, "cases": []}
    encoding = tiktoken.get_encoding("o200k_base")
    total_tokens = 0
    with psycopg.connect(**evaluate.database_options(settings)) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        for case in chosen:
            if cache["questions"][case["case_id"]] != case["question"]:
                raise RuntimeError("Cached question mismatch")
            entry = {"case_id": case["case_id"], "question": case["question"], "contexts": {}}
            for mode in ("chunks", "issues"):
                chunks = api.retrieve_context(conn, cache["vectors"][case["case_id"]], 5, context_mode=mode)
                if api.should_refuse(chunks, 0.5370554072220923):
                    raise RuntimeError("Selected case would be refused")
                capture = MagicMock()
                capture.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content="Captured"))]
                api.generate_grounded_answer_with_usage(capture, report["model"], case["question"], chunks)
                messages = capture.chat.completions.create.call_args.kwargs["messages"]
                tokens = sum(len(encoding.encode(m["content"])) for m in messages) + 16
                total_tokens += tokens
                entry["contexts"][mode] = {"chunks": chunks, "messages": messages, "estimated_input_tokens": tokens}
            report["cases"].append(entry)
    report["estimated_input_tokens"] = total_tokens
    report["estimated_cost_usd_at_400_output_tokens_per_call"] = (total_tokens * 0.05 + 20 * 400 * 0.4) / 1e6
    report["estimated_max_cost_usd_at_output_cap"] = (total_tokens * 0.05 + 20 * 1200 * 0.4) / 1e6
    (ROOT / "docs/experiments/context/context_comparison_inputs.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    # Models retrieval checks access without generating tokens.
    client = OpenAI(api_key=settings["OPENAI_API_KEY"], max_retries=0)
    print("Available model:", client.models.retrieve(report["model"]).id)


if __name__ == "__main__":
    main()
