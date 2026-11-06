# Infrastructure

The service on Azure Container Apps, in Terraform. It is deployed to be measured and then removed, so it runs only for a short, known period.

- `bootstrap/`: run once by hand. Creates the resource group, the storage for Terraform state, and the identity GitHub Actions signs in with. Its own state stays on the machine that ran it.
- This folder: the service. CI applies it through `.github/workflows/deploy.yml`.

The deploy identity is a Contributor on the `fruity` resource group only, and it signs in with a short-lived token, so no key is stored in GitHub.

## Bring it up

Use an Azure free account and do not upgrade it. Its spending limit disables the services when the credit runs out, instead of charging. Bootstrap also sets a USD 5 monthly budget on the `fruity` resource group, which emails at 50% and 100% of it and when the forecast passes it. The budget only warns.

```bash
az login
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var subscription_id=<id> -var state_storage_account=<unique-name> -var budget_email=<email>
terraform -chdir=infra/bootstrap output github_variables
```

Set each value from that output as a repository variable, with `gh variable set NAME --body VALUE --repo AndersHenriksen-dev/fruity`. Then turn deploys on and start one:

```bash
gh variable set DEPLOY_ENABLED --body true --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
```

## Measure it

Raise the request limit first, because the load test would otherwise measure only the limit. The next deploy applies it.

```bash
gh variable set REQUESTS_PER_MINUTE --body 100000 --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
uv run fruity loadtest --host <api_url> --output evals --azure-resource-id <api resource id>
uv run fruity loadtest --host <api_url> --output evals --cold-starts
gh variable delete REQUESTS_PER_MINUTE --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
```

The load test takes about 15 minutes and refuses any host except this service. Cold starts take over an hour, because the service must scale to zero before each one. Results go to `evals/LOAD.md`.

The dashboard and three alerts come with the service: 5xx answers, a slow average response, and memory near the limit. Alerts go to the address in the `ALERT_EMAIL` repository variable, which must be set before the first deploy. The slow answer alert is meant to fire during the load test, which proves it works. If the average stays under its limit of 1 second, lower `slow_answer_ms` for that run.

## Take it down

```bash
gh workflow run deploy.yml --ref main -f action=destroy --repo AndersHenriksen-dev/fruity
gh variable delete DEPLOY_ENABLED --repo AndersHenriksen-dev/fruity
terraform -chdir=infra/bootstrap destroy -var subscription_id=<id> -var state_storage_account=<unique-name> -var budget_email=<email>
```

Run them in this order. The service's state lives in the storage that the last command removes, and deleting `DEPLOY_ENABLED` stops a later merge from bringing the service back.
