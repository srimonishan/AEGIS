"""
AEGIS follow-up worker.

Cloud Run Job entrypoint (NOT an HTTP server): Cloud Scheduler invokes a
new execution of this job on a fixed cadence (see infra/terraform/
scheduler.tf, default every 30 minutes). Each execution: pulls every
`follow_ups` doc that's due (`status == pending AND not_before <= now`),
re-checks whether anything has changed about the case, takes action, and
exits. This -- a real query against a durable store, run by a real
scheduled trigger, minutes to hours after the original conversation --
is what makes "runs asynchronously in the background" true rather than
cosmetic.
"""

from __future__ import annotations

import logging
import sys

from schemas.enums import CaseStatus
from schemas.firestore_models import FollowUpDoc

import firestore_client
import whatsapp_sender
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegis.followup_worker")


def process_due_follow_ups() -> int:
    due = firestore_client.due_follow_ups(settings.batch_size)
    logger.info("follow_up_batch_start", extra={"count": len(due)})

    processed = 0
    for follow_up in due:
        try:
            _process_one(follow_up)
            firestore_client.mark_follow_up_done(follow_up.follow_up_id)
            processed += 1
        except Exception:
            logger.exception(
                "follow_up_processing_failed",
                extra={"follow_up_id": follow_up.follow_up_id, "report_id": follow_up.report_id},
            )
            firestore_client.mark_follow_up_failed(follow_up.follow_up_id)

    logger.info("follow_up_batch_end", extra={"processed": processed, "total": len(due)})
    return processed


def _process_one(follow_up: FollowUpDoc) -> None:
    report = firestore_client.get_user_report(follow_up.report_id)
    if report is None:
        logger.warning("follow_up_for_missing_report", extra={"report_id": follow_up.report_id})
        return

    if report.status != CaseStatus.MONITORING:
        # The case moved on (user re-engaged, got closed, escalated some
        # other way) since this follow-up was scheduled -- nothing to do.
        logger.info(
            "follow_up_skipped_status_changed",
            extra={"report_id": follow_up.report_id, "status": report.status.value},
        )
        return

    current_count = 0
    if report.matched_pattern_id:
        current_count = firestore_client.get_pattern_report_count(report.matched_pattern_id)

    firestore_client.append_reasoning_trace(
        follow_up.report_id,
        {
            "tool": "followup_worker.recheck",
            "matched_pattern_id": report.matched_pattern_id,
            "current_corroborating_count": current_count,
            "attempt": follow_up.attempt,
        },
    )

    if current_count >= 3:
        # Other users have since corroborated the same scam entity --
        # escalate rather than let this quietly sit in "monitoring".
        whatsapp_sender.send_whatsapp_text(
            report.user_id,
            "Update from AEGIS: since we last spoke, several other people have "
            "also reported the sender from your message as a scam. Please "
            "continue to avoid contact with them and don't share any personal "
            "or payment details.",
        )
        firestore_client.upsert_user_report_status(
            follow_up.report_id, report.user_id, status=CaseStatus.ESCALATED
        )
        return

    if follow_up.attempt >= settings.max_follow_up_cycles:
        firestore_client.upsert_user_report_status(
            follow_up.report_id, report.user_id, status=CaseStatus.CLOSED
        )
        return

    # Nothing new yet -- reschedule another check rather than closing
    # prematurely.
    firestore_client.schedule_next_follow_up(
        report_id=follow_up.report_id,
        user_id=report.user_id,
        reason=f"recheck cycle {follow_up.attempt + 1}",
        hours=24,
        attempt=follow_up.attempt + 1,
    )


if __name__ == "__main__":
    count = process_due_follow_ups()
    logger.info("follow_up_worker_done", extra={"processed": count})
    sys.exit(0)
