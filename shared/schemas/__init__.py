"""
AEGIS shared data contracts.

Every payload that crosses a Pub/Sub topic or a Firestore write MUST be
constructed through one of these typed models — never an ad hoc dict.
Import this package the same way from every service (it is copied into
each service's Docker build context; see services/*/Dockerfile).
"""

from .enums import (
    CaseStatus,
    ContentType,
    FollowUpStatus,
    ManipulationPattern,
    PendingLinkStatus,
    ReportChannel,
    Verdict,
)
from .events import (
    AnalysisResult,
    CaseVerdict,
    CrossReferenceResult,
    FollowUpEvent,
    GuardrailResult,
    IncomingReport,
    SenderReputationResult,
)
from .firestore_models import (
    FamilyLinkDoc,
    FollowUpDoc,
    GlobalPatternDoc,
    PendingDeletionDoc,
    PendingFamilyLinkDoc,
    UserDirectoryDoc,
    UserHistoryDoc,
    UserReportDoc,
)

__all__ = [
    "CaseStatus",
    "ContentType",
    "FollowUpStatus",
    "ManipulationPattern",
    "PendingLinkStatus",
    "ReportChannel",
    "Verdict",
    "AnalysisResult",
    "CaseVerdict",
    "CrossReferenceResult",
    "FollowUpEvent",
    "GuardrailResult",
    "IncomingReport",
    "SenderReputationResult",
    "FamilyLinkDoc",
    "FollowUpDoc",
    "GlobalPatternDoc",
    "PendingDeletionDoc",
    "PendingFamilyLinkDoc",
    "UserDirectoryDoc",
    "UserHistoryDoc",
    "UserReportDoc",
]
