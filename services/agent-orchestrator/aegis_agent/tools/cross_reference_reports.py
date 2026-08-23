from __future__ import annotations

from google.adk.tools import ToolContext

import firestore_client
from schemas.events import CrossReferenceResult


def cross_reference_reports(entity: str, tool_context: ToolContext) -> dict:
    """Check how many OTHER AEGIS users have reported this same entity
    recently. Corroboration from independent reports is one of the
    strongest signals available -- if several unrelated users reported the
    same phone number or domain in the last 30 days, weight that heavily
    even if your own content analysis alone was uncertain.

    Args:
        entity: The same domain/URL, phone number, or handle you passed to
            check_sender_reputation.

    Returns:
        corroborating_report_count and a suggested confidence_boost
        (0.0-0.3) you should add to your own analysis confidence.
    """
    count = firestore_client.count_corroborating_reports(entity)
    pattern = firestore_client.lookup_pattern_by_entity(entity)
    boost = min(0.3, count * 0.05) if count > 0 else 0.0

    result = CrossReferenceResult(
        report_id=tool_context.state["report_id"],
        matching_pattern_id=pattern.pattern_id if pattern else None,
        corroborating_report_count=count,
        confidence_boost=boost,
    )
    tool_context.state["cross_reference"] = result.model_dump(mode="json")

    return {
        "corroborating_report_count": result.corroborating_report_count,
        "confidence_boost": result.confidence_boost,
    }
