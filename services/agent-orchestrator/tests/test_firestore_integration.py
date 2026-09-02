"""
Integration tests against a REAL Firestore emulator (not mocks). Skipped
unless FIRESTORE_EMULATOR_HOST is set -- see
services/followup-worker/tests/test_firestore_integration.py's docstring
for why this class of test exists (mode="json" silently breaking
datetime range/comparison semantics) and how to run it locally.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from google.cloud.firestore_v1.base_query import FieldFilter

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.5-flash")
os.environ.setdefault("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("AEGIS_USER_ID_PEPPER", "test-pepper")

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="requires a running Firestore emulator",
)

import firestore_client  # noqa: E402
from schemas.enums import CaseStatus, ManipulationPattern, PendingLinkStatus, Verdict  # noqa: E402
from schemas.firestore_models import FamilyLinkDoc, PendingFamilyLinkDoc, UserReportDoc  # noqa: E402


def test_pending_family_link_round_trips_with_comparable_expiry():
    code = uuid.uuid4().hex[:6].upper()
    doc = PendingFamilyLinkDoc(
        code=code,
        requester_user_id="req-1",
        target_user_id="tgt-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    firestore_client.create_pending_family_link(doc)

    fetched = firestore_client.get_pending_family_link(code)
    assert fetched is not None
    assert fetched.status == PendingLinkStatus.PENDING
    # The whole point: this must be a real, comparable datetime, not a
    # string -- family_link_commands.py compares it directly against
    # datetime.now(timezone.utc).
    assert fetched.expires_at > datetime.now(timezone.utc)

    firestore_client.resolve_pending_family_link(code, PendingLinkStatus.CONFIRMED)
    resolved = firestore_client.get_pending_family_link(code)
    assert resolved.status == PendingLinkStatus.CONFIRMED
    assert resolved.resolved_at is not None


def test_family_link_lifecycle_and_stop_command_query():
    requester = f"req-{uuid.uuid4().hex[:8]}"
    contact = f"contact-{uuid.uuid4().hex[:8]}"

    firestore_client.upsert_family_link(
        FamilyLinkDoc(user_id=requester, family_contact_user_id=contact)
    )
    link = firestore_client.get_family_link(requester)
    assert link is not None
    assert link.active is True
    assert link.family_contact_user_id == contact

    # This is the real query STOP FAMILY ALERTS relies on -- proves the
    # where(family_contact_user_id==) + where(active==) filter actually
    # finds and deactivates the doc.
    deactivated = firestore_client.deactivate_family_links_for_contact(contact)
    assert deactivated == 1
    assert firestore_client.get_family_link(requester) is None


def test_purge_user_data_actually_erases_everything_real():
    user_id = f"purge-{uuid.uuid4().hex[:8]}"
    contact_id = f"purge-contact-{uuid.uuid4().hex[:8]}"

    # Seed real docs across every collection purge_user_data touches.
    firestore_client.upsert_user_report(
        UserReportDoc(report_id=f"r-{uuid.uuid4().hex[:6]}", user_id=user_id, status=CaseStatus.CLOSED)
    )
    firestore_client.upsert_user_report(
        UserReportDoc(report_id=f"r-{uuid.uuid4().hex[:6]}", user_id=user_id, status=CaseStatus.CLOSED)
    )
    firestore_client.record_report_in_history(user_id, "r-x", "safe", None)
    firestore_client.upsert_family_link(
        FamilyLinkDoc(user_id=user_id, family_contact_user_id=contact_id)
    )
    # user_id is ALSO someone else's family contact -- must be deactivated, not deleted.
    other_requester = f"other-{uuid.uuid4().hex[:8]}"
    firestore_client.upsert_family_link(
        FamilyLinkDoc(user_id=other_requester, family_contact_user_id=user_id)
    )
    firestore_client.db().collection("user_directory").document(user_id).set(
        {"user_id": user_id, "encrypted_wa_id": "ZmFrZQ==", "updated_at": datetime.now(timezone.utc)}
    )

    counts = firestore_client.purge_user_data(user_id)

    assert counts["user_reports"] == 2
    assert counts["user_history"] == 1
    assert counts["family_links_owned"] == 1
    assert counts["family_links_as_contact_deactivated"] == 1
    assert counts["user_directory"] == 1

    # And it's actually gone, not just counted.
    assert firestore_client.get_family_link(user_id) is None
    assert not firestore_client.db().collection("user_history").document(user_id).get().exists
    assert not firestore_client.db().collection("user_directory").document(user_id).get().exists
    remaining_reports = list(
        firestore_client.db()
        .collection("user_reports")
        .where(filter=FieldFilter("user_id", "==", user_id))
        .stream()
    )
    assert remaining_reports == []
    # The other person's own link (they're the protected user, not the
    # contact) is untouched -- only the specific link naming user_id as
    # the CONTACT gets deactivated.
    other_link = firestore_client.get_family_link(other_requester)
    assert other_link is None  # deactivated (active=False), so the getter correctly returns None


def test_later_partial_upsert_does_not_clobber_earlier_verdict_and_trace():
    """Reproduces a real bug found by actually running the full agent loop:
    draft_protective_action writes verdict/confidence/report_draft, then
    escalate_or_close writes only {report_id, user_id, status} -- without
    exclude_unset=True, that second write nulls out everything the first
    one wrote, because Firestore's merge=True still replaces any field
    that IS present in the payload dict, and model_dump() without
    exclude_unset includes every field at its Python default."""
    report_id = f"r-{uuid.uuid4().hex[:8]}"
    user_id = f"u-{uuid.uuid4().hex[:8]}"

    # Step 1: draft_protective_action's write (a real verdict + trace entries).
    firestore_client.upsert_user_report(
        UserReportDoc(
            report_id=report_id,
            user_id=user_id,
            status=CaseStatus.OPEN,
            verdict=Verdict.SCAM,
            confidence=0.93,
            manipulation_patterns=[ManipulationPattern.URGENCY],
            plain_language_explanation="This looks like a phishing scam.",
            report_draft="User received a phishing message.",
        )
    )
    firestore_client.append_reasoning_trace(report_id, {"tool": "analyze_content", "phase": "start"})
    firestore_client.append_reasoning_trace(report_id, {"tool": "analyze_content", "phase": "end"})

    # Step 2: escalate_or_close's write -- ONLY status, nothing else.
    firestore_client.upsert_user_report(
        UserReportDoc(report_id=report_id, user_id=user_id, status=CaseStatus.CLOSED)
    )

    # The verdict, confidence, report content, and trace from step 1 must
    # all have survived step 2's partial update.
    final = firestore_client.get_user_report(report_id)
    assert final.status == CaseStatus.CLOSED  # step 2's actual change did apply
    assert final.verdict == Verdict.SCAM
    assert final.confidence == 0.93
    assert final.manipulation_patterns == [ManipulationPattern.URGENCY]
    assert final.plain_language_explanation == "This looks like a phishing scam."
    assert final.report_draft == "User received a phishing message."
    assert len(final.reasoning_trace) == 2
