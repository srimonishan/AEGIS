"""
The one bridge between "everything is a hashed user_id" and "we actually
have to send a WhatsApp message to a phone number".

`remember_contact` is called once per IncomingReport (best-effort, never
blocks the case if it fails) to KMS-encrypt the raw wa_id and upsert it
into `user_directory/{user_id}`. `resolve_wa_id` is called only from
whatsapp_sender.py, right before a Graph API call -- never from a tool
function, so a raw phone number never becomes a tool-call argument that
the reasoning-trace logger could pick up.
"""

from __future__ import annotations

import base64
import logging

from google.cloud import kms

from schemas.firestore_models import UserDirectoryDoc

import firestore_client
from config import settings

logger = logging.getLogger("aegis.orchestrator.contact_directory")

_kms_client: kms.KeyManagementServiceClient | None = None


def _client() -> kms.KeyManagementServiceClient:
    global _kms_client
    if _kms_client is None:
        _kms_client = kms.KeyManagementServiceClient()
    return _kms_client


def _key_name() -> str:
    # projects/{p}/locations/{l}/keyRings/{r}/cryptoKeys/{k}
    return settings.contact_directory_kms_key


def remember_contact(user_id: str, wa_id: str) -> None:
    try:
        ciphertext = _client().encrypt(
            request={"name": _key_name(), "plaintext": wa_id.encode("utf-8")}
        ).ciphertext
        doc = UserDirectoryDoc(
            user_id=user_id,
            encrypted_wa_id=base64.b64encode(ciphertext).decode("ascii"),
        )
        firestore_client.db().collection("user_directory").document(user_id).set(
            doc.model_dump(mode="python"), merge=True
        )
    except Exception:
        # Never let a directory-registration failure break scam analysis;
        # the case still proceeds, it just may not be able to reply/notify.
        logger.exception("remember_contact_failed", extra={"user_id": user_id})


def resolve_wa_id(user_id: str) -> str | None:
    snap = firestore_client.db().collection("user_directory").document(user_id).get()
    if not snap.exists:
        logger.warning("contact_not_found", extra={"user_id": user_id})
        return None
    doc = UserDirectoryDoc.model_validate(snap.to_dict())
    ciphertext = base64.b64decode(doc.encrypted_wa_id)
    plaintext = _client().decrypt(
        request={"name": _key_name(), "ciphertext": ciphertext}
    ).plaintext
    return plaintext.decode("utf-8")
