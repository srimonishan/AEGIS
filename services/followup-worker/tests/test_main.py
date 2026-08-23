import os
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")

import main
from schemas.enums import CaseStatus
from schemas.firestore_models import FollowUpDoc, UserReportDoc

NOW = datetime.now(timezone.utc)


def _followup(attempt=1, pattern_id="p1"):
    return FollowUpDoc(
        follow_up_id="f1",
        report_id="r1",
        user_id="u1",
        reason="test",
        not_before=NOW,
        attempt=attempt,
    )


def _report(status=CaseStatus.MONITORING, pattern_id="p1"):
    return UserReportDoc(report_id="r1", user_id="u1", status=status, matched_pattern_id=pattern_id)


def test_escalates_when_corroboration_grew():
    with patch("firestore_client.get_user_report", return_value=_report()), patch(
        "firestore_client.get_pattern_report_count", return_value=5
    ), patch("firestore_client.append_reasoning_trace"), patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send, patch(
        "firestore_client.upsert_user_report_status"
    ) as mock_status, patch(
        "firestore_client.schedule_next_follow_up"
    ) as mock_schedule:
        main._process_one(_followup())

    assert mock_send.called
    mock_status.assert_called_once_with("r1", "u1", status=CaseStatus.ESCALATED)
    assert not mock_schedule.called


def test_closes_after_max_cycles_with_nothing_new():
    with patch("firestore_client.get_user_report", return_value=_report()), patch(
        "firestore_client.get_pattern_report_count", return_value=0
    ), patch("firestore_client.append_reasoning_trace"), patch(
        "whatsapp_sender.send_whatsapp_text"
    ) as mock_send, patch(
        "firestore_client.upsert_user_report_status"
    ) as mock_status, patch(
        "firestore_client.schedule_next_follow_up"
    ) as mock_schedule:
        main._process_one(_followup(attempt=3))  # == MAX_FOLLOW_UP_CYCLES default (3)

    assert not mock_send.called
    mock_status.assert_called_once_with("r1", "u1", status=CaseStatus.CLOSED)
    assert not mock_schedule.called


def test_reschedules_when_nothing_new_and_cycles_remain():
    with patch("firestore_client.get_user_report", return_value=_report()), patch(
        "firestore_client.get_pattern_report_count", return_value=0
    ), patch("firestore_client.append_reasoning_trace"), patch(
        "whatsapp_sender.send_whatsapp_text"
    ) as mock_send, patch(
        "firestore_client.upsert_user_report_status"
    ) as mock_status, patch(
        "firestore_client.schedule_next_follow_up"
    ) as mock_schedule:
        main._process_one(_followup(attempt=1))

    assert not mock_send.called
    assert not mock_status.called
    mock_schedule.assert_called_once()
    assert mock_schedule.call_args.kwargs["attempt"] == 2


def test_skips_case_whose_status_already_changed():
    with patch("firestore_client.get_user_report", return_value=_report(status=CaseStatus.CLOSED)), patch(
        "firestore_client.get_pattern_report_count"
    ) as mock_count, patch("whatsapp_sender.send_whatsapp_text") as mock_send:
        main._process_one(_followup())

    assert not mock_count.called
    assert not mock_send.called


def test_process_due_follow_ups_marks_failed_on_exception():
    with patch("firestore_client.due_follow_ups", return_value=[_followup()]), patch(
        "main._process_one", side_effect=RuntimeError("boom")
    ), patch("firestore_client.mark_follow_up_failed") as mock_failed, patch(
        "firestore_client.mark_follow_up_done"
    ) as mock_done:
        processed = main.process_due_follow_ups()

    assert processed == 0
    mock_failed.assert_called_once_with("f1")
    assert not mock_done.called
