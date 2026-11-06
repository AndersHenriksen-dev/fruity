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

variable "budget_amount" {
  description = "The monthly spend the account may reach, in its billing currency, which is DKK. 60 DKK stays under USD 10."
  type        = number
  default     = 60
}

variable "deployment_hours" {
  description = "How long after this is applied the service is removed."
  type        = number
  default     = 48
}

variable "budget_email" {
  description = "Where the budget emails go."
  type        = string
}
