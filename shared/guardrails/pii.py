"""
PII detection + redaction.

Design choice: this is a fast, regex/heuristic-based redactor, not a full
NLP PII model -- it runs synchronously in front of every model call and
every log line, so it has to be cheap. It is deliberately over-inclusive
(a false-positive redaction just replaces a non-PII token with a
placeholder; a false negative leaks PII -- so we bias toward redacting).

Nothing in this module ever returns the raw matched value to a caller
that might log it. `redact_pii` returns only the sanitized text and the
*types* of things it removed.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field

# --- Patterns -----------------------------------------------------------

_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{3,4}"
)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://[^\s]+|www\.[^\s]+")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Indian Aadhaar / generic 12-digit national-id-shaped numbers, and
# generic long digit runs that are almost certainly an account/ID number.
_LONG_DIGIT_RE = re.compile(r"\b\d{9,}\b")
_HANDLE_RE = re.compile(r"@[A-Za-z0-9_]{2,32}")

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("URL", _URL_RE),
    ("EMAIL", _EMAIL_RE),
    ("CARD", _CARD_RE),
    ("PHONE", _PHONE_RE),
    ("LONG_ID", _LONG_DIGIT_RE),
    ("HANDLE", _HANDLE_RE),
]


@dataclass
class PiiRedactionResult:
    sanitized_text: str
    redaction_types: list[str] = field(default_factory=list)
    # entities extracted for legitimate downstream use (link/sender checks),
    # kept separate from the "safe to log" sanitized_text.
    extracted_urls: list[str] = field(default_factory=list)
    extracted_handles: list[str] = field(default_factory=list)


def redact_pii(text: str) -> PiiRedactionResult:
    """Replace PII-shaped substrings with `[REDACTED:<TYPE>]` placeholders.

    URLs and @handles are *also* preserved in `extracted_*` because the
    orchestrator's sender/link-reputation tools legitimately need them --
    those lists must only ever be used for lookups, never written to logs
    verbatim (log the pattern_id / hash instead).
    """
    sanitized = text
    types_found: set[str] = set()
    urls = _URL_RE.findall(text)
    handles = _HANDLE_RE.findall(text)

    # Order matters: redact URLs/emails before the generic long-digit /
    # phone patterns so we don't double-mangle overlapping matches.
    for label, pattern in _PII_PATTERNS:
        def _sub(m: re.Match, label=label) -> str:
            types_found.add(label)
            return f"[REDACTED:{label}]"

        sanitized = pattern.sub(_sub, sanitized)

    return PiiRedactionResult(
        sanitized_text=sanitized,
        redaction_types=sorted(types_found),
        extracted_urls=urls,
        extracted_handles=handles,
    )


def hash_user_id(raw_wa_id: str) -> str:
    """Turn a raw WhatsApp id (phone number) into a stable, non-reversible
    user_id for storage. Uses HMAC-SHA256 with a server-side pepper so the
    hash can't be brute-forced back to a phone number even if the
    phone-number keyspace is small.

    AEGIS_USER_ID_PEPPER must be set in every service's environment (Secret
    Manager in production). This function intentionally raises if it's
    missing rather than silently falling back to an unsalted hash.
    """
    pepper = os.environ.get("AEGIS_USER_ID_PEPPER")
    if not pepper:
        raise RuntimeError(
            "AEGIS_USER_ID_PEPPER is not set -- refusing to hash a user id "
            "with no pepper. Set it via Secret Manager / env var."
        )
    digest = hmac.new(pepper.encode("utf-8"), raw_wa_id.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()
