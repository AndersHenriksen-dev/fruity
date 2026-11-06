output "api_url" {
  description = "The API."
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "demo_url" {
  description = "The demo page."
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}
