# NOTE: image URLs assume you've already built + pushed the three service
# images to Artifact Registry (see infra/README.md for the exact `gcloud
# builds submit` / `docker push` commands). Terraform provisions
# infrastructure; it does not build your application images.

variable "image_ingestion" {
  type = string
}
variable "image_orchestrator" {
  type = string
}
variable "image_followup_worker" {
  type = string
}

resource "google_cloud_run_v2_service" "ingestion" {
  name     = "aegis-ingestion"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # must be reachable by Meta's webhook caller

  template {
    service_account = google_service_account.ingestion.email

    # Blunt but real cost/abuse cap: even if the webhook is hammered,
    # this bounds how many container instances (and how much billing)
    # that can cause before you notice. Cloud Armor + an external HTTPS
    # LB is the proper rate-limiting fix (see README's production-hardening
    # notes) -- this is the floor, not the whole answer.
    scaling {
      max_instance_count = 20
    }

    containers {
      image = var.image_ingestion
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_TOPIC_INCOMING_REPORTS"
        value = google_pubsub_topic.incoming_reports.name
      }
      env {
        name  = "MEDIA_GCS_BUCKET"
        value = google_storage_bucket.media.name
      }
      env {
        name = "META_APP_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["meta_app_secret"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "META_VERIFY_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["meta_verify_token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "META_ACCESS_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["meta_access_token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "META_GRAPH_API_VERSION"
        value = var.meta_graph_api_version
      }
      env {
        name = "AEGIS_USER_ID_PEPPER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["aegis_user_id_pepper"].secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.ingestion_reads,
  ]
}

resource "google_cloud_run_v2_service" "orchestrator" {
  name     = "aegis-orchestrator"
  location = var.region
  # Pub/Sub push requests originate from Google's own infrastructure, not
  # your VPC, so they need the default (all) ingress path -- the real
  # access control is IAM (only pubsub_invoker may call this service; see
  # iam.tf) plus the app-level OIDC check in pubsub_auth.py, not network
  # ingress restriction.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.orchestrator.email
    timeout         = "300s" # a full ADK tool-calling turn can take a while

    # Lower ceiling than ingestion on purpose: every instance here can
    # make Vertex AI calls, which is where a runaway cost curve would
    # actually come from. Pair with a Vertex AI quota and the billing
    # budget alert below.
    scaling {
      max_instance_count = 10
    }

    containers {
      image = var.image_orchestrator
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "GEMINI_FALLBACK_MODELS"
        value = var.gemini_fallback_models
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "PUBSUB_TOPIC_FOLLOWUPS"
        value = google_pubsub_topic.follow_ups.name
      }
      env {
        name = "META_ACCESS_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["meta_access_token"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "META_PHONE_NUMBER_ID"
        value = var.meta_phone_number_id
      }
      env {
        name  = "META_GRAPH_API_VERSION"
        value = var.meta_graph_api_version
      }
      env {
        name = "GLOBAL_PATTERN_SALT"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["global_pattern_salt"].secret_id
            version = "latest"
          }
        }
      }
      env {
        # Needed here too: family_link_commands.py calls hash_user_id() on
        # a phone number the requester typed, which MUST use the same
        # pepper ingestion uses or the resulting user_id won't match.
        name = "AEGIS_USER_ID_PEPPER"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.this["aegis_user_id_pepper"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "CONTACT_DIRECTORY_KMS_KEY"
        value = google_kms_crypto_key.contact_directory.id
      }
      env {
        name  = "PUBSUB_PUSH_AUDIENCE"
        value = "" # filled in after first apply once the service URL is known; see infra/README.md
      }
    }
  }
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.orchestrator_reads,
  ]
}

resource "google_cloud_run_v2_job" "followup_worker" {
  name     = "aegis-followup-worker"
  location = var.region

  template {
    template {
      service_account = google_service_account.followup_worker.email
      max_retries     = 1
      timeout         = "540s"
      containers {
        image = var.image_followup_worker
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name = "GLOBAL_PATTERN_SALT"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this["global_pattern_salt"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "CONTACT_DIRECTORY_KMS_KEY"
          value = google_kms_crypto_key.contact_directory.id
        }
        env {
          name = "META_ACCESS_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.this["meta_access_token"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "META_PHONE_NUMBER_ID"
          value = var.meta_phone_number_id
        }
        env {
          name  = "META_GRAPH_API_VERSION"
          value = var.meta_graph_api_version
        }
      }
    }
  }
  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.followup_worker_reads,
  ]
}

resource "google_cloud_scheduler_job" "followup_worker_trigger" {
  name      = "aegis-followup-worker-trigger"
  region    = var.region
  schedule  = "*/30 * * * *" # every 30 minutes -- tune for your demo window
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.followup_worker.name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler_invoker.email
    }
  }
  depends_on = [google_project_service.apis]
}

output "ingestion_url" {
  value = google_cloud_run_v2_service.ingestion.uri
}

output "orchestrator_url" {
  value = google_cloud_run_v2_service.orchestrator.uri
}
