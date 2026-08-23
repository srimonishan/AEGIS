from __future__ import annotations

from datetime import datetime, timedelta, timezone

from google.adk.tools import ToolContext

import firestore_client
import followup_publisher
from schemas.enums import CaseStatus
from schemas.events import FollowUpEvent
from schemas.firestore_models import UserReportDoc

_DECISION_TO_STATUS = {
    "close": CaseStatus.CLOSED,
    "monitor": CaseStatus.MONITORING,
    "ask_user": CaseStatus.AWAITING_USER,
    "escalate": CaseStatus.ESCALATED,
}


def escalate_or_close(
    decision: str, reason: str, follow_up_hours: float, tool_context: ToolContext
) -> dict:
    """Decide what happens to this case next. Call this once, last, after
    draft_protective_action.

    Args:
        decision: One of:
            "close" -- verdict was clear (safe or confidently a scam with
                nothing left to check) and the user has what they need.
            "monitor" -- worth rechecking later (e.g. sender reputation
                might change, or you want to see if this user gets
                re-targeted by the same entity). Combine with
                follow_up_hours.
            "ask_user" -- you genuinely need more information from the
                user before you can reach a verdict. Do not use this if
                you already called draft_protective_action this turn.
            "escalate" -- high-confidence active scam, especially against
                a vulnerable user -- flag for human review in addition to
                whatever draft_protective_action already did.
        reason: One short sentence explaining the decision, for the ops
            dashboard.
        follow_up_hours: Only used when decision is "monitor" -- how many
            hours from now to recheck this case. Use 24 if unsure.

    Returns:
        Confirmation of the case's new status.
    """
    report_id = tool_context.state["report_id"]
    user_id = tool_context.state["user_id"]
    status = _DECISION_TO_STATUS.get(decision, CaseStatus.OPEN)

    firestore_client.upsert_user_report(
        UserReportDoc(report_id=report_id, user_id=user_id, status=status)
    )
    firestore_client.append_reasoning_trace(
        report_id,
        {
            "tool": "escalate_or_close",
            "decision": decision,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        },
    )

    if decision == "monitor":
        hours = follow_up_hours if follow_up_hours and follow_up_hours > 0 else 24
        event = FollowUpEvent(
            report_id=report_id,
            user_id=user_id,
            reason=reason,
            not_before=datetime.now(timezone.utc) + timedelta(hours=hours),
        )
        followup_publisher.publish_followup(event)

    return {"status": status.value}
