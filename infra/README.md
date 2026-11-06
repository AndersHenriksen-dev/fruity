# Infrastructure

The service on Azure Container Apps, in Terraform. It is deployed to be measured and then removed, so it runs only for a short, known period.

- `bootstrap/`: run once by hand. Creates the resource group, the storage for Terraform state, and the identity GitHub Actions signs in with. Its own state stays on the machine that ran it.
- This folder: the service. CI applies it through `.github/workflows/deploy.yml`.

The deploy identity is a Contributor on the `fruity` resource group only, and it signs in with a short-lived token, so no key is stored in GitHub.

## Bring it up

Use an Azure free account and do not upgrade it. Its spending limit disables the services when the credit runs out, instead of charging.

```bash
az login
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var subscription_id=<id> -var state_storage_account=<unique-name>
terraform -chdir=infra/bootstrap output github_variables
```

Set each value from that output as a repository variable, with `gh variable set NAME --body VALUE --repo AndersHenriksen-dev/fruity`. Then turn deploys on and start one:

```bash
gh variable set DEPLOY_ENABLED --body true --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
```

## Take it down

```bash
gh workflow run deploy.yml --ref main -f action=destroy --repo AndersHenriksen-dev/fruity
gh variable delete DEPLOY_ENABLED --repo AndersHenriksen-dev/fruity
terraform -chdir=infra/bootstrap destroy -var subscription_id=<id> -var state_storage_account=<unique-name>
```

Run them in this order. The service's state lives in the storage that the last command removes, and deleting `DEPLOY_ENABLED` stops a later merge from bringing the service back.
