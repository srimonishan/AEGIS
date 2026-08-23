from __future__ import annotations

import logging

from google.adk.tools import ToolContext

import firestore_client
import whatsapp_sender
from schemas.enums import CaseStatus, Verdict
from schemas.events import CaseVerdict
from schemas.firestore_models import UserReportDoc

logger = logging.getLogger("aegis.orchestrator.tools.draft_protective_action")


def draft_protective_action(
    verdict: str,
    confidence: float,
    plain_language_explanation: str,
    report_draft: str,
    family_notification_draft: str,
    tool_context: ToolContext,
) -> dict:
    """Finalize your verdict and deliver it to the user.

    Call this once, after analyze_content and (if any entities were found)
    check_sender_reputation / cross_reference_reports. This is the tool
    that actually sends a WhatsApp reply -- write plain_language_explanation
    as if speaking directly and kindly to the person who forwarded this,
    in the same language they wrote in, with no jargon.

    Args:
        verdict: One of "scam", "likely_scam", "uncertain", "likely_safe",
            "safe".
        confidence: Your final confidence 0.0-1.0, after weighing your own
            analysis, sender reputation, and cross-referenced corroboration.
        plain_language_explanation: A short, warm, non-alarmist explanation
            of what this message is and why (not) to trust it, written for
            someone who may not be tech-savvy. This is sent to the user
            verbatim.
        report_draft: If verdict is "scam" or "likely_scam", a short
            factual report suitable for filing with the relevant
            bank/platform/authority (who, what, when, how they were
            contacted). Pass "" if verdict doesn't warrant a report.
        family_notification_draft: If warranted, a brief, non-shaming
            message to send to the user's registered family contact (only
            used if one exists on file). Written to inform, not alarm.
            Pass "" if not warranted.

    Returns:
        Whether the explanation was delivered and whether family was
        notified.
    """
    report_id = tool_context.state["report_id"]
    user_id = tool_context.state["user_id"]

    try:
        verdict_enum = Verdict(verdict)
    except ValueError:
        verdict_enum = Verdict.UNCERTAIN

    case_verdict = CaseVerdict(
        report_id=report_id,
        verdict=verdict_enum,
        confidence=max(0.0, min(1.0, confidence)),
        status=CaseStatus.OPEN,  # escalate_or_close sets the final status
        plain_language_explanation=plain_language_explanation,
        report_draft=report_draft or None,
        family_notification_draft=family_notification_draft or None,
        next_action="pending",
    )
    tool_context.state["verdict"] = case_verdict.model_dump(mode="json")

    analysis = tool_context.state.get("analysis", {})
    matched_pattern_id = None
    for rep in tool_context.state.get("reputation_results", []):
        if rep.get("known_pattern_ids"):
            matched_pattern_id = rep["known_pattern_ids"][0]
            break

    doc = UserReportDoc(
        report_id=report_id,
        user_id=user_id,
        status=CaseStatus.OPEN,
        verdict=verdict_enum,
        confidence=case_verdict.confidence,
        manipulation_patterns=analysis.get("manipulation_patterns", []),
        matched_pattern_id=matched_pattern_id,
        plain_language_explanation=plain_language_explanation,
        report_draft=report_draft or None,
    )
    firestore_client.upsert_user_report(doc)

    delivered = whatsapp_sender.send_whatsapp_text(user_id, plain_language_explanation)

    family_notified = False
    if verdict_enum in (Verdict.SCAM, Verdict.LIKELY_SCAM) and family_notification_draft:
        family_link = firestore_client.get_family_link(user_id)
        if family_link:
            family_notified = whatsapp_sender.send_whatsapp_text(
                family_link.family_contact_user_id, family_notification_draft
            )
            if family_notified:
                firestore_client.upsert_user_report(
                    UserReportDoc(
                        report_id=report_id,
                        user_id=user_id,
                        status=CaseStatus.OPEN,
                        family_notified=True,
                    )
                )

    # Reinforce the shared pattern DB for every entity that was actually
    # checked, but only once the case is confirmed scam-leaning -- this is
    # the network-effect write path.
    if verdict_enum in (Verdict.SCAM, Verdict.LIKELY_SCAM):
        for entity_rec in tool_context.state.get("checked_entities", []):
            try:
                firestore_client.record_or_reinforce_pattern(
                    entity=entity_rec["entity"],
                    entity_type=entity_rec["entity_type"],
                    manipulation_patterns=analysis.get("manipulation_patterns", []),
                    claimed_institution=analysis.get("claimed_institution"),
                )
            except Exception:
                logger.exception("record_pattern_failed", extra={"report_id": report_id})

    firestore_client.record_report_in_history(
        user_id, report_id, verdict_enum.value, matched_pattern_id
    )

    return {"delivered_to_user": delivered, "family_notified": family_notified}
