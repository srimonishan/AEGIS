from __future__ import annotations

import uuid

from google.cloud import pubsub_v1

from schemas.events import FollowUpEvent
from schemas.firestore_models import FollowUpDoc

import firestore_client
from config import settings

_publisher: pubsub_v1.PublisherClient | None = None


def _client() -> pubsub_v1.PublisherClient:
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def publish_followup(event: FollowUpEvent) -> str:
    """Publishes the event to Pub/Sub (event-log/observability) AND writes
    a durable FollowUpDoc to Firestore (the actual scheduling mechanism --
    see FollowUpDoc's docstring for why Pub/Sub alone can't do this)."""
    follow_up_id = uuid.uuid4().hex
    doc = FollowUpDoc(
        follow_up_id=follow_up_id,
        report_id=event.report_id,
        user_id=event.user_id,
        reason=event.reason,
        not_before=event.not_before,
        attempt=event.attempt,
    )
    firestore_client.db().collection("follow_ups").document(follow_up_id).set(
        doc.model_dump(mode="python")
    )

    topic_path = _client().topic_path(settings.gcp_project_id, settings.pubsub_topic_followups)
    payload = event.model_dump_json().encode("utf-8")
    future = _client().publish(
        topic_path, payload, report_id=event.report_id, follow_up_id=follow_up_id
    )
    return future.result(timeout=30)
