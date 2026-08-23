from enum import Enum


class ReportChannel(str, Enum):
    WHATSAPP = "whatsapp"


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class ManipulationPattern(str, Enum):
    URGENCY = "urgency"
    AUTHORITY_IMPERSONATION = "authority_impersonation"
    TOO_GOOD_TO_BE_TRUE = "too_good_to_be_true"
    EMOTIONAL_EXPLOITATION = "emotional_exploitation"
    PAYMENT_REQUEST = "payment_request"
    CREDENTIAL_PHISHING = "credential_phishing"
    OTHER = "other"


class Verdict(str, Enum):
    SCAM = "scam"
    LIKELY_SCAM = "likely_scam"
    UNCERTAIN = "uncertain"
    LIKELY_SAFE = "likely_safe"
    SAFE = "safe"


class FollowUpStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class PendingLinkStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    DECLINED = "declined"


class CaseStatus(str, Enum):
    OPEN = "open"
    AWAITING_USER = "awaiting_user"
    MONITORING = "monitoring"
    ESCALATED = "escalated"
    CLOSED = "closed"
