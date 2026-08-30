import os


def _required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


class Settings:
    """Loaded lazily (at first access) rather than at import time, so unit
    tests can exercise pure logic (signature verification, payload parsing)
    without every required secret being set."""

    @property
    def gcp_project_id(self) -> str:
        return _required("GCP_PROJECT_ID")

    @property
    def pubsub_topic_incoming_reports(self) -> str:
        return os.environ.get("PUBSUB_TOPIC_INCOMING_REPORTS", "incoming-reports")

    @property
    def media_gcs_bucket(self) -> str:
        return _required("MEDIA_GCS_BUCKET")

    @property
    def meta_app_secret(self) -> str:
        return _required("META_APP_SECRET")

    @property
    def meta_verify_token(self) -> str:
        return _required("META_VERIFY_TOKEN")

    @property
    def meta_access_token(self) -> str:
        return _required("META_ACCESS_TOKEN")

    @property
    def meta_graph_api_version(self) -> str:
        return os.environ.get("META_GRAPH_API_VERSION", "v25.0")


settings = Settings()
