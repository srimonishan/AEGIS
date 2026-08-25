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


# NOTE: deliberately "/health", not "/healthz" -- on a Cloud Run service's
# default *.run.app domain, Google's own front-end intercepts requests to
# the literal path "/healthz" before they ever reach the container
# (a legacy reserved health-check path from Kubernetes/Knative-era
# serving infra) and answers with Google's generic 404 page instead of
# forwarding the request. Discovered by actually deploying to a real GCP
# project: every other path, including ones that don't exist, correctly
# reached the app and got its own {"detail":"Not Found"}; only the exact
# string "/healthz" never once reached the container, regardless of
# auth, IAM, or how long we waited. No local Docker test can catch this
# since it's specific to Cloud Run's real serving edge.
@app.get("/health")
def health():
    return {"status": "ok"}


# Meta requires a reachable privacy policy URL before an app can be
# published (even for WhatsApp test-number-only use) -- see App
# Dashboard > Publish. Served as plain HTML directly from this service
# rather than a separate hosted page, since this domain is already
# public and TLS-terminated. Kept honest and specific to what AEGIS
# actually does (see shared/guardrails and firestore_client.py's
# purge_user_data) rather than generic boilerplate.
_PRIVACY_POLICY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>AEGIS Scam Guard -- Privacy Policy</title></head>
<body style="font-family: sans-serif; max-width: 640px; margin: 2rem auto; line-height: 1.6;">
<h1>Privacy Policy -- AEGIS Scam Guard</h1>
<p>AEGIS is a WhatsApp-based assistant that helps you check whether a
message you received is a scam. This page explains what we do with
your data.</p>

<h2>What we receive</h2>
<p>When you forward a message to AEGIS, we receive the message content
(text, or the image/audio you send) and your WhatsApp number.</p>

<h2>What we do with it</h2>
<ul>
<li>Your WhatsApp number is one-way cryptographically hashed before
being used as an internal identifier or stored in our database -- we
do not store it in plain, reversible form except briefly, encrypted,
solely so we can send you our reply.</li>
<li>The message you forward is analyzed by an AI model to judge
whether it's a scam, and a plain-language explanation is sent back to
you on WhatsApp.</li>
<li>If the message matches a scam pattern, an anonymized fingerprint of
the scam (never anything identifying you) may be stored so we can
recognize the same scam if others report it.</li>
<li>We never sell your data or use it for advertising.</li>
</ul>

<h2>Family notifications</h2>
<p>AEGIS can optionally notify a family contact you explicitly opt in
via the <code>LINK FAMILY</code> command. Nothing is ever shared with a
family contact without that explicit opt-in, and either side can
revoke it at any time (<code>STOP FAMILY ALERTS</code>).</p>

<h2>Deleting your data</h2>
<p>Send <code>DELETE MY DATA</code> to AEGIS on WhatsApp at any time.
After a confirmation step, every record we hold that is tied to you is
permanently erased.</p>

<h2>Contact</h2>
<p>Questions about this policy can be sent to the WhatsApp number this
app is connected to.</p>
</body></html>"""


@app.get("/privacy")
def privacy_policy():
    return Response(content=_PRIVACY_POLICY_HTML, media_type="text/html")


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
