import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")
os.environ.setdefault("AEGIS_USER_ID_PEPPER", "test-pepper")

import data_deletion_commands as ddc
from schemas.events import IncomingReport
from schemas.firestore_models import PendingDeletionDoc


def _report(text, user_id="u1"):
    return IncomingReport(
        user_id=user_id, wa_id="15550001111", content_type="text", text_content=text,
        wa_message_id="wamid.x",
    )


def test_non_command_not_handled():
    with patch("whatsapp_sender.send_whatsapp_text") as mock_send:
        assert ddc.try_handle_command(_report("hello there")) is False
    assert not mock_send.called


def test_delete_my_data_starts_pending_window():
    with patch("firestore_client.create_pending_deletion") as mock_create, patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send:
        handled = ddc.try_handle_command(_report("delete my data"))
    assert handled is True
    mock_create.assert_called_once_with("u1")
    assert mock_send.called


def test_confirm_without_pending_request():
    with patch("firestore_client.get_pending_deletion", return_value=None), patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send, patch("firestore_client.purge_user_data") as mock_purge:
        handled = ddc.try_handle_command(_report("DELETE MY DATA CONFIRM"))
    assert handled is True
    assert not mock_purge.called
    assert mock_send.called


def test_confirm_after_expiry_does_not_purge():
    pending = PendingDeletionDoc(user_id="u1", expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    with patch("firestore_client.get_pending_deletion", return_value=pending), patch(
        "firestore_client.delete_pending_deletion"
    ) as mock_del, patch("firestore_client.purge_user_data") as mock_purge, patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ):
        handled = ddc.try_handle_command(_report("DELETE MY DATA CONFIRM"))
    assert handled is True
    assert not mock_purge.called
    mock_del.assert_called_once_with("u1")


def test_confirm_within_window_purges_and_sends_notice_first():
    pending = PendingDeletionDoc(user_id="u1", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
    call_order = []
    with patch("firestore_client.get_pending_deletion", return_value=pending), patch(
        "firestore_client.delete_pending_deletion"
    ) as mock_del, patch(
        "firestore_client.purge_user_data",
        side_effect=lambda uid: call_order.append("purge") or {"user_reports": 2},
    ) as mock_purge, patch(
        "whatsapp_sender.send_whatsapp_text",
        side_effect=lambda uid, body: call_order.append("send") or True,
    ) as mock_send:
        handled = ddc.try_handle_command(_report("DELETE MY DATA CONFIRM"))

    assert handled is True
    mock_purge.assert_called_once_with("u1")
    mock_del.assert_called_once_with("u1")
    assert mock_send.called
    # The confirmation must be sent BEFORE the purge deletes user_directory
    # (their contact) -- otherwise it can never be delivered.
    assert call_order == ["send", "purge"]
