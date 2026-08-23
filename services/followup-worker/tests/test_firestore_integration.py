"""
Integration test against a REAL Firestore emulator (not mocks). Skipped
unless FIRESTORE_EMULATOR_HOST is set.

Why this test exists: `model_dump(mode="json")` turns every datetime
field into an ISO string, and Firestore silently excludes a
string-valued field from a `<=` range query against a datetime query
value -- no error, just zero results, forever. Every unit test in
test_main.py mocks `firestore_client.due_follow_ups` directly, so none of
them would ever catch that. This test writes through the real
`schedule_next_follow_up` helper and queries through the real
`due_follow_ups` helper, against a real (emulated) Firestore, so a
regression back to `mode="json"` on a datetime field fails here instead
of silently shipping.

Run locally with:
    docker run -d --rm -p 8090:8080 gcr.io/google.com/cloudsdktool/cloud-sdk:emulators \\
        gcloud emulators firestore start --host-port=0.0.0.0:8080 --database-mode=firestore-native
    FIRESTORE_EMULATOR_HOST=localhost:8090 pytest tests/test_firestore_integration.py
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="requires a running Firestore emulator (see module docstring)",
)

import firestore_client  # noqa: E402  (import after env/skip setup)


def test_due_follow_ups_actually_finds_a_past_due_record():
    report_id = f"r-{uuid.uuid4().hex[:8]}"
    user_id = f"u-{uuid.uuid4().hex[:8]}"

    # Schedule one due 1 hour ago (should be found) and one due in 1 hour
    # (should NOT be found) -- proves both the "written as a queryable
    # native datetime" fix and that the range condition itself is correct.
    firestore_client.schedule_next_follow_up(
        report_id=report_id, user_id=user_id, reason="past due", hours=-1
    )
    firestore_client.schedule_next_follow_up(
        report_id=report_id, user_id=user_id, reason="not due yet", hours=1
    )

    due = firestore_client.due_follow_ups(limit=100)
    due_reasons_for_this_report = {f.reason for f in due if f.report_id == report_id}

    assert "past due" in due_reasons_for_this_report
    assert "not due yet" not in due_reasons_for_this_report


def test_mark_done_removes_it_from_future_due_queries():
    report_id = f"r-{uuid.uuid4().hex[:8]}"
    user_id = f"u-{uuid.uuid4().hex[:8]}"
    firestore_client.schedule_next_follow_up(
        report_id=report_id, user_id=user_id, reason="to be completed", hours=-1
    )

    due = firestore_client.due_follow_ups(limit=200)
    match = next(f for f in due if f.report_id == report_id)
    firestore_client.mark_follow_up_done(match.follow_up_id)

    due_after = firestore_client.due_follow_ups(limit=200)
    assert match.follow_up_id not in {f.follow_up_id for f in due_after}
