"""
Family-link opt-in, as deterministic string commands -- deliberately NOT
routed through the ADK agent.

Why not a tool the agent calls: the agent reasons over forwarded content
that may be adversarial (see shared/guardrails). If "create a family
link to +1..." were something the LLM could be talked into doing based
on text inside a forwarded message, a scammer could embed that text and
get AEGIS to message an arbitrary third party on their behalf -- a spam
and privacy vector, not just a jailbreak. So this whole module runs
BEFORE the guardrail-wrapped agent turn, on an exact command grammar, and
never touches Gemini. See main.py::_process_report for the call site.

Commands (case-insensitive, sent by the user as a plain WhatsApp message):
    LINK FAMILY <phone>       -- protected user requests a link
    CONFIRM LINK <code>       -- the *contact* accepts (must reply from
                                 the same number the code was sent to)
    DECLINE LINK <code>       -- the contact explicitly refuses
    STOP FAMILY ALERTS        -- the contact revokes consent at any time
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from schemas.enums import PendingLinkStatus
from schemas.events import IncomingReport
from schemas.firestore_models import FamilyLinkDoc, PendingFamilyLinkDoc
from guardrails.pii import hash_user_id

import contact_directory
import firestore_client
import whatsapp_sender

logger = logging.getLogger("aegis.orchestrator.family_link_commands")

_LINK_RE = re.compile(r"^\s*LINK\s+FAMILY\s+([+0-9()\-\s]{1,20})\s*$", re.IGNORECASE)
_CONFIRM_RE = re.compile(r"^\s*CONFIRM\s+LINK\s+([A-Za-z0-9]{4,10})\s*$", re.IGNORECASE)
_DECLINE_RE = re.compile(r"^\s*DECLINE\s+LINK\s+([A-Za-z0-9]{4,10})\s*$", re.IGNORECASE)
_STOP_RE = re.compile(r"^\s*STOP\s+FAMILY\s+ALERTS?\s*$", re.IGNORECASE)

_LINK_TTL_HOURS = 24


def _normalize_phone(raw: str) -> str:
    """Keep a leading '+' and digits only -- matches how Meta hands us
    `wa_id` (no punctuation, country code included, no leading '+' in
    practice, but we accept either on input)."""
    plus = "+" if raw.strip().startswith("+") else ""
    digits = re.sub(r"\D", "", raw)
    return plus + digits


def _generate_code() -> str:
    return uuid.uuid4().hex[:6].upper()


def try_handle_command(report: IncomingReport) -> bool:
    """Returns True if this message was a recognized command and has been
    fully handled -- the caller (main.py) must skip guardrail/agent
    processing for this report entirely when this returns True."""
    text = (report.text_content or "").strip()
    if not text:
        return False

    if m := _LINK_RE.match(text):
        _handle_link_request(report, m.group(1))
        return True
    if m := _CONFIRM_RE.match(text):
        _handle_confirm(report, m.group(1))
        return True
    if m := _DECLINE_RE.match(text):
        _handle_decline(report, m.group(1))
        return True
    if _STOP_RE.match(text):
        _handle_stop(report)
        return True
    return False


def _handle_link_request(report: IncomingReport, raw_phone: str) -> None:
    target_wa_id = _normalize_phone(raw_phone)
    if len(target_wa_id.lstrip("+")) < 7:
        whatsapp_sender.send_whatsapp_text(
            report.user_id,
            "That doesn't look like a valid phone number. Send it like: "
            "LINK FAMILY +15551234567",
        )
        return

    target_user_id = hash_user_id(target_wa_id)
    if target_user_id == report.user_id:
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "You can't add yourself as your own family contact."
        )
        return

    # Register the contact immediately (KMS-encrypted) so we can reach
    # them for the confirmation prompt even if they've never messaged
    # AEGIS before.
    contact_directory.remember_contact(target_user_id, target_wa_id)

    code = _generate_code()
    firestore_client.create_pending_family_link(
        PendingFamilyLinkDoc(
            code=code,
            requester_user_id=report.user_id,
            target_user_id=target_user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=_LINK_TTL_HOURS),
        )
    )

    whatsapp_sender.send_whatsapp_text(
        target_user_id,
        "Someone added you as a trusted contact on AEGIS, a scam-protection "
        "assistant. If you'd like to be alerted when they're targeted by a "
        f"scam, reply:\nCONFIRM LINK {code}\n\nDon't recognize this? Ignore "
        f"this message, or reply DECLINE LINK {code}.",
    )
    whatsapp_sender.send_whatsapp_text(
        report.user_id,
        "We've sent a confirmation request to that number. Once they "
        "confirm, they'll be notified if you're targeted by a scam. This "
        f"request expires in {_LINK_TTL_HOURS} hours.",
    )


def _handle_confirm(report: IncomingReport, code: str) -> None:
    pending = firestore_client.get_pending_family_link(code)
    if pending is None or pending.status != PendingLinkStatus.PENDING:
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "That confirmation code isn't valid or was already used."
        )
        return
    if datetime.now(timezone.utc) > pending.expires_at:
        firestore_client.resolve_pending_family_link(code, PendingLinkStatus.EXPIRED)
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "That confirmation code has expired. Ask them to send it again."
        )
        return
    if report.user_id != pending.target_user_id:
        # Whoever is confirming isn't the phone number the code was sent
        # to -- refuse rather than let a leaked code be redeemed by
        # anyone who saw it.
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "That code isn't associated with your number."
        )
        return

    firestore_client.upsert_family_link(
        FamilyLinkDoc(user_id=pending.requester_user_id, family_contact_user_id=pending.target_user_id)
    )
    firestore_client.resolve_pending_family_link(code, PendingLinkStatus.CONFIRMED)

    whatsapp_sender.send_whatsapp_text(
        report.user_id,
        "Confirmed. You'll get an occasional alert if they're targeted by a "
        "scam. Reply STOP FAMILY ALERTS anytime to opt out.",
    )
    whatsapp_sender.send_whatsapp_text(
        pending.requester_user_id,
        "Your family contact confirmed -- they'll now be notified if you're targeted by a scam.",
    )


def _handle_decline(report: IncomingReport, code: str) -> None:
    pending = firestore_client.get_pending_family_link(code)
    if pending is None or pending.status != PendingLinkStatus.PENDING:
        return  # nothing to decline; stay silent rather than confirm a code's existence
    if report.user_id != pending.target_user_id:
        return
    firestore_client.resolve_pending_family_link(code, PendingLinkStatus.DECLINED)
    whatsapp_sender.send_whatsapp_text(report.user_id, "Understood -- that request has been declined.")
    whatsapp_sender.send_whatsapp_text(
        pending.requester_user_id, "Your family contact declined the notification request."
    )


def _handle_stop(report: IncomingReport) -> None:
    count = firestore_client.deactivate_family_links_for_contact(report.user_id)
    if count:
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "You've been removed as a family contact and won't receive further alerts."
        )
    else:
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "You weren't registered as a family contact for anyone."
        )
