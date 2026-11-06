terraform {
  required_version = ">= 1.17"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }

  # The storage account comes from infra/bootstrap and is passed in at `terraform init`.
  backend "azurerm" {
    resource_group_name = "fruity-state"
    container_name      = "tfstate"
    key                 = "fruity.tfstate"
    use_oidc            = true
    use_azuread_auth    = true
  }
}

provider "azurerm" {
  features {}
  use_oidc = true
  # The deploy identity has no rights at subscription level. Bootstrap registers what the service needs.
  resource_provider_registrations = "none"
}
