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
os.environ["AEGIS_USER_ID_PEPPER"] = "test-pepper"

import family_link_commands as flc
from schemas.enums import PendingLinkStatus
from schemas.events import IncomingReport
from schemas.firestore_models import PendingFamilyLinkDoc
from guardrails.pii import hash_user_id


def _report(text, user_id="requester-hash", wa_id="15550001111"):
    return IncomingReport(
        user_id=user_id,
        wa_id=wa_id,
        content_type="text",
        text_content=text,
        wa_message_id="wamid.x",
    )


def test_non_command_text_is_not_handled():
    with patch("whatsapp_sender.send_whatsapp_text") as mock_send:
        handled = flc.try_handle_command(_report("URGENT your account is suspended"))
    assert handled is False
    assert not mock_send.called


def test_link_family_creates_pending_request_and_messages_both_sides():
    with patch("contact_directory.remember_contact") as mock_remember, patch(
        "firestore_client.create_pending_family_link"
    ) as mock_create, patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        handled = flc.try_handle_command(_report("LINK FAMILY +1 (555) 000-2222"))

    assert handled is True
    assert mock_remember.called
    target_user_id_registered = mock_remember.call_args[0][0]
    assert mock_create.called
    pending_doc: PendingFamilyLinkDoc = mock_create.call_args[0][0]
    assert pending_doc.requester_user_id == "requester-hash"
    assert pending_doc.target_user_id == target_user_id_registered
    assert pending_doc.status == PendingLinkStatus.PENDING
    # both the target and the requester get a message
    recipients = {call.args[0] for call in mock_send.call_args_list}
    assert pending_doc.target_user_id in recipients
    assert "requester-hash" in recipients


def test_link_family_rejects_self_link():
    self_wa_id = "15550009999"
    self_user_id = hash_user_id(self_wa_id)
    with patch("contact_directory.remember_contact") as mock_remember, patch(
        "firestore_client.create_pending_family_link"
    ) as mock_create, patch("whatsapp_sender.send_whatsapp_text", return_value=True):
        handled = flc.try_handle_command(_report(f"LINK FAMILY {self_wa_id}", user_id=self_user_id))

    assert handled is True
    assert not mock_remember.called
    assert not mock_create.called


def test_link_family_rejects_too_short_number():
    with patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send, patch(
        "firestore_client.create_pending_family_link"
    ) as mock_create:
        handled = flc.try_handle_command(_report("LINK FAMILY 123"))
    assert handled is True
    assert not mock_create.called
    assert mock_send.called


def test_confirm_link_success_creates_family_link():
    pending = PendingFamilyLinkDoc(
        code="ABC123",
        requester_user_id="requester-hash",
        target_user_id="target-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    with patch("firestore_client.get_pending_family_link", return_value=pending), patch(
        "firestore_client.upsert_family_link"
    ) as mock_upsert, patch(
        "firestore_client.resolve_pending_family_link"
    ) as mock_resolve, patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send:
        handled = flc.try_handle_command(_report("CONFIRM LINK ABC123", user_id="target-hash"))

    assert handled is True
    mock_upsert.assert_called_once()
    linked_doc = mock_upsert.call_args[0][0]
    assert linked_doc.user_id == "requester-hash"
    assert linked_doc.family_contact_user_id == "target-hash"
    mock_resolve.assert_called_once_with("ABC123", PendingLinkStatus.CONFIRMED)
    assert mock_send.call_count == 2


def test_confirm_link_rejected_from_wrong_number():
    pending = PendingFamilyLinkDoc(
        code="ABC123",
        requester_user_id="requester-hash",
        target_user_id="target-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    with patch("firestore_client.get_pending_family_link", return_value=pending), patch(
        "firestore_client.upsert_family_link"
    ) as mock_upsert, patch("whatsapp_sender.send_whatsapp_text", return_value=True):
        handled = flc.try_handle_command(_report("CONFIRM LINK ABC123", user_id="some-other-hash"))

    assert handled is True
    assert not mock_upsert.called


def test_confirm_link_expired():
    pending = PendingFamilyLinkDoc(
        code="ABC123",
        requester_user_id="requester-hash",
        target_user_id="target-hash",
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    with patch("firestore_client.get_pending_family_link", return_value=pending), patch(
        "firestore_client.resolve_pending_family_link"
    ) as mock_resolve, patch("firestore_client.upsert_family_link") as mock_upsert, patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ):
        handled = flc.try_handle_command(_report("CONFIRM LINK ABC123", user_id="target-hash"))

    assert handled is True
    assert not mock_upsert.called
    mock_resolve.assert_called_once_with("ABC123", PendingLinkStatus.EXPIRED)


def test_confirm_link_unknown_code():
    with patch("firestore_client.get_pending_family_link", return_value=None), patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send:
        handled = flc.try_handle_command(_report("CONFIRM LINK ZZZZZZ"))
    assert handled is True
    assert mock_send.called


def test_stop_family_alerts_deactivates_links():
    with patch("firestore_client.deactivate_family_links_for_contact", return_value=2) as mock_deactivate, patch(
        "whatsapp_sender.send_whatsapp_text", return_value=True
    ) as mock_send:
        handled = flc.try_handle_command(_report("STOP FAMILY ALERTS", user_id="target-hash"))

    assert handled is True
    mock_deactivate.assert_called_once_with("target-hash")
    assert mock_send.called


def test_decline_link():
    pending = PendingFamilyLinkDoc(
        code="ABC123",
        requester_user_id="requester-hash",
        target_user_id="target-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    with patch("firestore_client.get_pending_family_link", return_value=pending), patch(
        "firestore_client.resolve_pending_family_link"
    ) as mock_resolve, patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        handled = flc.try_handle_command(_report("DECLINE LINK ABC123", user_id="target-hash"))

    assert handled is True
    mock_resolve.assert_called_once_with("ABC123", PendingLinkStatus.DECLINED)
    assert mock_send.call_count == 2
