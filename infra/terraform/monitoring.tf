# Alerting. None of this existed in the initial build -- a Cloud Run
# service logs its own errors either way, but nothing paged anyone, and
# the DLQ topic in particular could have silently accumulated forever.

resource "google_monitoring_notification_channel" "email" {
  display_name = "AEGIS ops email"
  type         = "email"
  labels = {
    email_address = var.alert_notification_email
  }
  depends_on = [google_project_service.apis]
}

# --- Dead-lettered messages -------------------------------------------

resource "google_monitoring_alert_policy" "dlq_backlog" {
  display_name          = "AEGIS: incoming-reports DLQ has messages"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email.id]

  conditions {
    display_name = "num_undelivered_messages > 0 on the DLQ review subscription"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"pubsub_subscription\"",
        "resource.label.subscription_id = \"${google_pubsub_subscription.incoming_reports_dlq_review.name}\"",
        "metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }

  documentation {
    content   = "A report failed all 5 delivery attempts into the orchestrator and landed in incoming-reports-dlq. Something is structurally broken (bad payload, orchestrator down, permissions) -- inspect with `gcloud pubsub subscriptions pull incoming-reports-dlq-review --auto-ack`."
    mime_type = "text/markdown"
  }
}

# --- Cloud Run error rates ----------------------------------------------

resource "google_monitoring_alert_policy" "orchestrator_5xx" {
  display_name          = "AEGIS: orchestrator 5xx error rate"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email.id]

  conditions {
    display_name = "5xx responses > 5 in 5 min"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "resource.label.service_name = \"${google_cloud_run_v2_service.orchestrator.name}\"",
        "metric.type = \"run.googleapis.com/request_count\"",
        "metric.label.response_code_class = \"5xx\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    content   = "The orchestrator is returning 5xx to Pub/Sub push, which means those incoming-reports messages will retry and eventually dead-letter. Check Cloud Run logs and Vertex AI quota first."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "ingestion_5xx" {
  display_name          = "AEGIS: ingestion 5xx error rate"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email.id]

  conditions {
    display_name = "5xx responses > 5 in 5 min"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_revision\"",
        "resource.label.service_name = \"${google_cloud_run_v2_service.ingestion.name}\"",
        "metric.type = \"run.googleapis.com/request_count\"",
        "metric.label.response_code_class = \"5xx\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}

# --- Follow-up worker job failures --------------------------------------

resource "google_monitoring_alert_policy" "followup_worker_job_failure" {
  display_name          = "AEGIS: follow-up worker job execution failed"
  combiner              = "OR"
  notification_channels = [google_monitoring_notification_channel.email.id]

  conditions {
    display_name = "completed_execution_count{result=failed} > 0"
    condition_threshold {
      filter = join(" AND ", [
        "resource.type = \"cloud_run_job\"",
        "resource.label.job_name = \"${google_cloud_run_v2_job.followup_worker.name}\"",
        "metric.type = \"run.googleapis.com/job/completed_execution_count\"",
        "metric.label.result = \"failed\"",
      ])
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "1800s" # matches the scheduler's 30-min cadence
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    content   = "The scheduled follow-up worker execution failed -- open cases in 'monitoring' status will stop being rechecked until this is fixed. Check the job's Cloud Run execution logs."
    mime_type = "text/markdown"
  }
}

# --- Cost guard rail -----------------------------------------------------

resource "google_billing_budget" "aegis" {
  billing_account = var.billing_account_id
  display_name    = "AEGIS monthly budget"

  budget_filter {
    # The Billing Budgets API wants the numeric project NUMBER here, not
    # the project ID string -- data.google_project.current (declared in
    # pubsub.tf) already resolves that for this same project.
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = var.monthly_budget_usd
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 0.9
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }
}
