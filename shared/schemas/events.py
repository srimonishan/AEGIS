"""
Event contracts for every Pub/Sub topic in AEGIS.

Topics:
  incoming-reports  -> IncomingReport   (ingestion -> orchestrator)
  follow-ups        -> FollowUpEvent    (orchestrator -> followup-worker,
                                          and followup-worker -> itself on reschedule)

Firestore-facing tool outputs (AnalysisResult, SenderReputationResult,
CrossReferenceResult, CaseVerdict, GuardrailResult) are not published to
Pub/Sub but are still typed contracts between agent tools, so they live
here rather than as loose dicts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import CaseStatus, ContentType, ManipulationPattern, ReportChannel, Verdict


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


class IncomingReport(BaseModel):
    """Published by the ingestion service to the `incoming-reports` topic.

    NOTE: `user_id` is a stable HMAC hash of the WhatsApp wa_id, never the
    raw phone number (see shared/guardrails/pii.py::hash_user_id). Raw
    message content MAY be present here because this event is consumed
    exactly once, synchronously, by the orchestrator's guardrail layer
    before anything touches a model or a log line -- it is never persisted
    or logged in this form.

    `wa_id` (raw phone number) rides along for exactly one reason: AEGIS
    has to be able to reply on WhatsApp, and a one-way hash can't be
    reversed into a phone number. This field must NEVER be written to a
    log line, a Firestore doc, or a tool-call argument the reasoning trace
    captures. The orchestrator's only legitimate use of it is to register
    it (KMS-encrypted) in the `user_directory` collection keyed by
    `user_id` -- see agent-orchestrator/contact_directory.py -- after
    which every other code path operates on `user_id` alone.
    """

    report_id: str = Field(default_factory=_new_id)
    user_id: str
    wa_id: str
    channel: ReportChannel = ReportChannel.WHATSAPP
    content_type: ContentType
    text_content: Optional[str] = None
    media_gcs_uri: Optional[str] = None  # gs://... for image/audio/video
    media_mime_type: Optional[str] = None
    wa_message_id: str  # WhatsApp's own message id, for idempotency
    received_at: datetime = Field(default_factory=_now)
    locale_hint: Optional[str] = None


class GuardrailResult(BaseModel):
    """Output of the shared guardrail pipeline. Never carries raw PII --
    only placeholders and flags. This is what gets logged and what gets
    passed onward to the model."""

    sanitized_text: str
    risk_flags: list[str] = Field(default_factory=list)
    redaction_types: list[str] = Field(default_factory=list)  # e.g. ["PHONE", "EMAIL"]
    injection_suspected: bool = False
    injection_markers: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Output of the `analyze_content` agent tool."""

    report_id: str
    manipulation_patterns: list[ManipulationPattern] = Field(default_factory=list)
    claimed_institution: Optional[str] = None
    sender_handles: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)
    phone_numbers_mentioned: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str  # redaction-safe, written for the ops dashboard


class SenderReputationResult(BaseModel):
    """Output of the `check_sender_reputation` agent tool."""

    report_id: str
    entity: str  # the sender handle / domain / phone that was looked up
    known_pattern_ids: list[str] = Field(default_factory=list)
    prior_sightings: int = 0
    reputation_score: float = Field(ge=0.0, le=1.0)  # 0 = clean, 1 = known-bad


class CrossReferenceResult(BaseModel):
    """Output of the `cross_reference_reports` agent tool."""

    report_id: str
    matching_pattern_id: Optional[str] = None
    corroborating_report_count: int = 0
    confidence_boost: float = 0.0  # added to AnalysisResult.confidence


class CaseVerdict(BaseModel):
    """Output of `draft_protective_action` + final decision from
    `escalate_or_close`. This is what gets written to user_reports/{id}
    and shown on the dashboard."""

    report_id: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0)
    status: CaseStatus
    plain_language_explanation: str  # in user's detected language
    report_draft: Optional[str] = None
    family_notification_draft: Optional[str] = None
    next_action: str  # short machine-readable action tag, e.g. "close", "monitor", "ask_user"
    decided_at: datetime = Field(default_factory=_now)


class FollowUpEvent(BaseModel):
    """Published to the `follow-ups` topic to schedule re-engagement on an
    open case."""

    report_id: str
    user_id: str
    reason: str  # e.g. "recheck_sender", "repeat_target_window", "await_user_reply"
    not_before: datetime
    attempt: int = 1
