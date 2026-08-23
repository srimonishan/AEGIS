"""
AEGIS ingestion service.

Single responsibility: receive a WhatsApp webhook call, verify it's
actually from Meta, normalize it into a typed IncomingReport, publish it
to Pub/Sub, and return. No scam analysis, no Firestore access, no Gemini
calls happen here -- that IAM boundary is deliberate (see
infra/terraform/iam.tf): if this service is ever compromised via a
malicious payload, the blast radius is "can publish events", not "can
read every user's case history".
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response

from schemas.enums import ContentType
from schemas.events import IncomingReport
from guardrails import hash_user_id

from config import settings
from media import MediaResolutionError, resolve_media_to_gcs
from normalize import RawMessage, parse_webhook_payload
from publisher import publish_incoming_report
from signature import verify_meta_signature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegis.ingestion")

app = FastAPI(title="AEGIS Ingestion Service")

_TYPE_MAP = {
    "text": ContentType.TEXT,
    "image": ContentType.IMAGE,
    "audio": ContentType.AUDIO,
    "video": ContentType.VIDEO,
    "document": ContentType.TEXT,  # treated as text-with-attachment note for now
}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    # Meta's verification handshake uses dotted query param names
    # (hub.mode, hub.verify_token, hub.challenge) which aren't valid Python
    # identifiers, so we read them off the raw query params instead of
    # declaring them as FastAPI function parameters.
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == settings.meta_verify_token and challenge:
        return Response(content=challenge, media_type="text/plain", status_code=200)
    logger.warning("webhook_verification_failed")
    return Response(status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_meta_signature(raw_body, signature, settings.meta_app_secret):
        logger.warning("webhook_signature_verification_failed")
        return Response(status_code=401)

    body = await request.json()
    raw_messages = parse_webhook_payload(body)

    published_ids: list[str] = []
    for raw in raw_messages:
        try:
            report = _build_incoming_report(raw)
        except Exception:
            logger.exception(
                "failed_to_build_incoming_report", extra={"wa_message_id": raw.wa_message_id}
            )
            continue

        try:
            msg_id = publish_incoming_report(report)
            published_ids.append(msg_id)
            logger.info(
                "published_incoming_report",
                extra={
                    "report_id": report.report_id,
                    "content_type": report.content_type.value,
                    "pubsub_message_id": msg_id,
                },
            )
        except Exception:
            logger.exception(
                "failed_to_publish_incoming_report", extra={"report_id": report.report_id}
            )

    # WhatsApp only cares that we returned 200 quickly; the body is ignored.
    return {"received": len(raw_messages), "published": len(published_ids)}


def _build_incoming_report(raw: RawMessage) -> IncomingReport:
    content_type = _TYPE_MAP.get(raw.msg_type, ContentType.TEXT)
    media_gcs_uri = None
    media_mime_type = raw.media_mime_type
    text_content = raw.text_body

    if raw.media_id:
        try:
            media_gcs_uri, media_mime_type = resolve_media_to_gcs(
                raw.media_id, raw.wa_message_id
            )
        except MediaResolutionError:
            logger.exception(
                "media_resolution_failed", extra={"wa_message_id": raw.wa_message_id}
            )
            text_content = (text_content or "") + " [media could not be retrieved]"

    return IncomingReport(
        user_id=hash_user_id(raw.wa_id),
        wa_id=raw.wa_id,
        content_type=content_type,
        text_content=text_content,
        media_gcs_uri=media_gcs_uri,
        media_mime_type=media_mime_type,
        wa_message_id=raw.wa_message_id,
    )
