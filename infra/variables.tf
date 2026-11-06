variable "image_tag" {
  description = "The image tag to deploy: the commit the images were built from."
  type        = string
}

variable "image_repository" {
  description = "Where the images are. They are public, so no registry password is needed."
  type        = string
  default     = "ghcr.io/andershenriksen-dev/fruity"
}

variable "allowed_ip_ranges" {
  description = "Who may reach the apps, in CIDR notation. An empty list would let in everyone, so it is refused."
  type        = list(string)
  sensitive   = true

  validation {
    condition     = length(var.allowed_ip_ranges) > 0
    error_message = "At least one address is needed: with no rules, the apps accept everyone."
  }
}

variable "alert_email" {
  description = "Where alerts go."
  type        = string
}

variable "slow_answer_ms" {
  description = "The average response time that sets off an alert."
  type        = number
  default     = 1000
}

variable "requests_per_minute" {
  description = "How many requests one API replica accepts. A load test raises this while it runs, because the limit would otherwise be all it measures."
  type        = number
  default     = 120
}

variable "log_daily_quota_gb" {
  description = "Stop collecting logs for the day after this much, so noisy logs cannot run up a bill."
  type        = number
  default     = 0.2
}
