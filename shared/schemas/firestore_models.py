"""
Firestore document contracts.

Collections:
  user_reports/{reportId}         -> UserReportDoc
  global_patterns/{patternId}     -> GlobalPatternDoc   (anonymized, no raw PII ever)
  family_links/{userId}           -> FamilyLinkDoc
  user_history/{userId}           -> UserHistoryDoc
  user_directory/{userId}         -> UserDirectoryDoc     (KMS-encrypted contact)
  follow_ups/{followUpId}         -> FollowUpDoc
  pending_family_links/{code}     -> PendingFamilyLinkDoc
  pending_deletions/{userId}      -> PendingDeletionDoc

Every service that reads/writes Firestore MUST go through
`.model_dump(mode="json")` / `.model_validate()` on these models -- never
hand-build a dict for `doc_ref.set(...)`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from .enums import CaseStatus, FollowUpStatus, ManipulationPattern, PendingLinkStatus, Verdict


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserReportDoc(BaseModel):
    report_id: str
    user_id: str
    status: CaseStatus
    verdict: Optional[Verdict] = None
    confidence: Optional[float] = None
    manipulation_patterns: list[ManipulationPattern] = Field(default_factory=list)
    matched_pattern_id: Optional[str] = None
    plain_language_explanation: Optional[str] = None
    report_draft: Optional[str] = None
    family_notified: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    reasoning_trace: list[dict] = Field(default_factory=list)
    """List of {tool, redacted_input_summary, output_summary, at} -- what the
    dashboard's per-case drill-down renders. Never contains raw PII."""


class GlobalPatternDoc(BaseModel):
    """A de-identified, shared scam signature. This is the network-effect
    layer -- it must never contain a raw phone number, name, or message
    body. Only structural fingerprints."""

    pattern_id: str
    fingerprint: str  # stable hash of normalized entity (domain/number/handle)
    entity_type: str  # "domain" | "phone" | "handle"
    manipulation_patterns: list[ManipulationPattern] = Field(default_factory=list)
    claimed_institution: Optional[str] = None
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)
    report_count: int = 1
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class FamilyLinkDoc(BaseModel):
    """Opt-in mapping from a protected user to a notified family contact.
    Both ids are hashed WhatsApp ids, not raw phone numbers."""

    user_id: str
    family_contact_user_id: str
    display_label: Optional[str] = None  # e.g. "Priya (daughter)" -- user-supplied, opt-in
    created_at: datetime = Field(default_factory=_now)
    active: bool = True


class PendingFamilyLinkDoc(BaseModel):
    """A not-yet-confirmed family-link request, keyed by a short random
    `code`. Created when a user sends `LINK FAMILY <phone>`; only becomes
    a real FamilyLinkDoc once the *target* phone itself replies `CONFIRM
    LINK <code>` -- deliberately a two-sided handshake so nobody can
    subscribe a stranger to receive alerts about them without that
    stranger's own consent, and nobody can silently register themselves
    as another user's family contact. See
    agent-orchestrator/family_link_commands.py.

    Handled entirely by deterministic string-command parsing BEFORE any
    guardrail sanitization or ADK agent turn -- a forwarded scam message
    that happens to contain "LINK FAMILY ..." as adversarial content
    never reaches this code path, because that path only ever sees
    output the agent produces as tool-call arguments, never raw inbound
    text matched against a command grammar.
    """

    code: str
    requester_user_id: str
    target_user_id: str
    status: PendingLinkStatus = PendingLinkStatus.PENDING
    created_at: datetime = Field(default_factory=_now)
    expires_at: datetime
    resolved_at: Optional[datetime] = None


class PendingDeletionDoc(BaseModel):
    """A not-yet-confirmed 'forget me' request, keyed by `user_id`.
    Created by `DELETE MY DATA`, only executed if the SAME user_id
    replies `DELETE MY DATA CONFIRM` within the expiry window -- a
    two-step confirmation for an irreversible action, same reasoning as
    any destructive-action UX. See
    agent-orchestrator/data_deletion_commands.py."""

    user_id: str
    requested_at: datetime = Field(default_factory=_now)
    expires_at: datetime


class UserDirectoryDoc(BaseModel):
    """Maps a hashed user_id back to a KMS-encrypted WhatsApp id, so the
    orchestrator can deliver a reply/notification. This is the ONE place
    in Firestore that (indirectly) holds a phone number, and it is
    ciphertext at rest (Cloud KMS symmetric encrypt) -- see
    agent-orchestrator/contact_directory.py. IAM on this collection should
    be restricted to the orchestrator's service account only; it is
    deliberately not one of the four collections the brief calls out as
    dashboard-visible, and the dashboard must never read it."""

    user_id: str
    encrypted_wa_id: str  # base64 ciphertext from Cloud KMS Encrypt
    updated_at: datetime = Field(default_factory=_now)


class FollowUpDoc(BaseModel):
    """Durable, queryable record backing the `follow-ups` Pub/Sub topic.

    Pub/Sub has no native delayed-delivery -- a message published today
    can't be held back until `not_before` on its own. The orchestrator
    publishes a FollowUpEvent to Pub/Sub (for the event-log/observability
    story) AND writes one of these to Firestore in the same call; the
    followup-worker Cloud Run Job, woken on a Cloud Scheduler cadence,
    queries `status == pending AND not_before <= now` -- that query is
    what actually makes 'runs asynchronously in the background' real
    rather than cosmetic.
    """

    follow_up_id: str
    report_id: str
    user_id: str
    reason: str
    status: FollowUpStatus = FollowUpStatus.PENDING
    not_before: datetime
    created_at: datetime = Field(default_factory=_now)
    processed_at: Optional[datetime] = None
    attempt: int = 1


class UserHistoryDoc(BaseModel):
    """Lightweight per-user memory to speed up repeat-pattern detection."""

    user_id: str
    total_reports: int = 0
    scam_reports: int = 0
    last_report_id: Optional[str] = None
    last_verdict: Optional[Verdict] = None
    last_seen: datetime = Field(default_factory=_now)
    known_pattern_ids: list[str] = Field(default_factory=list)
