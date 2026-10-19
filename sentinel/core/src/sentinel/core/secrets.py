import re
from collections.abc import Iterable

REDACTED = "[REDACTED]"

SECRET_PATTERNS = (
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)",
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b",
    r"\bgithub_pat_[A-Za-z0-9_]{40,}\b",
    r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,}\b",
    r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b",
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
    r"(?i:\b(?:password|passwd|secret|token|api[_-]?key)\b)[ \t]*[:=][ \t]*[\"']?(?![{$<\[])[^\s\"',;{}]{8,}",
)

_SECRET_ALTERNATIVES = "|".join(f"(?:{pattern})" for pattern in SECRET_PATTERNS)
_secret_material = re.compile(_SECRET_ALTERNATIVES)


def contains_secret(text: str) -> bool:
    return bool(_secret_material.search(text))


def redact(text: str, known_values: Iterable[str] = ()) -> str:
    for value in known_values:
        if value and len(value) >= 4:
            text = text.replace(value, REDACTED)
    return _secret_material.sub(REDACTED, text)
