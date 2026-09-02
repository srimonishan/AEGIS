import os


def _required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


class Settings:
    @property
    def gcp_project_id(self) -> str:
        return _required("GCP_PROJECT_ID")

    @property
    def gcp_location(self) -> str:
        return os.environ.get("GCP_LOCATION", "us-central1")

    @property
    def gemini_model(self) -> str:
        # Must be a Gemini model id enabled in this project's Vertex AI
        # region. Configurable because exact model ids/availability change
        # faster than this codebase should need a redeploy for.
        return os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

    @property
    def gemini_fallback_models(self) -> list[str]:
        raw = os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash")
        return [model.strip() for model in raw.split(",") if model.strip()]

    @property
    def pubsub_topic_followups(self) -> str:
        return os.environ.get("PUBSUB_TOPIC_FOLLOWUPS", "follow-ups")

    @property
    def pubsub_subscription_incoming_reports(self) -> str:
        return os.environ.get(
            "PUBSUB_SUBSCRIPTION_INCOMING_REPORTS", "incoming-reports-orchestrator-push"
        )

    @property
    def meta_access_token(self) -> str:
        return _required("META_ACCESS_TOKEN")

    @property
    def meta_phone_number_id(self) -> str:
        return _required("META_PHONE_NUMBER_ID")

    @property
    def meta_graph_api_version(self) -> str:
        return os.environ.get("META_GRAPH_API_VERSION", "v25.0")

    @property
    def contact_directory_kms_key(self) -> str:
        # Full resource name: projects/{p}/locations/{l}/keyRings/{r}/cryptoKeys/{k}
        return _required("CONTACT_DIRECTORY_KMS_KEY")

    @property
    def global_pattern_salt(self) -> str:
        # Distinct from AEGIS_USER_ID_PEPPER: this one is intentionally the
        # SAME across all users/services so the same scam domain/phone
        # fingerprints identically no matter who reported it -- that's what
        # makes global_patterns a shared, cross-user signal.
        return _required("GLOBAL_PATTERN_SALT")

    @property
    def verify_pubsub_push_oidc(self) -> bool:
        # Disable only for local/manual testing; Cloud Run deploys must
        # leave this on so /pubsub/push only accepts calls carrying a valid
        # Google-signed OIDC token from the push subscription's service
        # account (see infra/terraform/pubsub.tf).
        return os.environ.get("VERIFY_PUBSUB_PUSH_OIDC", "true").lower() != "false"

    @property
    def pubsub_push_audience(self) -> str:
        return os.environ.get("PUBSUB_PUSH_AUDIENCE", "")


settings = Settings()
