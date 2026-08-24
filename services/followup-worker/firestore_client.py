"""
Firestore access for the follow-up worker. Trimmed to only what this
service needs (query/update follow_ups, re-check global_patterns, update
user_reports). Deliberately NOT importing the orchestrator's
firestore_client module -- each Cloud Run service is an independently
deployable, independently IAM-scoped unit; the *contract* (typed
Firestore models in shared/schemas) is shared, the client code is not.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from schemas.enums import FollowUpStatus
from schemas.firestore_models import FollowUpDoc, GlobalPatternDoc, UserReportDoc

from config import settings

_db: firestore.Client | None = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.gcp_project_id)
    return _db


def fingerprint_entity(entity: str) -> str:
    normalized = entity.strip().lower()
    salted = f"{settings.global_pattern_salt}:{normalized}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def due_follow_ups(limit: int) -> list[FollowUpDoc]:
    now = datetime.now(timezone.utc)
    query = (
        db()
        .collection("follow_ups")
        .where(filter=FieldFilter("status", "==", FollowUpStatus.PENDING.value))
        .where(filter=FieldFilter("not_before", "<=", now))
        .limit(limit)
    )
    return [FollowUpDoc.model_validate(snap.to_dict()) for snap in query.stream()]


def mark_follow_up_done(follow_up_id: str) -> None:
    db().collection("follow_ups").document(follow_up_id).set(
        {"status": FollowUpStatus.DONE.value, "processed_at": datetime.now(timezone.utc)},
        merge=True,
    )


def mark_follow_up_failed(follow_up_id: str) -> None:
    db().collection("follow_ups").document(follow_up_id).set(
        {"status": FollowUpStatus.FAILED.value, "processed_at": datetime.now(timezone.utc)},
        merge=True,
    )


def get_user_report(report_id: str) -> Optional[UserReportDoc]:
    snap = db().collection("user_reports").document(report_id).get()
    if not snap.exists:
        return None
    return UserReportDoc.model_validate(snap.to_dict())


def upsert_user_report_status(report_id: str, user_id: str, **fields) -> None:
    """Merges a PARTIAL status update -- see the matching (more detailed)
    docstring on agent-orchestrator/firestore_client.py::upsert_user_report
    for why `exclude_unset=True` is load-bearing here: without it, this
    call would silently null out the verdict/confidence/reasoning_trace
    the orchestrator already wrote for this report."""
    from schemas.enums import CaseStatus

    doc = UserReportDoc(
        report_id=report_id,
        user_id=user_id,
        status=fields.pop("status", CaseStatus.MONITORING),
        **fields,
    )
    db().collection("user_reports").document(report_id).set(
        doc.model_dump(mode="python", exclude_unset=True), merge=True
    )


def append_reasoning_trace(report_id: str, entry: dict) -> None:
    db().collection("user_reports").document(report_id).set(
        {"reasoning_trace": firestore.ArrayUnion([entry])}, merge=True
    )


def get_pattern_report_count(pattern_id: str) -> int:
    snap = db().collection("global_patterns").document(pattern_id).get()
    if not snap.exists:
        return 0
    return GlobalPatternDoc.model_validate(snap.to_dict()).report_count


def schedule_next_follow_up(
    report_id: str, user_id: str, reason: str, hours: float, attempt: int = 1
) -> None:
    import uuid

    follow_up_id = uuid.uuid4().hex
    doc = FollowUpDoc(
        follow_up_id=follow_up_id,
        report_id=report_id,
        user_id=user_id,
        reason=reason,
        not_before=datetime.now(timezone.utc) + timedelta(hours=hours),
        attempt=attempt,
    )
    db().collection("follow_ups").document(follow_up_id).set(doc.model_dump(mode="python"))
