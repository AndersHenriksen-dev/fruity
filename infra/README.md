# Infrastructure

The service on Azure Container Apps, in Terraform. It is deployed to be measured and then removed, so it runs only for a short, known period.

- `bootstrap/`: run once by hand. Creates the resource group, the storage for Terraform state, the identity GitHub Actions signs in with, and the spending limit below. Its own state stays on the machine that ran it. The 24 hours start when it is applied.
- This folder: the service. CI applies it through `.github/workflows/deploy.yml`.

The deploy identity is a Contributor on the `fruity` resource group only, and it signs in with a short-lived token, so no key is stored in GitHub.

## What it can cost

Azure has no spending limit for this subscription type, so nothing makes a charge above a set amount strictly impossible. These limits make it very unlikely:

| Limit | What it does | What it leaves open |
|---|---|---|
| Replica caps | At most 2 API replicas at 0.5 vCPU and 1 GiB, and 1 demo replica at 0.25 vCPU and 0.5 GiB. At the retail prices checked when this was written, that is at most about USD 0.135 an hour. | Time, which the timer limits |
| Timer | A runbook inside Azure removes the apps 24 hours after bootstrap. Over 24 hours, the caps above allow about USD 3.25 before the monthly free grant, which is larger than that. | The runbook failing |
| Allowed addresses | Only the listed addresses and the demo page reach the apps. | Requests from elsewhere, if Azure bills blocked requests, which its pricing page does not say |
| Budget | At 30 DKK of actual spend, half the 60 DKK limit, the same runbook removes the apps. It also emails at 25% and 100%. | Azure's cost data arrives 8 to 24 hours late and budgets are checked every 24 hours, so this can act up to about two days after the spend |

The apps cost only while they exist. State storage, logs and alert rules cost cents, and removing bootstrap removes them.

## Bring it up

```bash
az login --tenant <your directory>
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var subscription_id=<id> -var state_storage_account=<unique-name> -var budget_email=<email>
terraform -chdir=infra/bootstrap output github_variables
```

Set each value from that output as a repository variable, with `gh variable set NAME --body VALUE --repo AndersHenriksen-dev/fruity`. Also set `ALERT_EMAIL` the same way. Then store your own address as a secret, so it stays out of the public logs, turn deploys on and start one:

```bash
gh secret set ALLOWED_IP --body <your IP address> --repo AndersHenriksen-dev/fruity
gh variable set DEPLOY_ENABLED --body true --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
```

## Measure it

Raise the request limit first, because the load test would otherwise measure only the limit. The next deploy applies it.

```bash
gh variable set REQUESTS_PER_MINUTE --body 100000 --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
uv run fruity loadtest --host <api_url> --output evals --azure-resource-id <api resource id>
uv run fruity loadtest --host <api_url> --output evals --azure-resource-id <api resource id> --soak
uv run fruity loadtest --host <api_url> --output evals --cold-starts
gh variable delete REQUESTS_PER_MINUTE --repo AndersHenriksen-dev/fruity
gh workflow run deploy.yml --ref main --repo AndersHenriksen-dev/fruity
```

The stages take about 15 minutes, and the steady load 20 hours, on a computer that must stay on with the same address. Cold starts take over an hour, because the service must scale to zero before each one. The load test refuses any host except this service. Results go to `evals/LOAD.md`.

Before relying on the timer, start the runbook once by hand and check that the apps are removed, then deploy again.

The dashboard and three alerts come with the service: 5xx answers, a slow average response, and memory near the limit. Alerts go to the address in `ALERT_EMAIL`. The slow answer alert is meant to fire during the load test, which proves it works. If the average stays under its limit of 1 second, lower `slow_answer_ms` for that run.

## Take it down

```bash
gh workflow run deploy.yml --ref main -f action=destroy --repo AndersHenriksen-dev/fruity
gh variable delete DEPLOY_ENABLED --repo AndersHenriksen-dev/fruity
terraform -chdir=infra/bootstrap destroy -var subscription_id=<id> -var state_storage_account=<unique-name> -var budget_email=<email>
```

Run them in this order. The service's state lives in the storage that the last command removes, and deleting `DEPLOY_ENABLED` stops a later merge from bringing the service back.
