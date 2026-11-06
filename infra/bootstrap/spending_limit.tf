# Azure has no spending limit for this kind of subscription, so this is the nearest thing to one. A runbook inside Azure
# removes the apps, on a timer and when the budget is passed. Budgets see costs up to two days late, so the timer is
# what normally ends the deployment, and the budget's trigger is set well below the most that may be spent.
resource "azurerm_automation_account" "teardown" {
  name                = "fruity-teardown"
  resource_group_name = azurerm_resource_group.state.name
  location            = var.location
  sku_name            = "Basic"

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "teardown_service" {
  scope                = azurerm_resource_group.service.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_automation_account.teardown.identity[0].principal_id
}

resource "azurerm_automation_runbook" "teardown" {
  name                    = "remove-service"
  resource_group_name     = azurerm_resource_group.state.name
  location                = var.location
  automation_account_name = azurerm_automation_account.teardown.name
  runbook_type            = "PowerShell72"
  log_progress            = true
  log_verbose             = false
  content                 = file("${path.module}/teardown.ps1")
}

resource "azurerm_automation_schedule" "teardown" {
  name                    = "end-of-deployment"
  resource_group_name     = azurerm_resource_group.state.name
  automation_account_name = azurerm_automation_account.teardown.name
  frequency               = "OneTime"
  timezone                = "Etc/UTC"
  start_time              = timeadd(plantimestamp(), "${var.deployment_hours}h")

  # The clock starts at the first apply. A later plan must not push it back.
  lifecycle {
    ignore_changes = [start_time]
  }
}

resource "azurerm_automation_job_schedule" "teardown" {
  resource_group_name     = azurerm_resource_group.state.name
  automation_account_name = azurerm_automation_account.teardown.name
  schedule_name           = azurerm_automation_schedule.teardown.name
  runbook_name            = azurerm_automation_runbook.teardown.name
}

resource "azurerm_automation_webhook" "teardown" {
  name                    = "budget-passed"
  resource_group_name     = azurerm_resource_group.state.name
  automation_account_name = azurerm_automation_account.teardown.name
  runbook_name            = azurerm_automation_runbook.teardown.name
  enabled                 = true
  expiry_time             = timeadd(plantimestamp(), "2160h")

  lifecycle {
    ignore_changes = [expiry_time]
  }
}

resource "azurerm_monitor_action_group" "teardown" {
  name                = "fruity-teardown"
  resource_group_name = azurerm_resource_group.state.name
  short_name          = "teardown"

  email_receiver {
    name          = "owner"
    email_address = var.budget_email
  }

  automation_runbook_receiver {
    name                    = "remove-service"
    automation_account_id   = azurerm_automation_account.teardown.id
    runbook_name            = azurerm_automation_runbook.teardown.name
    webhook_resource_id     = azurerm_automation_webhook.teardown.id
    is_global_runbook       = false
    service_uri             = azurerm_automation_webhook.teardown.uri
    use_common_alert_schema = true
  }
}

# On the whole subscription, because the limit is on what the account spends. The amount is in the billing currency.
resource "azurerm_consumption_budget_subscription" "limit" {
  name            = "account-limit"
  subscription_id = "/subscriptions/${var.subscription_id}"
  amount          = var.budget_amount
  time_grain      = "Monthly"

  time_period {
    start_date = formatdate("YYYY-MM-01'T'00:00:00'Z'", plantimestamp())
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 25
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 50
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
    contact_groups = [azurerm_monitor_action_group.teardown.id]
  }

  notification {
    operator       = "GreaterThanOrEqualTo"
    threshold      = 100
    threshold_type = "Actual"
    contact_emails = [var.budget_email]
    contact_groups = [azurerm_monitor_action_group.teardown.id]
  }

  # Azure requires a start date in the current month. Keep the first one, or every later plan would replace the budget.
  lifecycle {
    ignore_changes = [time_period]
  }
}
