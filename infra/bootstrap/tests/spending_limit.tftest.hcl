# Runs with a mock provider, so it needs no account and creates nothing.
mock_provider "azurerm" {
  mock_resource "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity"
    }
  }
  mock_resource "azurerm_storage_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Storage/storageAccounts/state"
    }
  }
  mock_resource "azurerm_user_assigned_identity" {
    defaults = {
      id           = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/deploy"
      principal_id = "00000000-0000-0000-0000-000000000001"
      client_id    = "00000000-0000-0000-0000-000000000002"
      tenant_id    = "00000000-0000-0000-0000-000000000003"
    }
  }
  mock_resource "azurerm_automation_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Automation/automationAccounts/teardown"
    }
  }
  mock_resource "azurerm_automation_webhook" {
    defaults = {
      id  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Automation/automationAccounts/teardown/webHooks/budget"
      uri = "https://example.com/webhook"
    }
  }
  mock_resource "azurerm_monitor_action_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Insights/actionGroups/teardown"
    }
  }
}

variables {
  subscription_id       = "00000000-0000-0000-0000-000000000000"
  state_storage_account = "fruitystate"
  budget_email          = "owner@example.com"
}

run "the_budget_triggers_the_teardown_at_half_the_limit" {
  command = apply

  assert {
    condition     = azurerm_consumption_budget_subscription.limit.amount == 60
    error_message = "The limit changed."
  }

  assert {
    condition = anytrue([
      for notification in azurerm_consumption_budget_subscription.limit.notification :
      notification.threshold == 50 && contains(notification.contact_groups, azurerm_monitor_action_group.teardown.id)
    ])
    error_message = "Passing half the budget must remove the service."
  }
}

run "the_timer_runs_the_teardown_once" {
  command = apply

  assert {
    condition     = azurerm_automation_schedule.teardown.frequency == "OneTime"
    error_message = "The timer must run once."
  }

  assert {
    condition     = var.deployment_hours == 24
    error_message = "A longer deployment raises the most this can cost, so update infra/README.md."
  }

  assert {
    condition     = azurerm_automation_job_schedule.teardown.runbook_name == azurerm_automation_runbook.teardown.name
    error_message = "The timer must start the teardown."
  }
}
