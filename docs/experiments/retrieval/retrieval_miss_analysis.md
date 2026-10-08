# Checkpoint 2: nine retrieval misses

Baseline top-five issue lists are preserved in order, including repeated issues (each position is a chunk). Live top-five issue lists reproduce all nine misses. Ranks below are chunk ranks, not deduplicated issue ranks. Exact ranks use fresh cached question embeddings and an exhaustive cosine-distance count; approximate ranks use the production query with LIMIT 100 and are a separate diagnostic, not the original LIMIT 5 ranking. No generation calls or application changes were made.

## Rank and lexical summary

| Gold | Exact vector rank | Approximate rank (LIMIT 100) | OR FTS rank | OR matching chunks | Best OR chunk |
|---|---:|---:|---:|---:|---|
| encode/starlette#1119 | 3 | not returned | 158 | 29241 | issue_body |
| tiangolo/fastapi#2071 | 1 | not returned | 122 | 13169 | issue_body |
| pydantic/pydantic#4598 | 36 | 28 | 2566 | 29900 | comment |
| pydantic/pydantic#7461 | 1 | not returned | 19 | 60251 | issue_body |
| tiangolo/fastapi#5108 | 6 | 6 | 9 | 60916 | issue_body |
| pydantic/pydantic#4999 | 10 | 10 | 118 | 20043 | issue_body |
| pydantic/pydantic#4108 | 7 | 7 | 733 | 24922 | issue_body |
| pydantic/pydantic#11491 | 1 | not returned | 522 | 59259 | issue_body |
| tiangolo/fastapi#14502 | 8 | 8 | 7860 | 60613 | issue_body |

Strict plainto_tsquery and plain websearch_to_tsquery return zero candidates for every miss. OR matching uses English normalized non-stopword lexemes, ranked by ts_rank_cd with chunk_id as a deterministic tie-breaker. It matches gold chunks for 9/9 misses, but retrieves gold in the lexical top 5 for 0/9. The current hybrid candidate pool is only five chunks per branch; with that pool, none of these OR gold chunks reaches RRF. These lexical checks do not establish improved hybrid metrics.

## Per-case evidence and cause hypotheses

### encode/starlette#1119

Question: What could be the reason for receiving a 405 Method Not Allowed error when trying to access the /predict endpoint?

Baseline vector top five:

1. tiangolo/fastapi#4108 — pytest error: h11._util.RemoteProtocolError: illegal request line (comment; similarity 0.570522).
2. tiangolo/fastapi#793 — Post results to Error 405 Method not Allowed (comment; similarity 0.560975).
3. tiangolo/fastapi#5291 — http/1.1 "500 Internal Server Error ERROR: Exception in ASGI application" (comment; similarity 0.532189).
4. tiangolo/fastapi#793 — Post results to Error 405 Method not Allowed (comment; similarity 0.528218).
5. tiangolo/fastapi#793 — Post results to Error 405 Method not Allowed (comment; similarity 0.526603).

Best guess: Approximate vector candidate miss, with related-topic competition. Exact rank is 3 but live top 5 omits it. Gold comments explain GET-only routing versus a POST request; FastAPI #793 covers the same 405 symptom. The question omits Starlette and GET/POST detail. Gold body and comments are intact; no evidence of a missing chunk.

Best exact-vector gold chunk: https://github.com/Kludex/starlette/issues/1119#issuecomment-765319868

OR FTS top five: encode/starlette#34, encode/starlette#3064, pydantic/pydantic#1357, encode/starlette#1870, pydantic/pydantic#5562

### tiangolo/fastapi#2071

Question: What problem did the reporter observe when sending larger base64-encoded video frames over a WebSocket?

Baseline vector top five:

1. encode/starlette#407 — WebSocket max message size (comment; similarity 0.561248).
2. encode/starlette#1369 — websocket.receive_bytes() AssertionError (comment; similarity 0.533377).
3. encode/starlette#940 — WebSocket max connection pool size ? (comment; similarity 0.521693).
4. encode/starlette#407 — WebSocket max message size (comment; similarity 0.519028).
5. encode/starlette#940 — WebSocket max connection pool size ? (comment; similarity 0.508256).

Best guess: Approximate vector candidate miss. Gold body is exact rank 1 but live results focus on related Starlette WebSocket limits/disconnects. The body explicitly says larger base64 video frames disconnect the client. Gold body is intact; the linked Uvicorn issue is related evidence outside this indexed corpus.

Best exact-vector gold chunk: https://github.com/fastapi/fastapi/issues/2071

OR FTS top five: tiangolo/fastapi#4835, tiangolo/fastapi#4025, tiangolo/fastapi#4025, tiangolo/fastapi#4834, pydantic/pydantic#8053

### pydantic/pydantic#4598

Question: What workaround is suggested for enforcing non-empty strings in Pydantic models?

Baseline vector top five:

1. pydantic/pydantic#1626 — Empty strings are not considered null values (comment; similarity 0.654454).
2. pydantic/pydantic#3295 — Empty objects should be validated as None for optional fields (comment; similarity 0.643358).
3. pydantic/pydantic#3710 — Linting error when using nested models with optional arguments (comment; similarity 0.641008).
4. pydantic/pydantic#1626 — Empty strings are not considered null values (comment; similarity 0.640287).
5. pydantic/pydantic#1626 — Empty strings are not considered null values (issue_body; similarity 0.639317).

Best guess: Related issue ambiguity and comment-versus-body competition. Exact gold rank is 36. The question omits the proposed Field blank/not_allow_empty option; #1626 discusses empty strings and returns three chunks. Gold answers are in comments (min_length=1 and Annotated[str, MinLen(1)]), while its body describes a feature request. This is an exact-gold miss, not proof all retrieved evidence is useless.

Best exact-vector gold chunk: https://github.com/pydantic/pydantic/issues/4598#issuecomment-1272246954

OR FTS top five: pydantic/pydantic#646, tiangolo/fastapi#13399, fastapi/fastapi#13399, pydantic/pydantic#1767, pydantic/pydantic#11179

### pydantic/pydantic#7461

Question: What is the proposed workaround for the issue with hide_input_in_errors not working in error.json() and error.errors()?

Baseline vector top five:

1. tiangolo/fastapi#1909 — Custom exception handler + await request.json() == hanging service (comment; similarity 0.441107).
2. tiangolo/fastapi#1909 — Custom exception handler + await request.json() == hanging service (comment; similarity 0.422615).
3. encode/starlette#1175 — Custom 500 or Exception handlers do not run through middleware like other handled exceptions. (comment; similarity 0.421953).
4. tiangolo/fastapi#227 — Custom response format for validation error (comment; similarity 0.417052).
5. encode/starlette#1116 — Error are not reported using CORS middleware (comment; similarity 0.415554).

Best guess: Approximate vector candidate miss. The exact rank-1 gold comment discusses adding arguments to errors()/json(); other comments describe filtering input keys and include_input. The live top 5 contains general FastAPI/Starlette exception topics instead. The body and all 14 gold chunks are present; the specific identifier is not sufficient to rescue approximate retrieval.

Best exact-vector gold chunk: https://github.com/pydantic/pydantic/issues/7461#issuecomment-1723405986

OR FTS top five: tiangolo/fastapi#9164, tiangolo/fastapi#9164, pydantic/pydantic#5562, tiangolo/fastapi#9164, pydantic/pydantic#2148

### tiangolo/fastapi#5108

Question: What steps can I take to resolve the issue of missing roles when retrieving resources associated with a user in my FastAPI application?

Baseline vector top five:

1. tiangolo/fastapi#5676 — How we can manage roles and permissions using fast-API dynamically? (issue_body; similarity 0.649221).
2. tiangolo/fastapi#5676 — How we can manage roles and permissions using fast-API dynamically? (comment; similarity 0.632366).
3. tiangolo/fastapi#2350 — Using FastAPI OAuth scope to replace user role based system. (issue_body; similarity 0.622180).
4. tiangolo/fastapi#5676 — How we can manage roles and permissions using fast-API dynamically? (issue_body; similarity 0.617645).
5. tiangolo/fastapi#5676 — How we can manage roles and permissions using fast-API dynamically? (comment; similarity 0.615321).

Best guess: Vague roles wording favors authorization topics, plus repeated chunks crowd out gold (exact rank 6). The actual issue is nested many-to-many response validation with missing resources -> roles fields. Four top-five chunks come from authorization issue #5676. Gold body spans multiple chunks, some without repeated context; the detailed solution (optional roles/default_factory=list) is a comment. Chunk splitting is a plausible contributor, not proven causal.

Best exact-vector gold chunk: https://github.com/fastapi/fastapi/issues/5108

OR FTS top five: tiangolo/fastapi#5676, tiangolo/fastapi#4982, tiangolo/fastapi#9164, tiangolo/fastapi#9164, tiangolo/fastapi#4965

### pydantic/pydantic#4999

Question: What unexpected behavior occurred when the reporter called `.parse_obj()` in an async loop?

Baseline vector top five:

1. pydantic/pydantic#1287 — parse_obj() / json() not called recursively / inconsistent parse_obj() behavior (comment; similarity 0.586149).
2. pydantic/pydantic#1287 — parse_obj() / json() not called recursively / inconsistent parse_obj() behavior (comment; similarity 0.582742).
3. pydantic/pydantic#1287 — parse_obj() / json() not called recursively / inconsistent parse_obj() behavior (comment; similarity 0.576503).
4. pydantic/pydantic#1287 — parse_obj() / json() not called recursively / inconsistent parse_obj() behavior (comment; similarity 0.556284).
5. pydantic/pydantic#2160 — Parsing behaviours with parse_obj (comment; similarity 0.547861).

Best guess: Related parse_obj issues and repeated comments crowd out gold (exact rank 10). Four top-five chunks are #1287's recursive parsing discussion. Gold specifically reports hanging indefinitely with no ValidationError in an async function. The question asks what happened without naming the hang. Its long body is split into two chunks; the second lacks repeated issue context, but the first retains the symptom and title. Chunking is plausible, not proven.

Best exact-vector gold chunk: https://github.com/pydantic/pydantic/issues/4999

OR FTS top five: tiangolo/fastapi#2690, tiangolo/fastapi#2104, tiangolo/fastapi#2710, tiangolo/fastapi#2619, pydantic/pydantic#10489

### pydantic/pydantic#4108

Question: What should be the correct behavior for setting exclusiveMinimum and exclusiveMaximum in the model schema?

Baseline vector top five:

1. pydantic/pydantic#1417 — 'exclusiveMaximum': inf probably shouldn't appear in model schema (comment; similarity 0.634405).
2. pydantic/pydantic#1417 — 'exclusiveMaximum': inf probably shouldn't appear in model schema (comment; similarity 0.632252).
3. pydantic/pydantic#1417 — 'exclusiveMaximum': inf probably shouldn't appear in model schema (comment; similarity 0.626857).
4. pydantic/pydantic#1164 — value of exclusiveMinimum is wrong (comment; similarity 0.603435).
5. pydantic/pydantic#1164 — value of exclusiveMinimum is wrong (comment; similarity 0.596381).

Best guess: Related schema issues and comment competition. Exact gold rank is 7; top 5 contains three #1417 chunks and two #1164 chunks. The question omits the distinguishing numeric-versus-boolean/OpenAPI schema-version debate. Gold explanatory comments clarify that behavior depends on schema version. Gold body and comments exist; no missing evidence observed.

Best exact-vector gold chunk: https://github.com/pydantic/pydantic/issues/4108#issuecomment-1160205808

OR FTS top five: pydantic/pydantic#10586, pydantic/pydantic#7273, pydantic/pydantic#1767, pydantic/pydantic#7273, pydantic/pydantic#9783

### pydantic/pydantic#11491

Question: What specific issues were identified in the organization of the serialization documentation that led to the decision to rewrite it?

Baseline vector top five:

1. tiangolo/fastapi#518 — Documenting multiple possible error models for a single response code (comment; similarity 0.415306).
2. tiangolo/fastapi#919 — Refactor internal function (comment; similarity 0.413253).
3. tiangolo/fastapi#919 — Refactor internal function (heuristic_resolution; similarity 0.412134).
4. tiangolo/fastapi#4747 — Separate Website and Documentation into their own repos. (comment; similarity 0.408006).
5. tiangolo/fastapi#1217 — Custom Error Handling Broke Automatic Documentation. (issue_body; similarity 0.406917).

Best guess: Approximate vector candidate miss plus questionable evaluation question. Gold body is exact rank 1 but approximate top 5 returns FastAPI documentation/refactoring discussions. Gold has one short body, no comments: it says the serialization concepts page is not well organized and links external PRs. The requested specific organizational issues are not listed in indexed text. This needs human review; do not silently relabel the case.

Best exact-vector gold chunk: https://github.com/pydantic/pydantic/issues/11491

OR FTS top five: tiangolo/fastapi#9164, tiangolo/fastapi#9164, tiangolo/fastapi#9164, tiangolo/fastapi#9164, pydantic/pydantic#12382

### tiangolo/fastapi#14502

Question: What performance symptom does the issue report when the FastAPI application is under load?

Baseline vector top five:

1. fastapi/fastapi#14496 — Performance issue (issue_body; similarity 0.759309).
2. tiangolo/fastapi#14500 — Performance issue (issue_body; similarity 0.703743).
3. tiangolo/fastapi#14499 — Performance issue (issue_body; similarity 0.703121).
4. tiangolo/fastapi#14497 — Performance issue (issue_body; similarity 0.702196).
5. tiangolo/fastapi#14501 — Performance issue (issue_body; similarity 0.701836).

Best guess: Identical-content issue ambiguity. All five retrieved issues and gold have title 'Performance issue' and body 'Slow response under load'. Exact gold rank is 8. Issue metadata/context differentiates their vectors, but the question cannot distinguish these sources. This exact-ID miss can retrieve text that answers the question. Repository aliases (fastapi/fastapi and tiangolo/fastapi) also appear; no deduplication or fixture changes made.

Best exact-vector gold chunk: https://github.com/fastapi/fastapi/issues/14502

OR FTS top five: tiangolo/fastapi#9164, tiangolo/fastapi#9164, tiangolo/fastapi#13022, tiangolo/fastapi#5740, fastapi/fastapi#13022

## Cause groups (overlap allowed)

- Exact-versus-approximate retrieval gaps: 4 cases (#1119, #2071, #7461, #11491), with exact gold ranks 3, 1, 1, 1 but absent from the live approximate top 5.
- Related issues, vague wording, repeated chunks/comment competition: 4 main cases (#4598, #5108, #4999, #4108); #1119 also has a related 405 discussion.
- Identical source text: 1 case (#14502); top-five sources answer the same symptom but fail exact-ID scoring.
- Question asks for details missing from indexed evidence: 1 flagged case (#11491). Human review remains empty; no labels changed.
- Possible chunking contribution: #5108 and #4999 have body continuation chunks without repeated context. No missing gold body/comment chunks were observed, and this audit does not prove chunk size caused the misses.

## Confidence interaction

api.retrieval_score uses the first result's retrieval_score. Vector mode sets that to cosine similarity; hybrid mode sets it to normalized RRF: sum(1/(60+rank))/(2/61). Therefore the fixed 0.5370554072220923 cutoff is not vector-similarity-based in hybrid mode. A candidate at rank 1 in both branches scores 1.0 irrespective of its absolute similarity. With strict FTS empty, vector rank 1 scores 0.5 and is refused. Broader FTS overlap can push unrelated queries above the cutoff. Lexical-only chunks also currently get similarity_score=0 rather than a computed cosine. Checkpoint 3 must report the frozen-cutoff behavior explicitly, without tuning on the 15 unanswerables.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/analyze_retrieval_misses.py
.\.venv\Scripts\python.exe scripts/rank_retrieval_misses.py
.\.venv\Scripts\python.exe scripts/report_retrieval_misses.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The rank script reuses ignored .question_embeddings.json. Without that cache it stops unless --approved-embedding-run is explicitly supplied after cost approval. This run used 1,211 embedding input tokens, estimated $0.00002422 at the repository-recorded $0.02/million rate; no chat model was used. Re-running the evidence collector resets rank fields; re-run the rank script afterward.
