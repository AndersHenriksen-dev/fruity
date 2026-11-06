variable "subscription_id" {
  description = "The Azure subscription to use."
  type        = string
}

variable "location" {
  description = "The Azure region for everything."
  type        = string
  default     = "swedencentral"
}

variable "state_storage_account" {
  description = "A name for the state storage account, unique across all of Azure: 3 to 24 lowercase letters and digits."
  type        = string
}

variable "github_repository" {
  description = "The repository whose main branch may deploy."
  type        = string
  default     = "AndersHenriksen-dev/fruity"
}
