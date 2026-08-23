# Secret Manager, not plain Cloud Run env vars.
#
# Terraform creates the secret *containers* and the IAM bindings that let
# each service read exactly the secrets it needs -- nothing more. The
# secret *values* are deliberately NOT set here via a
# google_secret_manager_secret_version resource, because that would put
# the plaintext into Terraform state permanently. Instead, after the
# first `terraform apply`, add the initial version out-of-band:
#
#   echo -n "$META_APP_SECRET"       | gcloud secrets versions add aegis-meta-app-secret       --data-file=-
#   echo -n "$META_VERIFY_TOKEN"     | gcloud secrets versions add aegis-meta-verify-token      --data-file=-
#   echo -n "$META_ACCESS_TOKEN"     | gcloud secrets versions add aegis-meta-access-token      --data-file=-
#   echo -n "$AEGIS_USER_ID_PEPPER"  | gcloud secrets versions add aegis-user-id-pepper          --data-file=-
#   echo -n "$GLOBAL_PATTERN_SALT"   | gcloud secrets versions add aegis-global-pattern-salt     --data-file=-
#
# Cloud Run references `version = "latest"`, so rotating a secret is just
# `gcloud secrets versions add ... ` followed by redeploying (or
# force-restarting) the affected service to pick it up -- no Terraform
# apply, no plaintext ever touches state or a .tf file.

locals {
  secret_ids = {
    meta_app_secret      = "aegis-meta-app-secret"
    meta_verify_token    = "aegis-meta-verify-token"
    meta_access_token    = "aegis-meta-access-token"
    aegis_user_id_pepper = "aegis-user-id-pepper"
    global_pattern_salt  = "aegis-global-pattern-salt"
  }
}

resource "google_secret_manager_secret" "this" {
  for_each  = local.secret_ids
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# Least-privilege reads: ingestion needs the Meta webhook secrets + the
# pepper (to hash wa_id); the orchestrator needs the access token + the
# global salt; the follow-up worker needs the access token + global salt
# too (it sends proactive WhatsApp messages and fingerprints entities).
# Neither of them gets a secret it doesn't use.

resource "google_secret_manager_secret_iam_member" "ingestion_reads" {
  for_each  = toset(["meta_app_secret", "meta_verify_token", "meta_access_token", "aegis_user_id_pepper"])
  secret_id = google_secret_manager_secret.this[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_secret_manager_secret_iam_member" "orchestrator_reads" {
  # aegis_user_id_pepper is needed here too: family_link_commands.py hashes
  # a phone number the requester typed via the same hash_user_id() function
  # ingestion uses, and it MUST use the identical pepper or the resulting
  # user_id won't match the one ingestion would have produced for that
  # same phone number.
  for_each  = toset(["meta_access_token", "global_pattern_salt", "aegis_user_id_pepper"])
  secret_id = google_secret_manager_secret.this[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_secret_manager_secret_iam_member" "followup_worker_reads" {
  for_each  = toset(["meta_access_token", "global_pattern_salt"])
  secret_id = google_secret_manager_secret.this[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.followup_worker.email}"
}
