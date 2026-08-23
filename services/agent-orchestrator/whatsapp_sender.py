"""
Outbound WhatsApp delivery (plain-language explanations, family
notifications, clarifying questions).

Callers (tool functions) pass only a hashed `user_id`. The raw
destination phone number is resolved + KMS-decrypted right here, at the
last possible moment before the Graph API call -- it never appears in a
tool-call argument, so it never ends up in the reasoning trace that gets
logged and shown on the dashboard.
"""

from __future__ import annotations

import logging

import httpx

import contact_directory
from config import settings

logger = logging.getLogger("aegis.orchestrator.whatsapp")

_GRAPH_BASE = "https://graph.facebook.com"


def send_whatsapp_text(user_id: str, body: str) -> bool:
    wa_id = contact_directory.resolve_wa_id(user_id)
    if wa_id is None:
        logger.error("cannot_send_no_contact_on_file", extra={"user_id": user_id})
        return False

    version = settings.meta_graph_api_version
    url = f"{_GRAPH_BASE}/{version}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": wa_id,
        "type": "text",
        "text": {"body": body},
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code >= 300:
            logger.error("whatsapp_send_failed", extra={"status": resp.status_code, "user_id": user_id})
            return False
        return True
    except httpx.HTTPError:
        logger.exception("whatsapp_send_exception", extra={"user_id": user_id})
        return False
