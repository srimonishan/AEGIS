"""
Resolves a WhatsApp media id to a durable gs:// URI.

Why download here rather than pass raw bytes through Pub/Sub: Pub/Sub caps
message size at 10MB and forwarded images/voice notes routinely get close
to that; a GCS URI keeps every downstream event small and lets Firestore
docs/dashboard reference the same object without re-fetching from Meta
(whose media URLs expire).
"""

from __future__ import annotations

import mimetypes
import uuid

import httpx
from google.cloud import storage

from config import settings

_GRAPH_BASE = "https://graph.facebook.com"


class MediaResolutionError(RuntimeError):
    pass


def resolve_media_to_gcs(media_id: str, wa_message_id: str) -> tuple[str, str]:
    """Returns (gcs_uri, mime_type). Raises MediaResolutionError on failure
    -- callers should still publish the IncomingReport with media fields
    left empty and a note in text_content rather than dropping the report
    entirely, so a Meta-side hiccup doesn't silently swallow a user's
    scam report.
    """
    headers = {"Authorization": f"Bearer {settings.meta_access_token}"}
    version = settings.meta_graph_api_version

    with httpx.Client(timeout=15.0) as client:
        meta_resp = client.get(f"{_GRAPH_BASE}/{version}/{media_id}", headers=headers)
        if meta_resp.status_code != 200:
            raise MediaResolutionError(
                f"media metadata lookup failed: {meta_resp.status_code}"
            )
        meta = meta_resp.json()
        media_url = meta.get("url")
        mime_type = meta.get("mime_type", "application/octet-stream")
        if not media_url:
            raise MediaResolutionError("media metadata missing url")

        content_resp = client.get(media_url, headers=headers)
        if content_resp.status_code != 200:
            raise MediaResolutionError(
                f"media download failed: {content_resp.status_code}"
            )
        content = content_resp.content

    ext = mimetypes.guess_extension(mime_type) or ""
    blob_name = f"media/{wa_message_id}-{uuid.uuid4().hex[:8]}{ext}"

    gcs_client = storage.Client()
    bucket = gcs_client.bucket(settings.media_gcs_bucket)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(content, content_type=mime_type)

    return f"gs://{settings.media_gcs_bucket}/{blob_name}", mime_type
