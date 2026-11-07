# 5. Infrastructure as code

## Why not click in the portal

Clicking works once. Then nobody can say exactly what exists, review a change before it happens, or build it again. Infrastructure as code describes the wanted result in files, so it goes through git and review like any other change, and `terraform destroy` removes all of it. For a deployment meant to exist briefly, that last part is the point.

## How Terraform thinks

You describe what should exist, not the steps to get there:

- **`terraform plan`** compares your files with what exists and lists the differences.
- **`terraform apply`** makes those changes.
- **State** is Terraform's record of what it created. Without it, Terraform cannot tell its resources from anything else.

State can hold secrets, so it never goes in git. It lives in Azure storage here, which also lets CI and a laptop share it.

Terraform works out the order from references. If the demo page refers to the API's address, the API gets created first. That causes a real problem here: the API's allowed list needs the demo page's outbound addresses, and the demo page needs the API's address, which would be a cycle. It is broken by building the API's address from its name and the environment's domain, so the demo page no longer depends on the API resource. Cycles like this are common, and the fix is usually to find a value that is known without creating the other resource.

## Why there are two Terraform folders

A chicken-and-egg problem: CI needs storage for state and an identity to sign in with, but cannot create those before it can sign in. So:

- **`infra/bootstrap/`** runs once, by hand, signed in as the owner. It creates the resource groups, the state storage, the deploy identity and the spending limit. Its own state stays local.
- **`infra/`** is the service, applied by CI.

This split also limits damage: everyday deploys cannot touch the budget or the kill switch, because the deploy identity has no rights over them.

## Azure Container Apps

| Term | Meaning |
|---|---|
| Resource group | A folder for resources, and the unit for permissions and budgets |
| Container app | One service: an image plus its scale and network settings |
| Replica | One running copy of the container |
| Environment | The shared network and logging around a set of apps |
| Ingress | The front door: it takes HTTPS traffic, checks addresses and forwards requests |
| Revision | A version of an app, created on each change to its template |

**Why this and not a virtual machine or Kubernetes?** A virtual machine costs money all day, even with no visitors. Kubernetes solves problems of a size this project does not have, and a cluster costs money just to exist. Container Apps scales to zero and bills per second, so an idle service uses no compute.

**Scaling.** Ingress sees requests, so the platform can add a replica when each has more than 10 in flight, up to the maximum. After some minutes with no requests, it scales down to zero. The first request after that waits while a replica starts: a **cold start**. It is the price of paying nothing while idle.

**Probes.** The platform calls `/health`. The readiness probe decides whether a replica gets traffic, and the liveness probe decides whether it gets restarted.

## Decoding the Terraform

Most of `main.tf` is direct: `cpu = 0.5` is a limit and `max_replicas = 2` is a ceiling. Three lines deserve a closer look:

- `daily_quota_gb` stops collecting logs for the day after that much, so a logging loop cannot run up a bill.
- `resource_provider_registrations = "none"`: Azure must have each service turned on for a subscription. The deploy identity is not allowed to do that, so bootstrap does it, and this line stops CI from trying.
- `sensitive = true` on `allowed_ip_ranges` keeps your address out of the public workflow logs.

## Testing infrastructure

`terraform validate` checks the code is well formed. `terraform test` goes further, with a mock provider that pretends to be Azure: it needs no account, costs nothing, and checks the logic. Here it checks that the address rules exist, that an empty list is refused, and that the replica caps have not grown. What mocks cannot check is whether Azure accepts the result. Only a real deployment shows that.

## In this repo

- [infra/README.md](../../infra/README.md): bring it up, measure it, take it down.
- [infra/main.tf](../../infra/main.tf): the service.
- [infra/bootstrap/main.tf](../../infra/bootstrap/main.tf): state and the deploy identity.
- [infra/tests/service.tftest.hcl](../../infra/tests/service.tftest.hcl): the tests on mocks.
