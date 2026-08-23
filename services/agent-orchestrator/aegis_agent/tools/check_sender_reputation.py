from __future__ import annotations

from google.adk.tools import ToolContext

import firestore_client
from schemas.events import SenderReputationResult


def check_sender_reputation(entity: str, entity_type: str, tool_context: ToolContext) -> dict:
    """Look up an extracted entity against AEGIS's shared threat database.

    Call this once per distinct URL/domain, phone number, or handle that
    analyze_content extracted. This is a real lookup against reports from
    ALL AEGIS users (anonymized) -- a hit here is strong signal
    independent of your own read of the message content.

    Args:
        entity: The raw domain/URL, phone number, or handle to check
            (e.g. "http://fake-bank.example/login" or "+1-800-555-0199").
        entity_type: One of "domain", "phone", "handle".

    Returns:
        prior_sightings (how many times this exact entity has been seen
        across all users) and reputation_score (0.0 clean - 1.0 known-bad).
    """
    pattern = firestore_client.lookup_pattern_by_entity(entity)

    checked = tool_context.state.setdefault("checked_entities", [])
    checked.append({"entity": entity, "entity_type": entity_type})

    if pattern is None:
        result = SenderReputationResult(
            report_id=tool_context.state["report_id"],
            entity=entity,
            known_pattern_ids=[],
            prior_sightings=0,
            reputation_score=0.0,
        )
    else:
        result = SenderReputationResult(
            report_id=tool_context.state["report_id"],
            entity=entity,
            known_pattern_ids=[pattern.pattern_id],
            prior_sightings=pattern.report_count,
            reputation_score=pattern.confidence,
        )

    tool_context.state.setdefault("reputation_results", []).append(result.model_dump(mode="json"))
    return {
        "prior_sightings": result.prior_sightings,
        "reputation_score": result.reputation_score,
    }
