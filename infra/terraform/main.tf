terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Required when applying with user credentials (gcloud auth
  # application-default login) rather than a service account key: some
  # APIs (billingbudgets.googleapis.com in particular) reject
  # user-credential requests that don't carry an explicit quota project
  # header. Without this, `google_billing_budget` fails with "quota
  # project, which is not set by default" even though `gcloud auth
  # application-default set-quota-project` was already run -- that only
  # updates the local ADC file; it doesn't make the provider attach the
  # header to its API calls.
  user_project_override = true
  billing_project        = var.project_id
}

locals {
  services = [
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "cloudkms.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
    "billingbudgets.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
