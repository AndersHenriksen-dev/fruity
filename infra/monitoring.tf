# Alerts email the address below. Metric names are from Azure's reference for Microsoft.App/containerapps.
locals {
  metric_namespace = "Microsoft.App/containerapps"

  dashboard_charts = [
    { title = "Requests", metric = "Requests", aggregation = 1 },
    { title = "Average response time (ms)", metric = "ResponseTime", aggregation = 4 },
    { title = "Replicas", metric = "Replicas", aggregation = 3 },
    { title = "Memory used (% of limit)", metric = "MemoryPercentage", aggregation = 3 },
  ]
}

resource "azurerm_monitor_action_group" "email" {
  name                = "fruity-email"
  resource_group_name = data.azurerm_resource_group.service.name
  short_name          = "fruity"

  email_receiver {
    name          = "owner"
    email_address = var.alert_email
  }
}

resource "azurerm_monitor_metric_alert" "server_errors" {
  name                = "fruity-api-server-errors"
  resource_group_name = data.azurerm_resource_group.service.name
  scopes              = [azurerm_container_app.api.id]
  description         = "The API answered with a 5xx status."
  severity            = 1
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = local.metric_namespace
    metric_name      = "Requests"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0

    dimension {
      name     = "statusCodeCategory"
      operator = "Include"
      values   = ["5xx"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

resource "azurerm_monitor_metric_alert" "slow_answers" {
  name                = "fruity-api-slow-answers"
  resource_group_name = data.azurerm_resource_group.service.name
  scopes              = [azurerm_container_app.api.id]
  description         = "The API's average response time is over the limit."
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = local.metric_namespace
    metric_name      = "ResponseTime"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = var.slow_answer_ms
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

resource "azurerm_monitor_metric_alert" "high_memory" {
  name                = "fruity-api-high-memory"
  resource_group_name = data.azurerm_resource_group.service.name
  scopes              = [azurerm_container_app.api.id]
  description         = "A replica of the API is close to its memory limit, where it would be restarted."
  severity            = 2
  frequency           = "PT1M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = local.metric_namespace
    metric_name      = "MemoryPercentage"
    aggregation      = "Maximum"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }
}

resource "azurerm_portal_dashboard" "service" {
  name                = "fruity"
  resource_group_name = data.azurerm_resource_group.service.name
  location            = data.azurerm_resource_group.service.location

  dashboard_properties = jsonencode({
    lenses = {
      "0" = {
        order = 0
        parts = {
          for index, chart in local.dashboard_charts : tostring(index) => {
            position = { x = (index % 2) * 6, y = floor(index / 2) * 4, colSpan = 6, rowSpan = 4 }
            metadata = {
              type = "Extension/HubsExtension/PartType/MonitorChartPart"
              inputs = [
                {
                  name = "options"
                  value = {
                    chart = {
                      title         = chart.title
                      titleKind     = 2
                      visualization = { chartType = 2 }
                      metrics = [
                        {
                          resourceMetadata = { id = azurerm_container_app.api.id }
                          name             = chart.metric
                          aggregationType  = chart.aggregation
                          namespace        = lower(local.metric_namespace)
                        },
                      ]
                    }
                  }
                },
                { name = "sharedTimeRange", isOptional = true },
              ]
            }
          }
        }
      }
    }
    metadata = {
      model = {
        timeRange = {
          type  = "MsPortalFx.Composition.Configuration.ValueTypes.TimeRange"
          value = { relative = { duration = 24, timeUnit = 1 } }
        }
      }
    }
  })
}
