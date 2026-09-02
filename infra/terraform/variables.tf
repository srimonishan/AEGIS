variable "project_id" {
  description = "GCP project ID to deploy AEGIS into."
  type        = string
}

variable "region" {
  description = "Cloud Run / Cloud Scheduler region."
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore multi-region or region (e.g. nam5, us-central1)."
  type        = string
  default     = "nam5"
}

variable "gemini_model" {
  description = "Gemini model id to use via Vertex AI (must be enabled in this project/region)."
  type        = string
  default     = "gemini-3.5-flash"
}

variable "gemini_fallback_models" {
  description = "Comma-separated fallback Gemini model ids used when the primary model is unavailable or quota-limited."
  type        = string
  default     = "gemini-2.5-flash"
}

# NOTE: the five secret values (meta_app_secret, meta_verify_token,
# meta_access_token, aegis_user_id_pepper, global_pattern_salt) are
# deliberately NOT Terraform variables. Terraform creates the Secret
# Manager *containers* for them (see secrets.tf) and the IAM bindings
# that let each service read them -- the actual values are added
# out-of-band via `gcloud secrets versions add`, documented in
# secrets.tf's header comment, so no plaintext secret ever gets written
# into a .tfvars file or Terraform state.

variable "meta_phone_number_id" {
  description = "Meta WhatsApp phone_number_id to send messages from."
  type        = string
}

variable "meta_graph_api_version" {
  description = "Versioned Meta Graph API path used for WhatsApp Cloud API calls."
  type        = string
  default     = "v25.0"
}

variable "media_gcs_bucket_name" {
  description = "GCS bucket name for resolved WhatsApp media (must be globally unique)."
  type        = string
}

variable "alert_notification_email" {
  description = "Email address to receive Cloud Monitoring alerts (DLQ backlog, error rates, scheduler failures) and the billing budget alert."
  type        = string
}

variable "billing_account_id" {
  description = "Billing account ID this project is linked to (for the budget alert). Find it with `gcloud billing accounts list`."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly budget threshold in USD that triggers the billing alert."
  type        = number
  default     = 50
}
