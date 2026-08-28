"""Redaction, applied before hashing.

Order matters: if a secret were hashed and then removed, the chain would commit
to the secret's value and a reader could confirm a guess. Everything here runs on
the way in, not on the way out.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PLACEHOLDER = "[redacted]"

# Values that must never reach an artifact even once.
_SECRET_KEYS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|credential|dsn|conninfo)", re.IGNORECASE
)
_PASSWORD_IN_URL = re.compile(r"(?P<scheme>\w+://[^:/@\s]+:)[^@/\s]+(?P<at>@)")


def redact_text(value: str, *, extra_secrets: tuple[str, ...] = ()) -> tuple[str, list[str]]:
    """Remove credentials and private host paths from a string."""
    applied: list[str] = []

    for secret in extra_secrets:
        if secret and secret in value:
            value = value.replace(secret, PLACEHOLDER)
            applied.append("literal-secret")

    replaced, count = _PASSWORD_IN_URL.subn(rf"\g<scheme>{PLACEHOLDER}\g<at>", value)
    if count:
        value = replaced
        applied.append("url-password")

    home = str(Path.home())
    if home in value:
        value = value.replace(home, "~")
        applied.append("host-home-path")

    return value, applied


def redact_payload(
    payload: dict[str, Any], *, extra_secrets: tuple[str, ...] = ()
) -> tuple[dict[str, Any], list[str]]:
    """Redact a payload by key name and by value content."""
    applied: list[str] = []

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for key, item in value.items():
                if isinstance(key, str) and _SECRET_KEYS.search(key):
                    out[key] = PLACEHOLDER
                    applied.append(f"key:{key}")
                else:
                    out[key] = walk(item)
            return out
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str):
            cleaned, marks = redact_text(value, extra_secrets=extra_secrets)
            applied.extend(marks)
            return cleaned
        return value

    return walk(payload), sorted(set(applied))
