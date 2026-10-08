# Local demo safety changes

Streamlit sanitizes answer/excerpt/debug text and keeps source metadata separate.
Quota checks occur before ask_api: five attempts per browser session, fifty attempts
per UTC date shared by all sessions on one app instance. Failed calls consume quota.
SQLite transactions reserve daily slots atomically; quota errors fail closed.
The local artifacts/demo_quota.sqlite3 file is ignored. Cloud filesystem resets,
new browser sessions and multiple instances limit protection; direct API access
bypasses this UI guard. Durable distributed/global spending limits are not provided.

Community Cloud secrets: RAG_API_URL should be
https://w3qqwb25w0.execute-api.us-east-2.amazonaws.com and API_AUTH_TOKEN
must contain the existing private bearer token. Do not paste its value into source.
The token is used in server-side request headers, not browser output. Hosted
secrets/logs/browser inspection remains pending; no claim of exhaustive audit.

Manual API Gateway console setting proposal (no AWS changes performed):
Select us-east-2, API Gateway, github-rag-api-dev (w3qqwb25w0), Stages,
the serving stage (normally $default), Edit default route throttling/settings.
Set rate=1 request/second and burst=2; Save. Review POST /ask overrides so none
raise that limit. Existing requests still incur charges; throttling has no separate
feature fee. It is best-effort throttling, not a hard daily spend cap.

Local validation: 104 unit tests pass. Replaying the previously saved unsafe
settings response produces the fixed API-controlled unsafe-answer withholding
message. This is offline verification, not a new live request or UI deployment.
