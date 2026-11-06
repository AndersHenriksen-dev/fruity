# Runs with a mock provider, so it needs no account and creates nothing.
mock_provider "azurerm" {
  mock_resource "azurerm_container_app" {
    defaults = {
      id                    = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.App/containerApps/app"
      outbound_ip_addresses = ["203.0.113.10"]
    }
  }
  mock_resource "azurerm_container_app_environment" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.App/managedEnvironments/env"
    }
  }
  mock_resource "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.OperationalInsights/workspaces/logs"
    }
  }
  mock_resource "azurerm_monitor_action_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Insights/actionGroups/email"
    }
  }
  mock_resource "azurerm_monitor_metric_alert" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/fruity/providers/Microsoft.Insights/metricAlerts/alert"
    }
  }
}

variables {
  image_tag         = "test"
  alert_email       = "owner@example.com"
  allowed_ip_ranges = ["198.51.100.7/32"]
}

run "only_the_allowed_addresses_reach_the_apps" {
  command = apply

  assert {
    condition     = length(azurerm_container_app.frontend.ingress[0].ip_security_restriction) == 1
    error_message = "The demo page must accept only the allowed addresses."
  }

  assert {
    condition     = length(azurerm_container_app.api.ingress[0].ip_security_restriction) == 2
    error_message = "The API must accept the allowed addresses and the demo page."
  }
}

run "compute_cannot_grow_past_the_ceiling_in_the_readme" {
  command = apply

  assert {
    condition     = azurerm_container_app.api.template[0].max_replicas == 2 && azurerm_container_app.frontend.template[0].max_replicas == 1
    error_message = "More replicas raise the most this can cost, so update infra/README.md."
  }

  assert {
    condition     = azurerm_container_app.api.template[0].container[0].cpu == 0.5 && azurerm_container_app.frontend.template[0].container[0].cpu == 0.25
    error_message = "More CPU raises the most this can cost, so update infra/README.md."
  }
}

run "an_empty_list_cannot_open_the_apps_to_everyone" {
  command = plan

  variables {
    allowed_ip_ranges = []
  }

  expect_failures = [var.allowed_ip_ranges]
}
