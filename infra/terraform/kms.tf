resource "google_kms_key_ring" "aegis" {
  name       = "aegis-keyring"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "contact_directory" {
  name     = "aegis-contact-directory"
  key_ring = google_kms_key_ring.aegis.id
  purpose  = "ENCRYPT_DECRYPT"

  # Never destroy this key -- doing so permanently un-decryptable-izes
  # every phone number in user_directory, silently breaking AEGIS's
  # ability to reply to anyone.
  lifecycle {
    prevent_destroy = true
  }
}
