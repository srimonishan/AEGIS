"""Read-only counterpart of the orchestrator's contact_directory.py --
this service only ever resolves an existing entry (to send a proactive
check-in), it never registers a new one (that only happens when
ingestion sees a fresh IncomingReport, handled by the orchestrator)."""

from __future__ import annotations

import base64
import logging

from google.cloud import kms

from schemas.firestore_models import UserDirectoryDoc

import firestore_client
from config import settings

logger = logging.getLogger("aegis.followup.contact_directory")

_kms_client: kms.KeyManagementServiceClient | None = None


def _client() -> kms.KeyManagementServiceClient:
    global _kms_client
    if _kms_client is None:
        _kms_client = kms.KeyManagementServiceClient()
    return _kms_client


def resolve_wa_id(user_id: str) -> str | None:
    snap = firestore_client.db().collection("user_directory").document(user_id).get()
    if not snap.exists:
        logger.warning("contact_not_found", extra={"user_id": user_id})
        return None
    doc = UserDirectoryDoc.model_validate(snap.to_dict())
    ciphertext = base64.b64decode(doc.encrypted_wa_id)
    plaintext = _client().decrypt(
        request={"name": settings.contact_directory_kms_key, "ciphertext": ciphertext}
    ).plaintext
    return plaintext.decode("utf-8")
