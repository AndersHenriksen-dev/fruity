output "github_variables" {
  description = "The repository variables the deploy workflow reads. None of these is a secret."
  value = {
    AZURE_CLIENT_ID       = azurerm_user_assigned_identity.deploy.client_id
    AZURE_TENANT_ID       = azurerm_user_assigned_identity.deploy.tenant_id
    AZURE_SUBSCRIPTION_ID = var.subscription_id
    STATE_STORAGE_ACCOUNT = azurerm_storage_account.state.name
  }
}
