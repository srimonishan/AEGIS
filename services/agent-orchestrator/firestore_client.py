"""
Typed Firestore access. Every read/write goes through a model in
schemas.firestore_models -- no ad hoc dicts (see project standards in the
root README).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from schemas.enums import CaseStatus, PendingLinkStatus, Verdict
from schemas.firestore_models import (
    FamilyLinkDoc,
    GlobalPatternDoc,
    PendingDeletionDoc,
    PendingFamilyLinkDoc,
    UserHistoryDoc,
    UserReportDoc,
)

from config import settings

_db: firestore.Client | None = None


def db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.gcp_project_id)
    return _db


def fingerprint_entity(entity: str) -> str:
    """Deterministic, cross-user fingerprint for a scam entity (domain,
    phone, handle). Uses a fixed global salt (NOT the per-user pepper) so
    the same scam entity reported by different users collides to the same
    global_patterns doc -- that collision is the entire network-effect
    story of this product."""
    normalized = entity.strip().lower()
    salted = f"{settings.global_pattern_salt}:{normalized}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


# ---- user_reports --------------------------------------------------------


def upsert_user_report(doc: UserReportDoc) -> None:
    """Merges a PARTIAL update into user_reports/{report_id}.

    Uses `exclude_unset=True` deliberately: callers construct a
    `UserReportDoc` passing only the fields they actually mean to change
    (e.g. escalate_or_close passes only report_id/user_id/status). Without
    exclude_unset, `model_dump()` would include every other field at its
    Python default (None, [], False) and Firestore's merge=True would
    still overwrite those onto the existing document -- silently wiping
    out the verdict/confidence/reasoning_trace a *previous* call (e.g.
    draft_protective_action) had just written. Found by actually running
    the full agent loop against real Firestore: the final verdict/
    reasoning_trace was empty despite the agent clearly having reasoned
    through it (visible in the one surviving trace entry). See
    tests/test_firestore_integration.py for the regression test.
    """
    doc.updated_at = datetime.now(timezone.utc)
    db().collection("user_reports").document(doc.report_id).set(
        doc.model_dump(mode="python", exclude_unset=True), merge=True
    )


def get_user_report(report_id: str) -> Optional[UserReportDoc]:
    snap = db().collection("user_reports").document(report_id).get()
    if not snap.exists:
        return None
    return UserReportDoc.model_validate(snap.to_dict())


def append_reasoning_trace(report_id: str, entry: dict) -> None:
    db().collection("user_reports").document(report_id).set(
        {"reasoning_trace": firestore.ArrayUnion([entry])}, merge=True
    )


# ---- global_patterns ------------------------------------------------------


def lookup_pattern_by_entity(entity: str) -> Optional[GlobalPatternDoc]:
    fp = fingerprint_entity(entity)
    snap = db().collection("global_patterns").document(fp).get()
    if not snap.exists:
        return None
    return GlobalPatternDoc.model_validate(snap.to_dict())


def record_or_reinforce_pattern(
    entity: str,
    entity_type: str,
    manipulation_patterns: list[str],
    claimed_institution: Optional[str] = None,
) -> GlobalPatternDoc:
    """Called once a case is confirmed scam/likely_scam -- this is what
    makes AEGIS 'get smarter over time'. Never pass raw victim PII here;
    `entity` must be the scammer-side entity (domain/phone/handle), not
    anything identifying the reporting user."""
    fp = fingerprint_entity(entity)
    ref = db().collection("global_patterns").document(fp)
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def _txn(transaction: firestore.Transaction):
        snap = ref.get(transaction=transaction)
        if snap.exists:
            existing = GlobalPatternDoc.model_validate(snap.to_dict())
            existing.last_seen = now
            existing.report_count += 1
            existing.confidence = min(1.0, existing.confidence + 0.05)
            merged_patterns = sorted(set(existing.manipulation_patterns) | set(manipulation_patterns))
            existing.manipulation_patterns = merged_patterns  # type: ignore[assignment]
            transaction.set(ref, existing.model_dump(mode="python"))
            return existing
        else:
            new_doc = GlobalPatternDoc(
                pattern_id=fp,
                fingerprint=fp,
                entity_type=entity_type,
                manipulation_patterns=manipulation_patterns,  # type: ignore[arg-type]
                claimed_institution=claimed_institution,
                first_seen=now,
                last_seen=now,
                report_count=1,
                confidence=0.5,
            )
            transaction.set(ref, new_doc.model_dump(mode="python"))
            return new_doc

    return _txn(db().transaction())


def count_corroborating_reports(entity: str, within_days: int = 30) -> int:
    pattern = lookup_pattern_by_entity(entity)
    if pattern is None:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
    if pattern.last_seen < cutoff:
        return 0
    return pattern.report_count


# ---- family_links -----------------------------------------------------


def get_family_link(user_id: str) -> Optional[FamilyLinkDoc]:
    snap = db().collection("family_links").document(user_id).get()
    if not snap.exists:
        return None
    doc = FamilyLinkDoc.model_validate(snap.to_dict())
    return doc if doc.active else None


def upsert_family_link(doc: FamilyLinkDoc) -> None:
    db().collection("family_links").document(doc.user_id).set(doc.model_dump(mode="python"))


def deactivate_family_links_for_contact(family_contact_user_id: str) -> int:
    """Used by the STOP-FAMILY-ALERTS command: the *contact* (not the
    protected user) can revoke consent at any time. A contact may be
    linked from more than one protected user, so this deactivates every
    link naming them, not just one doc."""
    query = (
        db()
        .collection("family_links")
        .where(filter=FieldFilter("family_contact_user_id", "==", family_contact_user_id))
        .where(filter=FieldFilter("active", "==", True))
    )
    count = 0
    for snap in query.stream():
        snap.reference.set({"active": False}, merge=True)
        count += 1
    return count


# ---- pending_family_links -----------------------------------------------


def create_pending_family_link(doc: PendingFamilyLinkDoc) -> None:
    db().collection("pending_family_links").document(doc.code).set(doc.model_dump(mode="python"))


def get_pending_family_link(code: str) -> Optional[PendingFamilyLinkDoc]:
    snap = db().collection("pending_family_links").document(code.upper()).get()
    if not snap.exists:
        return None
    return PendingFamilyLinkDoc.model_validate(snap.to_dict())


def resolve_pending_family_link(code: str, status: PendingLinkStatus) -> None:
    db().collection("pending_family_links").document(code.upper()).set(
        {"status": status.value, "resolved_at": datetime.now(timezone.utc)}, merge=True
    )


# ---- user_history -----------------------------------------------------


def get_or_init_user_history(user_id: str) -> UserHistoryDoc:
    snap = db().collection("user_history").document(user_id).get()
    if snap.exists:
        return UserHistoryDoc.model_validate(snap.to_dict())
    return UserHistoryDoc(user_id=user_id)


def record_report_in_history(
    user_id: str, report_id: str, verdict: str, pattern_id: Optional[str]
) -> None:
    ref = db().collection("user_history").document(user_id)
    history = get_or_init_user_history(user_id)
    history.total_reports += 1
    if verdict in ("scam", "likely_scam"):
        history.scam_reports += 1
    history.last_report_id = report_id
    history.last_verdict = Verdict(verdict)
    history.last_seen = datetime.now(timezone.utc)
    if pattern_id and pattern_id not in history.known_pattern_ids:
        history.known_pattern_ids.append(pattern_id)
    ref.set(history.model_dump(mode="python"), merge=True)


# ---- pending_deletions / data erasure -----------------------------------


def create_pending_deletion(user_id: str, ttl_minutes: int = 10) -> None:
    doc = PendingDeletionDoc(
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    db().collection("pending_deletions").document(user_id).set(doc.model_dump(mode="python"))


def get_pending_deletion(user_id: str) -> Optional[PendingDeletionDoc]:
    snap = db().collection("pending_deletions").document(user_id).get()
    if not snap.exists:
        return None
    return PendingDeletionDoc.model_validate(snap.to_dict())


def delete_pending_deletion(user_id: str) -> None:
    db().collection("pending_deletions").document(user_id).delete()


def purge_user_data(user_id: str) -> dict[str, int]:
    """Erases everything AEGIS holds that's keyed to this user_id.
    Returns counts only (never content) so the caller can log/audit
    without ever touching what was deleted.

    Deliberately NOT touched: `global_patterns` -- those docs are
    anonymized scam-entity fingerprints shared across all users and never
    identify who reported them, so there is nothing of this user's to
    erase there. `pending_family_links` mentioning this user are left to
    expire on their own (harmless: only hashed ids + timestamps).

    IMPORTANT ordering: `user_directory` (their KMS-encrypted contact) is
    deleted LAST, since it's what lets AEGIS message them at all -- delete
    it before sending any confirmation and the confirmation can never be
    delivered.
    """
    counts: dict[str, int] = {}

    reports = list(
        db().collection("user_reports").where(filter=FieldFilter("user_id", "==", user_id)).stream()
    )
    for r in reports:
        r.reference.delete()
    counts["user_reports"] = len(reports)

    history_ref = db().collection("user_history").document(user_id)
    if history_ref.get().exists:
        history_ref.delete()
        counts["user_history"] = 1
    else:
        counts["user_history"] = 0

    own_link_ref = db().collection("family_links").document(user_id)
    if own_link_ref.get().exists:
        own_link_ref.delete()
        counts["family_links_owned"] = 1
    else:
        counts["family_links_owned"] = 0

    counts["family_links_as_contact_deactivated"] = deactivate_family_links_for_contact(user_id)

    directory_ref = db().collection("user_directory").document(user_id)
    if directory_ref.get().exists:
        directory_ref.delete()
        counts["user_directory"] = 1
    else:
        counts["user_directory"] = 0

    return counts
