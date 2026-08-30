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
    def contact_directory_kms_key(self) -> str:
        return _required("CONTACT_DIRECTORY_KMS_KEY")

    @property
    def global_pattern_salt(self) -> str:
        return _required("GLOBAL_PATTERN_SALT")

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
    def max_follow_up_cycles(self) -> int:
        # After this many "nothing new" cycles, close the case instead of
        # rescheduling another follow-up indefinitely.
        return int(os.environ.get("MAX_FOLLOW_UP_CYCLES", "3"))

    @property
    def batch_size(self) -> int:
        return int(os.environ.get("FOLLOWUP_BATCH_SIZE", "50"))


settings = Settings()
