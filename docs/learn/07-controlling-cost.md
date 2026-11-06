# 7. Controlling cost

## The problem

The goal was a hard limit of USD 10. On a Pay-As-You-Go subscription, Azure does not offer one. Microsoft's docs are direct on three points:

- The spending limit exists only on subscriptions with credit, and "Custom spending limits aren't available".
- A budget does not stop anything: "Resources aren't affected, and your consumption isn't stopped".
- "Cost and usage data is typically available within 8-24 hours and budgets are evaluated against these costs every 24 hours."

So a budget can act up to about two days after the spending happened. In a 24-hour deployment, that is too late to be the main protection. Grouping things differently does not help either: a resource group, a management group or a second subscription is still Pay-As-You-Go underneath.

This changes the question from "how do I set a limit?" to "how do I make the bill small even when nobody is watching?"

## How the bill works

| Item | Retail price | Limited by |
|---|---:|---|
| Active vCPU | USD 0.000024 per second | Replica caps |
| Memory | USD 0.000003 per GiB-second | Replica caps |
| Requests | USD 0.40 per million | Nothing in Azure, so the address list |
| Logs | USD 2.30 per GB | Daily quota, and 5 GB free each month |
| Alert rules and state storage | Cents | Small by nature |

The free grant comes first each month: 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests. That is about USD 5.40 of compute.

The ceiling on compute is arithmetic:

```text
2 API replicas x (0.5 vCPU, 1 GiB)  +  1 demo replica x (0.25 vCPU, 0.5 GiB)
= 1.25 vCPU and 2.5 GiB
= 1.25 x 0.000024 + 2.5 x 0.000003  = USD 0.0000375 per second
= USD 0.135 per hour
= USD 3.24 over 24 hours, less than the free grant
```

## The layers

Each layer covers what the one before cannot.

1. **Replica caps** turn an unknown into a known rate. Compute cannot grow, however much traffic arrives. A Terraform test fails if the caps or sizes change.
2. **The timer** limits how long that rate can run. A runbook, which is a script run by Azure Automation, removes the apps 24 hours after bootstrap. It runs inside Azure, so it works with no computer on. The clock is deliberately not moved by later applies.
3. **The address list** closes the one cost the caps leave open. Requests are billed per request, so a flood could cost money with compute held flat. With only your address allowed, strangers get "RBAC: Access Denied". Azure's pricing page does not say whether blocked requests are billed, so this may not remove that cost entirely. Reaching USD 10 that way would still take about 27 million requests in the window.
4. **The budget** is the last resort. At 30 DKK of actual spend, half of the 60 DKK limit, it fires the same runbook. It sits at half because it is late.

## What is left

Nothing here makes a higher bill strictly impossible, and it is better to say that than to imply otherwise. If the timer fails, compute runs on at no more than USD 0.135 an hour, and the free grant has to be used up first, so USD 10 takes about 4.7 days, by which time the budget should have fired. A safety system you have never seen work is a hope, so the kill switch gets run once on purpose before anyone relies on it.

Azure bills in the account's currency, so a budget amount is in that currency too. The 60 here means DKK, about USD 9.

## Why the deployment is temporary

The service runs for a known window, the evidence gets recorded, and it comes down. That costs the live demo link, but gives a bill you can bound in advance. The results stay, and one command can bring it back.

## In this repo

- [infra/bootstrap/spending_limit.tf](../../infra/bootstrap/spending_limit.tf): the budget, the timer and the action group.
- [infra/bootstrap/teardown.ps1](../../infra/bootstrap/teardown.ps1): the kill switch.
- [infra/main.tf](../../infra/main.tf): the caps and the address list.
- [infra/README.md](../../infra/README.md): each limit and what it leaves open.
