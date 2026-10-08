# Revised deployment cost preflight ? enforced generation-input budget

**Prepared only. No deployment, OpenAI call, RDS access, database mutation or infrastructure change occurred.** The deployed image still predates these new input/output/retry controls.

## Settings required before live tests

- `RAG_MAX_GENERATION_INPUT_TOKENS=12000`.
- `OPENAI_GENERATION_MAX_OUTPUT_TOKENS=512` ? SDK `max_completion_tokens=512`.
- `OPENAI_MAX_RETRIES=0` ? SDK client `max_retries=0` for embedding and generation.
- Exactly two HTTP `/ask` requests with `top_k=5`; no manual retry or replay. Verify effective image and runtime settings; abort on mismatching overrides.

## Exact questions

- What is the recommended way to dump settings in starlette.config without exposing sensitive information like JWT secrets?
- What is the latest stable Python release today?

## Enforced input behavior

The budget counts the final serialized system prompt (instructions, JSON metadata and excerpts), complete user question and role text using tiktoken.encoding_for_model, plus 512 reserved tokens for the standard two-message Chat Completions framing. The reserve is part of the 12000 limit, not added on top. There are no tools, image inputs or additional messages in this path. Unknown tokenizer mappings fail before generation rather than guessing a count.

If full excerpts exceed the budget, a deterministic search for a fitting shared character-prefix length clips only excerpt strings. Source citation IDs, repository/issue identifiers, URLs, chunk types, similarity scores and source order stay intact. excerpt_truncated explicitly marks incomplete text. Complete excerpts are unchanged when they fit. The final candidate is recounted before SDK invocation. If fixed metadata/instructions/question cannot fit, return the fixed API abstention and zero generation usage. Structured citations are still assembled from the original retrieval list; cleanup checks only the clipped text actually supplied to generation.

Retrieval remains vector, ef_search=100, fetch 30 then collapse to five distinct issues, three repositories, and cutoff 0.5370554072220923. Ranking and cutoff decisions happen before clipping and are unchanged. Clipping may remove needed details, so capped-code answer quality/latency has not been remeasured. Prior historical/local measurements are not relabeled as results for this code.

## Conservative maximum OpenAI cost for these two requests

| Component | Maximum usage | Rate per million | Maximum USD |
|---|---:|---:|---:|
| Fixed-question embeddings | 29 tokens total | $0.02 | $5.8E-7 |
| Generation input, assuming both requests pass cutoff | 2 ? 12000 = 24000 tokens | $0.15 | $0.00360000 |
| Generation output | 2 ? 512 = 1024 tokens | $0.60 | $0.00061440 |
| Total | | | **$0.00421498** |

This is below the prior $0.01 hard cap, with $0.00578502 headroom, conditional on verifying the three exact control settings and executing only the two specified questions once. The embedding token count is obtained locally with cl100k_base; no embedding API call was made. No cached-input discount, cutoff refusal, marker-only output, or free credit is assumed. The 12000 allowance already contains conservative framing overhead for this exact plain-text two-message request form; adding tools or messages requires revisiting the accounting. This bound covers API token usage, not taxes, invoice adjustments, unrelated traffic or account-wide spending.

## Future deployment scope and AWS estimate

Only on explicit approval: build one local amd64 image, push to existing ECR github-rag-api and update existing Lambda github-rag-api in us-east-2. Preserve all other configuration/resources and existing images. The new settings can use code defaults where no environment override exists; verify them before smoke. Create no NAT/VPC endpoint/EC2/Glue/Multi-AZ or other infrastructure.

Prior AWS smoke estimate stays approximately $0.00036109 for one /health and the two /ask checks, under the original 15 aggregate billed GB-second/100 KiB log/1 MiB NAT assumptions. New image retention estimate remains $0.025/month assuming 250 MB entirely additional storage. These AWS estimates are not hard billing limits. Actual image size, billed duration and AWS invoice costs remain unknown until a separately approved execution. Existing NAT, IPv4 and RDS charges continue independently.

## Tests and evidence

93 local tests pass. Coverage includes full-prompt budget enforcement with Unicode and JSON escaping; unchanged prompts when they fit; source identity/order/URLs preserved through clipping and structured API serialization; no generation call when fixed overhead cannot fit; cleanup rejects code visible only in omitted excerpt tails; output and retry forwarding; environment bounds. git diff --check passes.

## References

- [GPT-4o mini prices](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Embedding prices](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [Chat Completions output limit](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)

This preflight supersedes the input-unbounded cost ceiling in docs/deployment/preflights/deployment_cost_controls_preflight.md; historical deployment/live reports remain unchanged. Stopped for review.
