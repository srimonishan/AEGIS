import os
from unittest.mock import patch

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")
os.environ["AEGIS_USER_ID_PEPPER"] = "test-pepper"

import bot_info_commands
from schemas.events import IncomingReport


def _report(text, content_type="text"):
    return IncomingReport(
        user_id="hashed-user",
        wa_id="15550001111",
        content_type=content_type,
        text_content=text,
        wa_message_id="wamid.x",
    )


def test_greeting_gets_humanized_agent_reply():
    with patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        handled = bot_info_commands.try_handle_command(_report("hi"))

    assert handled is True
    assert mock_send.call_args.args[0] == "hashed-user"
    assert "WhatsApp AI safety agent" in mock_send.call_args.args[1]


def test_owner_question_includes_creator_site():
    with patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        handled = bot_info_commands.try_handle_command(_report("who created this bot?"))

    assert handled is True
    assert "Created by Srimonishan" in mock_send.call_args.args[1] or "created by Srimonishan" in mock_send.call_args.args[1]
    assert "https://srimonishan.com/" in mock_send.call_args.args[1]


def test_bot_question_explains_whatsapp_bot():
    with patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        handled = bot_info_commands.try_handle_command(_report("what is AEGIS bot?"))

    assert handled is True
    body = mock_send.call_args.args[1]
    assert "WhatsApp-native AI scam detection bot" in body
    assert "https://wa.me/94764460037" in body


def test_suspicious_message_falls_through_to_agent():
    with patch("whatsapp_sender.send_whatsapp_text") as mock_send:
        handled = bot_info_commands.try_handle_command(
            _report("URGENT: Your bank account will be suspended. Click http://fake-bank.example/login")
        )

    assert handled is False
    assert not mock_send.called


def test_media_falls_through_to_agent():
    with patch("whatsapp_sender.send_whatsapp_text") as mock_send:
        handled = bot_info_commands.try_handle_command(_report(None, content_type="image"))

    assert handled is False
    assert not mock_send.called
