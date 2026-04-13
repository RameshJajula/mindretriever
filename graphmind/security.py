from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
_KEY_RE = re.compile(r'(?i)(api[_-]?key|secret|token)\s*[:=]\s*["\']?[A-Za-z0-9_\-]{8,}')


def redact_text(text: str, *, redact_emails: bool, redact_keys: bool) -> str:
    redacted = text
    if redact_emails:
        redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    if redact_keys:
        redacted = _KEY_RE.sub("[REDACTED_SECRET]", redacted)
    return redacted
