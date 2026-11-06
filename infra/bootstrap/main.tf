# Run once by hand, signed in with `az login`, before the first deploy. Everything CI needs and may not create itself:
# a place for Terraform state, and an identity that can only touch the service's resource group.
terraform {
  required_version = ">= 1.17"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  # A new subscription has few of these registered, and the deploy identity has no rights at subscription level to do
  # it later. Naming them here keeps the list to what this project uses.
  resource_provider_registrations = "none"
  resource_providers_to_register = [
    "Microsoft.App",
    "Microsoft.Consumption",
    "Microsoft.ManagedIdentity",
    "Microsoft.OperationalInsights",
    "Microsoft.Storage",
  ]
}

resource "azurerm_resource_group" "service" {
  name     = "fruity"
  location = var.location
}

resource "azurerm_resource_group" "state" {
  name     = "fruity-state"
  location = var.location
}

resource "azurerm_storage_account" "state" {
  name                            = var.state_storage_account
  resource_group_name             = azurerm_resource_group.state.name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}

resource "azurerm_storage_container" "state" {
  name               = "tfstate"
  storage_account_id = azurerm_storage_account.state.id
}

# GitHub Actions signs in with a short-lived token for this repo's main branch, so no key is stored anywhere.
resource "azurerm_user_assigned_identity" "deploy" {
  name                = "fruity-deploy"
  resource_group_name = azurerm_resource_group.state.name
  location            = var.location
}

resource "azurerm_federated_identity_credential" "main_branch" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.state.name
  parent_id           = azurerm_user_assigned_identity.deploy.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repository}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "deploy_service" {
  scope                = azurerm_resource_group.service.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.deploy.principal_id
}

resource "azurerm_role_assignment" "deploy_state" {
  scope                = azurerm_storage_account.state.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.deploy.principal_id
}

# Scoped to this project, because other projects share the subscription and its credit. A budget only sends email:
# it does not stop anything. On a free account the spending limit is what stops charges.
resource "azurerm_consumption_budget_resource_group" "service" {
  name              = "fruity"
  resource_group_id = azurerm_resource_group.service.id
  amount            = var.budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00'Z'", plantimestamp())
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 50
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Forecasted"
    contact_emails = [var.budget_email]
  }

  # Azure requires a start date in the current month. Keep the first one, or every later plan would replace the budget.
  lifecycle {
    ignore_changes = [time_period]
  }
}
