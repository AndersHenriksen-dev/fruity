variable "image_tag" {
  description = "The image tag to deploy: the commit the images were built from."
  type        = string
}

variable "image_repository" {
  description = "Where the images are. They are public, so no registry password is needed."
  type        = string
  default     = "ghcr.io/andershenriksen-dev/fruity"
}

variable "log_daily_quota_gb" {
  description = "Stop collecting logs for the day after this much, so noisy logs cannot use up the credit."
  type        = number
  default     = 0.2
}
