"""Run the frozen twenty-call comparison only after explicit cost approval."""
import argparse
import json
from pathlib import Path

from openai import OpenAI
from rag_assistant import api

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-budget-usd", type=float, required=True)
    args = parser.parse_args()
    prepared = json.loads((ROOT / "context_comparison_inputs.json").read_text())
    if not 0 < args.approved_budget_usd <= 0.02 or prepared["generation_calls"] != 20 or len(prepared["cases"]) != 10:
        raise RuntimeError("Invalid approved budget or experiment size")
    if prepared["estimated_max_cost_usd_at_output_cap"] > args.approved_budget_usd:
        raise RuntimeError("Prepared run exceeds approved budget")
    output = ROOT / "context_comparison_answers.json"
    if output.exists():
        raise RuntimeError("Results already exist; refusing to repeat paid calls")
    client = OpenAI(api_key=api.get_settings()["OPENAI_API_KEY"], max_retries=0, timeout=90)
    results = {"model": prepared["model"], "approved_budget_usd": args.approved_budget_usd, "measured_cost_usd": 0, "answers": []}
    for case in prepared["cases"]:
        for mode, context in case["contexts"].items():
            next_max = (context["estimated_input_tokens"] * 0.05 + 1200 * 0.4) / 1e6
            if results["measured_cost_usd"] + next_max > args.approved_budget_usd:
                raise RuntimeError("Remaining budget insufficient")
            response = client.chat.completions.create(model=prepared["model"], messages=context["messages"], reasoning_effort="minimal", max_completion_tokens=1200)
            choice = response.choices[0]
            usage = response.usage
            cost = (usage.prompt_tokens * 0.05 + usage.completion_tokens * 0.4) / 1e6
            results["measured_cost_usd"] += cost
            results["answers"].append({"case_id": case["case_id"], "question": case["question"], "mode": mode, "answer": api.clean_generated_answer(choice.message.content or "", [c["chunk_text"] for c in context["chunks"]]), "citations": [{"citation": f"[{i}]", "url": c["source_url"], "issue_url": c["issue_url"]} for i, c in enumerate(context["chunks"], 1)], "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens, "finish_reason": choice.finish_reason, "cost_usd": cost})
            output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(case["case_id"], mode, "saved", flush=True)
            if choice.finish_reason != "stop" or not choice.message.content:
                raise RuntimeError("Incomplete answer saved; no automatic retry")
    def cell(answer):
        text = answer["answer"].replace("|", "\\|").replace("\n", "<br>")
        links = " ".join(f'[{c["citation"]}]({c["url"]})' for c in answer["citations"])
        return text + "<br>Sources: " + links
    lines = ["# Old versus distinct-issue context", "", "Same questions, model and prompt; context selection differs. Human quality review is pending.", "", "| Question | Old: five chunks | New: five issues |", "|---|---|---|"]
    for case in prepared["cases"]:
        answers = {a["mode"]: a for a in results["answers"] if a["case_id"] == case["case_id"]}
        lines.append(f'| {case["question"].replace("|", "\\|")} | {cell(answers["chunks"])} | {cell(answers["issues"])} |')
    (ROOT / "context_comparison_answers.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Measured cost USD:", results["measured_cost_usd"])


if __name__ == "__main__":
    main()
