import hashlib
import hmac

from signature import verify_meta_signature

APP_SECRET = "test-app-secret"


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_accepted():
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(body)
    assert verify_meta_signature(body, header, APP_SECRET) is True


def test_tampered_body_rejected():
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(body)
    tampered = body + b"x"
    assert verify_meta_signature(tampered, header, APP_SECRET) is False


def test_wrong_secret_rejected():
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(body, secret="wrong-secret")
    assert verify_meta_signature(body, header, APP_SECRET) is False


def test_missing_header_rejected():
    body = b'{"object":"whatsapp_business_account"}'
    assert verify_meta_signature(body, None, APP_SECRET) is False


def test_malformed_header_rejected():
    body = b'{"object":"whatsapp_business_account"}'
    assert verify_meta_signature(body, "not-a-valid-header", APP_SECRET) is False
