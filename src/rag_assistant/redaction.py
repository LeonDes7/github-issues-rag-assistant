"""Conservative text redaction for model evidence and rendered responses."""
import re

REDACTED = "[REDACTED]"
UNSAFE_SETTINGS_ANSWER = (
    "The generated settings-dump example could expose sensitive values and has "
    "been withheld. Review the retrieved sources before using such code."
)
UNSAFE_SETTINGS_PATTERN = re.compile(
    r"\bdict\s*\(\s*settings\.config\s*\)|\breturn\s+settings\.config\b",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:[a-z0-9_]*(?:password|passwd|secret|api_key|access_token|refresh_token|"
    r"private_key|authorization)[a-z0-9_]*|token)\b[\"']?\s*[:=]\s*)"
    r"(?:Secret\s*\(\s*)?([\"'])([^\r\n]*?)\2"
)


def redact_sensitive_text(text: str) -> str:
    """Redact literal values, not setting names in config()/environment lookups."""
    text = re.sub(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
                  r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", REDACTED, text)
    text = SECRET_ASSIGNMENT.sub(lambda m:
        m[0][:m.start(3) - m.start()] + REDACTED + m[0][m.end(3) - m.start():], text)
    text = re.sub(r"(?i)(\bBearer\s+)[a-z0-9._~+/=-]+", r"\1" + REDACTED, text)
    text = re.sub(r"\b(?:sk-[a-zA-Z0-9_-]{16,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b", REDACTED, text)
    text = re.sub(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b", REDACTED, text)
    text = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", r"\1" + REDACTED + "@", text)
    # Quoted JSON/config scalar values and common unquoted assignments.
    text = re.sub(r"(?im)(\b(?:JWT_SECRET|SECRET_KEY|API_KEY|PASSWORD|ACCESS_TOKEN)\s*=\s*)"
                  r"([^\s\"'\n][^\n]*)", lambda m: m[0] if re.match(
                      r"(?:config\(|Secret\(|os\.|getenv\(|None\b|\[REDACTED\])", m[2]
                  ) else m[1] + REDACTED, text)
    text = re.sub(r"(?im)^(\s*(?:JWT_SECRET|SECRET_KEY|API_KEY|PASSWORD|ACCESS_TOKEN)\s*:\s*)"
                  r"([^\s\"'\n][^\n]*)", r"\1" + REDACTED, text)
    return text


def safe_excerpt(text: str) -> str:
    text = redact_sensitive_text(text)
    return re.sub(r"(?ms)^\s*```[^\n]*\n.*?^\s*```", lambda m:
                  "[Unsafe settings-dump example omitted]" if UNSAFE_SETTINGS_PATTERN.search(m[0]) else m[0], text)


def safe_display_payload(value):
    """Sanitize textual excerpts recursively, keeping citation metadata intact."""
    if isinstance(value, dict):
        return {key: (UNSAFE_SETTINGS_ANSWER if key == "answer" and isinstance(item, str)
                      and UNSAFE_SETTINGS_PATTERN.search(item) else
                      safe_excerpt(item) if key in {"answer", "excerpt", "chunk_text"}
                      and isinstance(item, str) else safe_display_payload(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [safe_display_payload(item) for item in value]
    return value
