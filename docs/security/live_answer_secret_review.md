# Local review of the live settings answer

Finding: no literal credential was found in the exact live answer or its five cited excerpts. `JWT_SECRET = config("JWT_SECRET", cast=starlette.datastructures.Secret)` references an environment setting name; it does not contain its value. `Secret('**********')` is a masking illustration, not a credential. No credential-validity test was attempted.

The actual defect is an unsafe recommendation. Source [1], Starlette issue #408, reports that its settings endpoint returns secrets. The live answer nevertheless offers the same `dict(settings.config)`/return example as an implementation, then warns that filtering or masking is needed. The snippet should not be presented as a safe secret-redaction solution.

A read-only RDS inspection found exactly one matching chunk for each of the five saved live citation metadata records. All five matched the earlier local saved excerpts byte-for-byte. [live_answer_secret_review_sources.json](live_answer_secret_review_sources.json) records source metadata, hashes, and sanitized review text. No database data was changed. The original live artifact is retained; no deployment or OpenAI call occurred.

Proposed local-only patch:

- Redact recognizable literal credentials in excerpts before prompt budgeting/model transmission, and in finalized answers: sensitive quoted assignments/JSON values, common unquoted config/YAML credentials, bearer tokens, recognizable API/AWS keys, JWTs, private-key blocks and URL user/password fields.
- Preserve setting-name lookups such as config("JWT_SECRET") and existing masking illustrations. Redaction intentionally hides even synthetic/example literal credentials rather than claiming they are real.
- Omit the known unsafe fenced settings-dump pattern from model evidence. Withhold any generated answer containing that pattern, replacing it with a fixed API-controlled message. This avoids retaining the misleading opening recommendation alongside its warning.
- Apply the same defenses to UI-displayed answer/excerpt/chunk_text fields, including debug payloads from an older API. Citation URLs, source IDs, ranking scores and other metadata stay intact; stored chunks are not mutated. The current UI normally displays source links rather than excerpt bodies, but nested text fields are sanitized if supplied.

101 local tests pass, covering literal redaction, setting-name/mask preservation, unsafe-answer suppression, model-facing text sanitization before budgeting, UI text suppression and source metadata preservation. Existing retrieval, cutoff, budget, abstention and API tests pass. `git diff --check` passes.

This is a deterministic pattern-based defense, not a complete credential detector or general unsafe-code verifier. Arbitrary sensitive strings without recognizable context and other unsafe code patterns can evade it. No quality, latency or live-output claims are made for this undeployed patch.

Patch files: src/rag_assistant/redaction.py, src/rag_assistant/api.py, streamlit_app.py, tests/test_redaction.py. The Lambda and UI have not been redeployed. Stopped for user review.
