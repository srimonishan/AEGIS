# --- incoming-reports: ingestion -> orchestrator -----------------------

resource "google_pubsub_topic" "incoming_reports" {
  name       = "incoming-reports"
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "incoming_reports_dlq" {
  name = "incoming-reports-dlq"
}

# A Pub/Sub topic retains nothing on its own -- without a subscription,
# every message dead-lettered here would be silently dropped the moment
# it's published, with no error and no trace. This pull subscription
# exists purely so those messages are retrievable (for manual triage) and
# so the num_undelivered_messages metric in monitoring.tf has something
# real to alert on. 7-day retention gives a person time to notice the
# alert and go look.
resource "google_pubsub_subscription" "incoming_reports_dlq_review" {
  name                       = "incoming-reports-dlq-review"
  topic                      = google_pubsub_topic.incoming_reports_dlq.name
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false
}

resource "google_pubsub_subscription" "incoming_reports_push" {
  name  = "incoming-reports-orchestrator-push"
  topic = google_pubsub_topic.incoming_reports.name

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.orchestrator.uri}/pubsub/push"
    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
    }
  }

  ack_deadline_seconds = 300 # generous: a full ADK tool-calling turn can take a few seconds

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.incoming_reports_dlq.id
    max_delivery_attempts = 5
  }
}

# --- follow-ups: orchestrator -> (event log; Firestore is the real queue) --

resource "google_pubsub_topic" "follow_ups" {
  name = "follow-ups"
}

# No push subscription needed for follow-ups -- the followup-worker Cloud
# Run Job is woken by Cloud Scheduler and queries Firestore directly (see
# shared/schemas/firestore_models.py::FollowUpDoc for why). This topic
# exists purely as an observability/event-log trail; add a subscription
# here if you later want a second consumer (e.g. a metrics pipeline).

# --- IAM: let Pub/Sub's service agent publish DLQ messages -----------------

data "google_project" "current" {}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.incoming_reports_dlq.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber_grant" {
  subscription = google_pubsub_subscription.incoming_reports_push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
