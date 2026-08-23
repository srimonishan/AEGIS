"""
Parses a raw WhatsApp Cloud API webhook body into a flat list of
`RawMessage`. Pure function, no I/O -- easy to unit test against fixture
payloads without hitting Meta or GCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RawMessage:
    wa_id: str  # sender's WhatsApp id (phone number) -- raw, hash before storing/publishing
    wa_message_id: str
    msg_type: str  # "text" | "image" | "audio" | "video" | ...
    text_body: Optional[str] = None
    media_id: Optional[str] = None
    media_mime_type: Optional[str] = None
    timestamp: Optional[str] = None


def parse_webhook_payload(body: dict[str, Any]) -> list[RawMessage]:
    messages: list[RawMessage] = []
    if body.get("object") != "whatsapp_business_account":
        return messages

    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue
            for msg in value.get("messages", []):
                msg_type = msg.get("type", "")
                raw = RawMessage(
                    wa_id=msg.get("from", ""),
                    wa_message_id=msg.get("id", ""),
                    msg_type=msg_type,
                    timestamp=msg.get("timestamp"),
                )
                if msg_type == "text":
                    raw.text_body = msg.get("text", {}).get("body")
                elif msg_type in ("image", "audio", "video", "document"):
                    media_obj = msg.get(msg_type, {})
                    raw.media_id = media_obj.get("id")
                    raw.media_mime_type = media_obj.get("mime_type")
                    raw.text_body = media_obj.get("caption")
                else:
                    # unsupported type (e.g. location, sticker, reaction) --
                    # still forward with a text_body note so the case isn't
                    # silently dropped; the orchestrator can decide it's
                    # out of scope.
                    raw.text_body = f"[unsupported message type: {msg_type}]"
                if raw.wa_id and raw.wa_message_id:
                    messages.append(raw)
    return messages
