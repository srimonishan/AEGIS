# Per-service service accounts -- deliberately NOT a shared "god"
# credential. Each binding below is scoped to the single resource that
# service actually needs, not project-wide roles, so a compromised
# ingestion service (the one directly exposed to the internet) cannot
# read Firestore, call Gemini, or decrypt anything.

resource "google_service_account" "ingestion" {
  account_id   = "aegis-ingestion"
  display_name = "AEGIS ingestion service"
}

resource "google_service_account" "orchestrator" {
  account_id   = "aegis-orchestrator"
  display_name = "AEGIS agent orchestrator"
}

resource "google_service_account" "followup_worker" {
  account_id   = "aegis-followup-worker"
  display_name = "AEGIS follow-up worker (Cloud Run Job)"
}

resource "google_service_account" "pubsub_invoker" {
  account_id   = "aegis-pubsub-invoker"
  display_name = "Identity Pub/Sub uses to push into the orchestrator"
}

resource "google_service_account" "scheduler_invoker" {
  account_id   = "aegis-scheduler-invoker"
  display_name = "Identity Cloud Scheduler uses to run the follow-up worker job"
}

# --- ingestion: publish incoming-reports, write media, nothing else -------

resource "google_pubsub_topic_iam_member" "ingestion_publish" {
  topic  = google_pubsub_topic.incoming_reports.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_storage_bucket_iam_member" "ingestion_media_write" {
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

# --- orchestrator: Firestore, Vertex AI, KMS encrypt+decrypt, publish follow-ups, read media --

resource "google_project_iam_member" "orchestrator_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_pubsub_topic_iam_member" "orchestrator_publish_followups" {
  topic  = google_pubsub_topic.follow_ups.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_kms_crypto_key_iam_member" "orchestrator_kms" {
  crypto_key_id = google_kms_crypto_key.contact_directory.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_storage_bucket_iam_member" "orchestrator_media_read" {
  bucket = google_storage_bucket.media.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.orchestrator.email}"
}

# --- followup-worker: Firestore, KMS DECRYPT ONLY (never registers a new contact) --

resource "google_project_iam_member" "followup_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.followup_worker.email}"
}

resource "google_kms_crypto_key_iam_member" "followup_kms_decrypt" {
  crypto_key_id = google_kms_crypto_key.contact_directory.id
  role          = "roles/cloudkms.cryptoKeyDecrypter"
  member        = "serviceAccount:${google_service_account.followup_worker.email}"
}

# --- Pub/Sub push invoker: can invoke the orchestrator, nothing else -------

resource "google_cloud_run_v2_service_iam_member" "pubsub_can_invoke_orchestrator" {
  name     = google_cloud_run_v2_service.orchestrator.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# The above grant lets pubsub_invoker CALL the orchestrator, but Pub/Sub's
# own service agent still needs permission to actually MINT an OIDC token
# AS pubsub_invoker in the first place -- without this, the push
# subscription silently fails to authenticate on every attempt (the
# resource itself still creates fine; nothing about `terraform apply`
# would tell you this is missing) and the orchestrator never receives a
# single message.
resource "google_service_account_iam_member" "pubsub_agent_can_impersonate_invoker" {
  service_account_id = google_service_account.pubsub_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# --- Cloud Scheduler: can execute the follow-up worker job, nothing else ---

resource "google_cloud_run_v2_job_iam_member" "scheduler_can_run_followup_job" {
  name     = google_cloud_run_v2_job.followup_worker.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# Same reasoning as the Pub/Sub grant above: Cloud Scheduler's own service
# agent needs to be able to mint an OAuth token AS scheduler_invoker, or
# every scheduled execution silently fails to authenticate and the
# follow-up worker never actually runs.
resource "google_service_account_iam_member" "scheduler_agent_can_impersonate_invoker" {
  service_account_id = google_service_account.scheduler_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-cloudscheduler.iam.gserviceaccount.com"
}

# --- ingestion's webhook is public (Meta calls it directly); everything
# else requires authentication. ---

resource "google_cloud_run_v2_service_iam_member" "ingestion_public" {
  name     = google_cloud_run_v2_service.ingestion.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
