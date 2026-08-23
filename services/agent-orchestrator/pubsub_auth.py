"""
Verifies that a Pub/Sub push request actually came from Google's Pub/Sub
service (not an attacker who found the Cloud Run URL). Push subscriptions
are configured (see infra/terraform/pubsub.tf) with a dedicated invoker
service account and OIDC token; we verify that token's signature and
audience here.
"""

from __future__ import annotations

import logging

from fastapi import Request
from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token

from config import settings

logger = logging.getLogger("aegis.orchestrator.pubsub_auth")

_google_request = ga_requests.Request()


def verify_push_request(request: Request) -> bool:
    if not settings.verify_pubsub_push_oidc:
        return True  # local/manual testing only

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        logger.warning("pubsub_push_missing_bearer_token")
        return False
    token = auth_header.split(" ", 1)[1]

    try:
        claims = id_token.verify_oauth2_token(
            token, _google_request, audience=settings.pubsub_push_audience or None
        )
    except Exception:
        logger.exception("pubsub_push_token_verification_failed")
        return False

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning("pubsub_push_unexpected_issuer", extra={"iss": claims.get("iss")})
        return False
    return True
