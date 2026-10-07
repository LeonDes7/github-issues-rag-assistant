"""Render checkpoint 2 evidence with explicitly labeled cause hypotheses."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAUSES = {
    1119: "Approximate vector candidate miss, with related-topic competition. Exact rank is 3 but live top 5 omits it. Gold comments explain GET-only routing versus a POST request; FastAPI #793 covers the same 405 symptom. The question omits Starlette and GET/POST detail. Gold body and comments are intact; no evidence of a missing chunk.",
    2071: "Approximate vector candidate miss. Gold body is exact rank 1 but live results focus on related Starlette WebSocket limits/disconnects. The body explicitly says larger base64 video frames disconnect the client. Gold body is intact; the linked Uvicorn issue is related evidence outside this indexed corpus.",
    4598: "Related issue ambiguity and comment-versus-body competition. Exact gold rank is 36. The question omits the proposed Field blank/not_allow_empty option; #1626 discusses empty strings and returns three chunks. Gold answers are in comments (min_length=1 and Annotated[str, MinLen(1)]), while its body describes a feature request. This is an exact-gold miss, not proof all retrieved evidence is useless.",
    7461: "Approximate vector candidate miss. The exact rank-1 gold comment discusses adding arguments to errors()/json(); other comments describe filtering input keys and include_input. The live top 5 contains general FastAPI/Starlette exception topics instead. The body and all 14 gold chunks are present; the specific identifier is not sufficient to rescue approximate retrieval.",
    5108: "Vague roles wording favors authorization topics, plus repeated chunks crowd out gold (exact rank 6). The actual issue is nested many-to-many response validation with missing resources -> roles fields. Four top-five chunks come from authorization issue #5676. Gold body spans multiple chunks, some without repeated context; the detailed solution (optional roles/default_factory=list) is a comment. Chunk splitting is a plausible contributor, not proven causal.",
    4999: "Related parse_obj issues and repeated comments crowd out gold (exact rank 10). Four top-five chunks are #1287's recursive parsing discussion. Gold specifically reports hanging indefinitely with no ValidationError in an async function. The question asks what happened without naming the hang. Its long body is split into two chunks; the second lacks repeated issue context, but the first retains the symptom and title. Chunking is plausible, not proven.",
    4108: "Related schema issues and comment competition. Exact gold rank is 7; top 5 contains three #1417 chunks and two #1164 chunks. The question omits the distinguishing numeric-versus-boolean/OpenAPI schema-version debate. Gold explanatory comments clarify that behavior depends on schema version. Gold body and comments exist; no missing evidence observed.",
    11491: "Approximate vector candidate miss plus questionable evaluation question. Gold body is exact rank 1 but approximate top 5 returns FastAPI documentation/refactoring discussions. Gold has one short body, no comments: it says the serialization concepts page is not well organized and links external PRs. The requested specific organizational issues are not listed in indexed text. This needs human review; do not silently relabel the case.",
    14502: "Identical-content issue ambiguity. All five retrieved issues and gold have title 'Performance issue' and body 'Slow response under load'. Exact gold rank is 8. Issue metadata/context differentiates their vectors, but the question cannot distinguish these sources. This exact-ID miss can retrieve text that answers the question. Repository aliases (fastapi/fastapi and tiangolo/fastapi) also appear; no deduplication or fixture changes made.",
}


def main():
    evidence = json.loads((ROOT / "retrieval_miss_evidence.json").read_text())
    lines = ["# Checkpoint 2: nine retrieval misses", "",
             "Baseline top-five issue lists are preserved in order, including repeated issues (each position is a chunk). Live top-five issue lists reproduce all nine misses. Ranks below are chunk ranks, not deduplicated issue ranks. Exact ranks use fresh cached question embeddings and an exhaustive cosine-distance count; approximate ranks use the production query with LIMIT 100 and are a separate diagnostic, not the original LIMIT 5 ranking. No generation calls or application changes were made.", "",
             "## Rank and lexical summary", "",
             "| Gold | Exact vector rank | Approximate rank (LIMIT 100) | OR FTS rank | OR matching chunks | Best OR chunk |",
             "|---|---:|---:|---:|---:|---|"]
    for item in evidence:
        gold = item["gold"]
        loose = item["lexical"]["loose"]
        lines.append(f"| {gold['repository']}#{gold['issue_number']} | {item['exact_vector_gold_rank']} | {item.get('approximate_vector_gold_rank_with_limit_100') or 'not returned'} | {loose['gold_best_chunk_rank']} | {loose['candidate_count']} | {loose['gold_best_chunk']['chunk_type']} |")
    lines += ["", "Strict plainto_tsquery and plain websearch_to_tsquery return zero candidates for every miss. OR matching uses English normalized non-stopword lexemes, ranked by ts_rank_cd with chunk_id as a deterministic tie-breaker. It matches gold chunks for 9/9 misses, but retrieves gold in the lexical top 5 for 0/9. The current hybrid candidate pool is only five chunks per branch; with that pool, none of these OR gold chunks reaches RRF. These lexical checks do not establish improved hybrid metrics.", "",
              "## Per-case evidence and cause hypotheses", ""]
    for item in evidence:
        gold = item["gold"]
        lines += [f"### {gold['repository']}#{gold['issue_number']}", "", f"Question: {item['question']}", "", "Baseline vector top five:", ""]
        for rank, retrieved in enumerate(item["baseline_top5"], 1):
            source = next(s for s in item["sources"] if s["issue"] and s["issue"]["repository"] == retrieved["repository"] and s["issue"]["issue_number"] == retrieved["issue_number"])
            title = source["issue"]["title"]
            live = item["live_vector_top5"][rank - 1]
            lines.append(f"{rank}. {retrieved['repository']}#{retrieved['issue_number']} — {title} ({live['chunk_type']}; similarity {live['similarity_score']:.6f}).")
        lines += ["", "Best guess: " + CAUSES[gold["issue_number"]], "", "Best exact-vector gold chunk: " + item["exact_vector_gold_chunk"]["source_url"], "",
                  "OR FTS top five: " + ", ".join(f"{r['repository']}#{r['issue_number']}" for r in item["lexical"]["loose"]["top5"]), ""]
    lines += ["## Cause groups (overlap allowed)", "",
              "- Exact-versus-approximate retrieval gaps: 4 cases (#1119, #2071, #7461, #11491), with exact gold ranks 3, 1, 1, 1 but absent from the live approximate top 5.",
              "- Related issues, vague wording, repeated chunks/comment competition: 4 main cases (#4598, #5108, #4999, #4108); #1119 also has a related 405 discussion.",
              "- Identical source text: 1 case (#14502); top-five sources answer the same symptom but fail exact-ID scoring.",
              "- Question asks for details missing from indexed evidence: 1 flagged case (#11491). Human review remains empty; no labels changed.",
              "- Possible chunking contribution: #5108 and #4999 have body continuation chunks without repeated context. No missing gold body/comment chunks were observed, and this audit does not prove chunk size caused the misses.", "",
              "## Confidence interaction", "",
              "api.retrieval_score uses the first result's retrieval_score. Vector mode sets that to cosine similarity; hybrid mode sets it to normalized RRF: sum(1/(60+rank))/(2/61). Therefore the fixed 0.5370554072220923 cutoff is not vector-similarity-based in hybrid mode. A candidate at rank 1 in both branches scores 1.0 irrespective of its absolute similarity. With strict FTS empty, vector rank 1 scores 0.5 and is refused. Broader FTS overlap can push unrelated queries above the cutoff. Lexical-only chunks also currently get similarity_score=0 rather than a computed cosine. Checkpoint 3 must report the frozen-cutoff behavior explicitly, without tuning on the 15 unanswerables.", "",
              "## Reproduction", "",
              "```powershell", ".\\.venv\\Scripts\\python.exe scripts/analyze_retrieval_misses.py",
              ".\\.venv\\Scripts\\python.exe scripts/rank_retrieval_misses.py",
              ".\\.venv\\Scripts\\python.exe scripts/report_retrieval_misses.py",
              ".\\.venv\\Scripts\\python.exe -m unittest discover -s tests", "```", "",
              "The rank script reuses ignored .question_embeddings.json. Without that cache it stops unless --approved-embedding-run is explicitly supplied after cost approval. This run used 1,211 embedding input tokens, estimated $0.00002422 at the repository-recorded $0.02/million rate; no chat model was used. Re-running the evidence collector resets rank fields; re-run the rank script afterward.", ""]
    (ROOT / "retrieval_miss_analysis.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
