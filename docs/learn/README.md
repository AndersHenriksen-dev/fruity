# Learning guide

A study guide to the ideas behind this repository and to what the code actually does. Read the files in order once; afterwards each one works as a reference. Every file ends with where to find its ideas in the code.

| # | File | What it covers |
|---|---|---|
| 1 | [The system](01-the-system.md) | The parts, what one request does from start to finish, and why each part exists |
| 2 | [Choosing a model](02-choosing-a-model.md) | Splitting data, fixing a rule before seeing results, the sweep, and why the test set is read once |
| 3 | [ONNX and serving](03-onnx-and-serving.md) | Why the service has no PyTorch, what quantization does, and how the same numbers were proven |
| 4 | [Containers](04-containers.md) | Images, layers, multi-stage builds, resource limits, and the choices in these Dockerfiles |
| 5 | [Infrastructure as code](05-infrastructure-as-code.md) | Terraform, state, Azure Container Apps, scaling to zero, and the bootstrap |
| 6 | [CI and deployment](06-ci-and-deployment.md) | What runs when, signing in without a key, least privilege, and the off switch |
| 7 | [Controlling cost](07-controlling-cost.md) | Why this subscription has no spending limit, why budgets are late, and the limits built instead |
| 8 | [Monitoring and load testing](08-monitoring-and-load-testing.md) | Metrics and alerts, percentiles, what happens as a service fills up, and how to read the results |
| 9 | [Questions to test yourself](09-questions.md) | Short questions with answers, and exercises that change the code |
| 10 | [Further reading](10-further-reading.md) | Papers and docs behind the ideas |

The one idea to take away: **anything you want to rely on has to be measured or enforced, not assumed.** That applies at every level here. The rule for choosing a model was committed before the results existed. The ONNX file had to match PyTorch on 7,575 images before the test set could be opened. A budget only warns, up to about two days late, so the real cost limits are replica caps, a timer and an address list, each of which holds whether or not anyone is watching.

The code runs with `uv run fruity`. The numbers quoted come from [evals/](../../evals/), and the reasons behind each choice are in [decisions.md](../decisions.md).
