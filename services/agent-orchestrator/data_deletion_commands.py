"""
"Forget me" as a deterministic WhatsApp command -- same reasoning as
family_link_commands.py for why this bypasses the ADK agent entirely:
an irreversible, security-relevant action should never be reachable via
text the agent is reasoning over adversarially, only via an exact command
grammar checked before guardrails or any Gemini call ever run.

Commands:
    DELETE MY DATA            -- starts a 10-minute confirmation window
    DELETE MY DATA CONFIRM    -- actually erases everything (irreversible)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from schemas.events import IncomingReport

import firestore_client
import whatsapp_sender

logger = logging.getLogger("aegis.orchestrator.data_deletion_commands")

_DELETE_RE = re.compile(r"^\s*DELETE\s+MY\s+DATA\s*$", re.IGNORECASE)
_DELETE_CONFIRM_RE = re.compile(r"^\s*DELETE\s+MY\s+DATA\s+CONFIRM\s*$", re.IGNORECASE)


def try_handle_command(report: IncomingReport) -> bool:
    text = (report.text_content or "").strip()
    if not text:
        return False

    if _DELETE_CONFIRM_RE.match(text):
        _handle_confirm(report)
        return True
    if _DELETE_RE.match(text):
        _handle_request(report)
        return True
    return False


def _handle_request(report: IncomingReport) -> None:
    firestore_client.create_pending_deletion(report.user_id)
    whatsapp_sender.send_whatsapp_text(
        report.user_id,
        "This will permanently delete your AEGIS case history, family-link "
        "settings, and saved contact info. This can't be undone. To "
        "confirm, reply within 10 minutes:\nDELETE MY DATA CONFIRM",
    )


def _handle_confirm(report: IncomingReport) -> None:
    pending = firestore_client.get_pending_deletion(report.user_id)
    if pending is None:
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "No pending deletion request found. Send DELETE MY DATA to start one."
        )
        return
    if datetime.now(timezone.utc) > pending.expires_at:
        firestore_client.delete_pending_deletion(report.user_id)
        whatsapp_sender.send_whatsapp_text(
            report.user_id, "That confirmation window expired. Send DELETE MY DATA to start again."
        )
        return

    # Send the confirmation WHILE we can still reach this user_id --
    # purge_user_data removes user_directory (their contact) as its last
    # step, after which AEGIS has no way to message them until they write
    # in again.
    whatsapp_sender.send_whatsapp_text(
        report.user_id,
        "Your AEGIS data is being deleted now. If you forward another "
        "message in the future, we'll start completely fresh.",
    )
    counts = firestore_client.purge_user_data(report.user_id)
    firestore_client.delete_pending_deletion(report.user_id)
    logger.info("user_data_purged", extra=counts)  # counts only, never content
