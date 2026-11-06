# Both apps scale to zero when idle, so they use no compute between requests.
# The API's size comes from measuring its image at 0.25, 0.5 and 1 vCPU.
data "azurerm_resource_group" "service" {
  name = "fruity"
}

resource "azurerm_log_analytics_workspace" "logs" {
  name                = "fruity-logs"
  resource_group_name = data.azurerm_resource_group.service.name
  location            = data.azurerm_resource_group.service.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = var.log_daily_quota_gb
}

resource "azurerm_container_app_environment" "service" {
  name                       = "fruity"
  resource_group_name        = data.azurerm_resource_group.service.name
  location                   = data.azurerm_resource_group.service.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id
}

resource "azurerm_container_app" "api" {
  name                         = "fruity-api"
  resource_group_name          = data.azurerm_resource_group.service.name
  container_app_environment_id = azurerm_container_app_environment.service.id
  revision_mode                = "Single"

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 2

    http_scale_rule {
      name                = "requests"
      concurrent_requests = "10"
    }

    container {
      name   = "api"
      image  = "${var.image_repository}/api:${var.image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "FRUITY_REQUESTS_PER_MINUTE"
        value = tostring(var.requests_per_minute)
      }

      readiness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/health"
        port      = 8000
      }
    }
  }
}

resource "azurerm_container_app" "frontend" {
  name                         = "fruity-demo"
  resource_group_name          = data.azurerm_resource_group.service.name
  container_app_environment_id = azurerm_container_app_environment.service.id
  revision_mode                = "Single"

  ingress {
    external_enabled = true
    target_port      = 8501
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "frontend"
      image  = "${var.image_repository}/frontend:${var.image_tag}"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "FRUITY_API_ENDPOINT"
        value = "https://${azurerm_container_app.api.ingress[0].fqdn}/batch/classification"
      }
    }
  }
}
