"""
Deterministic WhatsApp replies for non-scam product questions.

These are intentionally handled before the ADK agent: greetings, owner
questions, and "what is this bot?" should be fast, cheap, and predictable.
Forwarded suspicious content still falls through to the normal agent path.
"""

from __future__ import annotations

import re

import whatsapp_sender
from schemas.events import IncomingReport

_OWNER_URL = "https://srimonishan.com/"
_WHATSAPP_URL = "https://wa.me/94764460037"

_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|start|menu|help)\s*[!.?]*\s*$", re.IGNORECASE)
_OWNER_RE = re.compile(
    r"\b(owner|creator|created|founder|developer|made|built|who made|who created|srimonishan|sri monishan)\b",
    re.IGNORECASE,
)
_BOT_RE = re.compile(
    r"\b(what is this|about|bot|aegis|scam guard|whatsapp bot|how (do|does) (you|this) work|help)\b",
    re.IGNORECASE,
)

_GREETING_REPLY = (
    "Hello. I am AEGIS Scam Guard, your WhatsApp AI safety agent.\n\n"
    "Send me any suspicious message, link, image, or voice note. I will check it for scam risk "
    "and reply with a clear safety explanation and next steps."
)

_OWNER_REPLY = (
    "AEGIS Scam Guard was created by Srimonishan.\n\n"
    f"Website: {_OWNER_URL}\n\n"
    "You can send suspicious WhatsApp messages here and I will help check them for scam risk."
)

_BOT_REPLY = (
    "AEGIS Scam Guard is a WhatsApp-native AI scam detection bot.\n\n"
    "You can forward suspicious messages, links, images, or voice notes. AEGIS checks for phishing, "
    "impersonation, urgency, financial pressure, and social-engineering patterns, then replies with "
    "a plain-language verdict.\n\n"
    f"Try it here: {_WHATSAPP_URL}\n"
    f"Created by Srimonishan: {_OWNER_URL}"
)


def try_handle_command(report: IncomingReport) -> bool:
    """Returns True when a simple product/profile question was answered."""

    text = (report.text_content or "").strip()
    if report.content_type.value != "text" or not text:
        return False

    if _GREETING_RE.fullmatch(text):
        whatsapp_sender.send_whatsapp_text(report.user_id, _GREETING_REPLY)
        return True

    if _OWNER_RE.search(text):
        whatsapp_sender.send_whatsapp_text(report.user_id, _OWNER_REPLY)
        return True

    if _BOT_RE.search(text) and len(text) <= 180:
        whatsapp_sender.send_whatsapp_text(report.user_id, _BOT_REPLY)
        return True

    return False
