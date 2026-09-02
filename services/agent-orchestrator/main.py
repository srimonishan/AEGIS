"""
AEGIS agent orchestrator: consumes `incoming-reports` (via a Pub/Sub push
subscription hitting POST /pubsub/push), runs the ADK agent through its
guardrail-wrapped tool-calling loop, and lets the agent's own tool calls
persist to Firestore / reply on WhatsApp / schedule follow-ups.

This is the ONLY service with Firestore read/write, Gemini/Vertex AI, and
outbound WhatsApp-send access -- see infra/terraform/iam.tf for the
service-account scoping that makes that a real boundary, not just a
comment.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid

from fastapi import FastAPI, Request, Response
from google.adk.runners import InMemoryRunner
from google.genai import types

import contact_directory
import data_deletion_commands
import family_link_commands
import whatsapp_sender
from aegis_agent import build_agent
from guardrails import GuardrailPipeline
from pubsub_auth import verify_push_request
from schemas.events import IncomingReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegis.orchestrator")

app = FastAPI(title="AEGIS Agent Orchestrator")

_agent = build_agent()
_APP_NAME = "aegis"


# NOTE: deliberately "/health", not "/healthz" -- see the identical note
# in services/ingestion/main.py. Google's front-end intercepts the exact
# path "/healthz" on a Cloud Run service's default *.run.app domain
# before it reaches the container; only found by deploying to real GCP.
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/pubsub/push")
async def pubsub_push(request: Request):
    if not verify_push_request(request):
        return Response(status_code=401)

    envelope = await request.json()
    message = envelope.get("message", {})
    data_b64 = message.get("data")
    if not data_b64:
        # Malformed push -- ack anyway so Pub/Sub doesn't retry forever on
        # something that will never parse.
        logger.warning("pubsub_push_missing_data")
        return Response(status_code=200)

    try:
        raw = base64.b64decode(data_b64)
        report = IncomingReport.model_validate(json.loads(raw))
    except Exception:
        logger.exception("failed_to_parse_incoming_report")
        return Response(status_code=200)  # permanent parse failure, don't retry

    try:
        await _process_report(report)
    except Exception as exc:
        if _is_quota_exhausted(exc):
            logger.exception("report_processing_quota_exhausted", extra={"report_id": report.report_id})
            whatsapp_sender.send_whatsapp_text(
                report.user_id,
                "I received your message, but AEGIS is temporarily rate-limited while analyzing it. "
                "Please try again in a few minutes.",
            )
            return Response(status_code=200)
        if _is_model_unavailable(exc):
            logger.exception("report_processing_model_unavailable", extra={"report_id": report.report_id})
            whatsapp_sender.send_whatsapp_text(
                report.user_id,
                "I received your message, but AEGIS cannot reach its AI analysis model right now. "
                "Please try again shortly.",
            )
            return Response(status_code=200)
        logger.exception("report_processing_failed", extra={"report_id": report.report_id})
        return Response(status_code=500)  # transient failure -- let Pub/Sub retry

    return Response(status_code=200)


def _is_quota_exhausted(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "RESOURCE_EXHAUSTED" in text or "429" in text


def _is_model_unavailable(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    return "NOT_FOUND" in text or "404" in text or "model" in text.lower() and "not found" in text.lower()


async def _process_report(report: IncomingReport) -> None:
    # Best-effort: register the contact so draft_protective_action can
    # reply. Never let this block scam analysis.
    contact_directory.remember_contact(report.user_id, report.wa_id)

    # Family-link opt-in commands are deterministic string matches, handled
    # entirely BEFORE guardrail sanitization or any Gemini call -- see
    # family_link_commands.py's module docstring for why that separation
    # matters (a forwarded scam message must never be able to trigger a
    # family-link side effect via the LLM's tool-calling loop).
    if family_link_commands.try_handle_command(report):
        logger.info("handled_family_link_command", extra={"report_id": report.report_id})
        return

    # Same reasoning, for data-erasure requests -- see
    # data_deletion_commands.py's module docstring.
    if data_deletion_commands.try_handle_command(report):
        logger.info("handled_data_deletion_command", extra={"report_id": report.report_id})
        return

    guardrail_result = GuardrailPipeline.run(report.text_content or "")
    wrapped_content = GuardrailPipeline.wrap_for_prompt(guardrail_result.sanitized_text)

    if report.media_gcs_uri:
        media_note = (
            f"\n[The user also attached {report.content_type.value} media at "
            f"{report.media_gcs_uri} ({report.media_mime_type}). Consider it part "
            "of the forwarded content.]"
        )
        wrapped_content += media_note

    logger.info(
        "processing_report",
        extra={
            "report_id": report.report_id,
            "content_type": report.content_type.value,
            "risk_flags": guardrail_result.risk_flags,
            "injection_suspected": guardrail_result.injection_suspected,
        },
    )

    runner = InMemoryRunner(agent=_agent, app_name=_APP_NAME)
    session_id = report.report_id
    await runner.session_service.create_session(
        app_name=_APP_NAME,
        user_id=report.user_id,
        session_id=session_id,
        state={"report_id": report.report_id, "user_id": report.user_id},
    )

    parts = [types.Part(text=wrapped_content)]
    if report.media_gcs_uri and report.media_mime_type and report.content_type.value in (
        "image",
        "video",
    ):
        parts.append(
            types.Part(
                file_data=types.FileData(
                    file_uri=report.media_gcs_uri, mime_type=report.media_mime_type
                )
            )
        )

    async for event in runner.run_async(
        user_id=report.user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=parts),
    ):
        logger.debug("agent_event", extra={"report_id": report.report_id, "event_id": getattr(event, "id", None)})
