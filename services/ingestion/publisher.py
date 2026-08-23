from __future__ import annotations

import json

from google.cloud import pubsub_v1

from schemas.events import IncomingReport

from config import settings

_publisher: pubsub_v1.PublisherClient | None = None


def _client() -> pubsub_v1.PublisherClient:
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
    return _publisher


def publish_incoming_report(report: IncomingReport) -> str:
    topic_path = _client().topic_path(
        settings.gcp_project_id, settings.pubsub_topic_incoming_reports
    )
    payload = report.model_dump_json().encode("utf-8")
    future = _client().publish(
        topic_path,
        payload,
        wa_message_id=report.wa_message_id,
        content_type=report.content_type.value,
    )
    return future.result(timeout=30)
