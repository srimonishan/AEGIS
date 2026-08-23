resource "google_firestore_database" "aegis" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

# Composite index the follow-up worker's due-follow-ups query needs
# (equality on status + range on not_before).
resource "google_firestore_index" "follow_ups_due" {
  project    = var.project_id
  database   = google_firestore_database.aegis.name
  collection = "follow_ups"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "not_before"
    order      = "ASCENDING"
  }
}

resource "google_storage_bucket" "media" {
  name                        = var.media_gcs_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition {
      age = 90 # forwarded scam media doesn't need to live forever
    }
    action {
      type = "Delete"
    }
  }
}
