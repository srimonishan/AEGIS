"""
Meta webhook signature verification.

Meta signs every webhook POST body with:
  X-Hub-Signature-256: sha256=<HMAC-SHA256(raw_body, app_secret)>

We MUST verify against the raw, unparsed request bytes -- re-serializing
the parsed JSON before hashing can produce a different byte string
(whitespace/key-order) and break verification, or worse, silently accept
a payload we should have rejected. Never trust an incoming webhook call
that doesn't verify.
"""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    provided = signature_header.removeprefix("sha256=")
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    # constant-time compare
    return hmac.compare_digest(provided, expected)
