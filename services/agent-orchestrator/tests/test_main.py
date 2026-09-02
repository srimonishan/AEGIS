import base64
import json
import os
from unittest.mock import AsyncMock, patch

os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
os.environ.setdefault("META_ACCESS_TOKEN", "x")
os.environ.setdefault("META_PHONE_NUMBER_ID", "x")
os.environ.setdefault("GLOBAL_PATTERN_SALT", "test-salt")
os.environ.setdefault(
    "CONTACT_DIRECTORY_KMS_KEY", "projects/test/locations/us/keyRings/r/cryptoKeys/k"
)
os.environ.setdefault("AEGIS_USER_ID_PEPPER", "test-pepper")
os.environ["VERIFY_PUBSUB_PUSH_OIDC"] = "false"

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def _envelope(report_dict: dict) -> dict:
    data = base64.b64encode(json.dumps(report_dict).encode()).decode()
    return {"message": {"data": data, "messageId": "m1"}, "subscription": "sub1"}


REPORT = {
    "report_id": "r1",
    "user_id": "hashed-abc",
    "wa_id": "15551234567",
    "content_type": "text",
    "text_content": "hello",
    "wa_message_id": "wamid.1",
}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_valid_push_triggers_processing():
    with patch.object(main, "_process_report", new=AsyncMock()) as mock_process:
        r = client.post("/pubsub/push", json=_envelope(REPORT))
        assert r.status_code == 200
        assert mock_process.called
        processed_report = mock_process.call_args[0][0]
        assert processed_report.report_id == "r1"
        assert processed_report.wa_id == "15551234567"


def test_malformed_data_acked_not_retried():
    with patch.object(main, "_process_report", new=AsyncMock()) as mock_process:
        r = client.post(
            "/pubsub/push",
            json={"message": {"data": base64.b64encode(b"not json").decode()}},
        )
        assert r.status_code == 200
        assert not mock_process.called


def test_missing_data_field_acked():
    r = client.post("/pubsub/push", json={"message": {}})
    assert r.status_code == 200


def test_processing_exception_returns_500_for_retry():
    with patch.object(main, "_process_report", new=AsyncMock(side_effect=RuntimeError("boom"))):
        r = client.post("/pubsub/push", json=_envelope(REPORT))
        assert r.status_code == 500


def test_quota_exhaustion_sends_user_visible_fallback_and_acks():
    with patch.object(
        main,
        "_process_report",
        new=AsyncMock(side_effect=RuntimeError("429 RESOURCE_EXHAUSTED")),
    ), patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        r = client.post("/pubsub/push", json=_envelope(REPORT))

    assert r.status_code == 200
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "hashed-abc"
    assert "temporarily rate-limited" in mock_send.call_args[0][1]


def test_model_not_found_sends_user_visible_fallback_and_acks():
    with patch.object(
        main,
        "_process_report",
        new=AsyncMock(side_effect=RuntimeError("404 NOT_FOUND Publisher model was not found")),
    ), patch("whatsapp_sender.send_whatsapp_text", return_value=True) as mock_send:
        r = client.post("/pubsub/push", json=_envelope(REPORT))

    assert r.status_code == 200
    mock_send.assert_called_once()
    assert mock_send.call_args[0][0] == "hashed-abc"
    assert "cannot reach its AI analysis model" in mock_send.call_args[0][1]
