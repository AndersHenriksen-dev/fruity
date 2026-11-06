# 6. CI and deployment

## What runs when

| When | Job | What it catches |
|---|---|---|
| Every pull request | `ruff`, `mypy`, `pytest` | Style, wrong types, broken behavior |
| Every pull request | Build both images | A Dockerfile that no longer works, or a model whose checksum differs |
| Every pull request | `terraform fmt`, `validate`, `test` | Malformed infrastructure and broken cost limits |
| Every pull request | gitleaks | A key or password in the commits |
| Merge to `main`, if `DEPLOY_ENABLED` is on | Build, push, `terraform apply`, smoke test | A release that does not work |

The hand-in's report claimed mypy ran in CI, but the workflow did not run it. So a useful habit is to read the workflow file, not the description of it.

## Signing in without a key

The usual way to let CI into a cloud account is to store a long-lived key as a secret. That key works from anywhere until someone revokes it, and it is easy to leak. This repo uses **OpenID Connect** (OIDC) instead:

1. When a workflow runs, GitHub can issue a short-lived signed token saying "this is `AndersHenriksen-dev/fruity`, on branch `main`".
2. Azure was told in advance, in `azurerm_federated_identity_credential`, to trust GitHub tokens with exactly that subject.
3. Azure checks the signature and the subject, then gives back an access token for the deploy identity.

So there is nothing to steal from the repository. A pull request from another branch has a different subject and is refused. The `id-token: write` permission is what lets a job ask for the token, and only the jobs that need it have it.

## Least privilege

The deploy identity is a Contributor on the `fruity` resource group only. It cannot see the rest of the subscription, cannot touch the budget or the kill switch, and cannot grant itself more. If the workflow were somehow abused, the damage stops at that group. The same idea shows up elsewhere: the kill switch can change only that group, and the workflow's default permission is `contents: read`.

## The off switch

Most deploy workflows run on every merge. Here that would be a trap. Once the service is removed to stop costs, the next merge of anything, even a typo fix, would rebuild it and restart the bill. So every deploy job checks `vars.DEPLOY_ENABLED == 'true'`. When a deployment is finished, that variable is deleted. The merges into `main` before any deployment existed prove it: both jobs were skipped.

## The smoke test

Tests before a deploy cannot show that the deployed thing works. So after `apply`, CI calls `/health` and sends one tiny image, with retries since a replica may be starting from zero. It checks that 3 answers come back. It sends a 1 by 1 pixel image because this proves the model runs over HTTP. It does not prove the model is right, and evaluation already covers that. The allowed list means the runner's own address has to be added for this step.

## Where things are kept

| Kind | Where | Why |
|---|---|---|
| Code, config, lock files | git | Reviewed, and needed to rebuild |
| Results and decisions | `evals/`, `docs/` | So every claim traces to something |
| Weights | GitHub Release | Too large for git, and pinned by checksum |
| Images | GitHub Container Registry | Public images are free, unlike Azure's own registry |
| Terraform state | Azure storage, or local for bootstrap | Can hold secrets, so never in git |
| IDs that are not secret | Repository variables | Needed by the workflow |
| Your address | Repository secret | Public logs would show a plain variable |

## In this repo

- [.github/workflows/ci.yml](../../.github/workflows/ci.yml): the checks.
- [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml): build, apply, smoke test, and removal.
- [infra/bootstrap/main.tf](../../infra/bootstrap/main.tf): the federated credential and the role assignments.
