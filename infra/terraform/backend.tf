# Remote state, not a local .tfstate file. Terraform backend config
# can't reference variables or interpolation, so the bucket name is
# literal here -- edit it to match whatever you create in the bootstrap
# step below, then re-run `terraform init` (it will offer to migrate any
# existing local state into the bucket).
#
# Bootstrap (once, before the first `terraform init` in this directory):
#
#   PROJECT_ID="your-gcp-project-id"
#   BUCKET="${PROJECT_ID}-aegis-tfstate"
#   gsutil mb -l us-central1 -b on "gs://${BUCKET}"
#   gsutil versioning set on "gs://${BUCKET}"
#   # Lock down who can read state (it can contain secret RESOURCE NAMES,
#   # though not secret VALUES since those are never Terraform-managed --
#   # see secrets.tf):
#   gsutil iam ch -d allUsers "gs://${BUCKET}" 2>/dev/null || true
#
# Then set `bucket` below to that name.

terraform {
  backend "gcs" {
    bucket = "aegis-scamguard-69313-tfstate"
    prefix = "aegis"
  }
}
