# 10. Further reading

## The model and the data

- Bossard, Guillaumin and Van Gool, [Food-101: Mining Discriminative Components with Random Forests](https://link.springer.com/chapter/10.1007/978-3-319-10599-4_29) (ECCV 2014). The dataset, including why training images were left noisy.
- Liu et al., [A ConvNet for the 2020s](https://arxiv.org/abs/2201.03545) (CVPR 2022). ConvNeXt, the deployed architecture.
- Howard et al., [Searching for MobileNetV3](https://arxiv.org/abs/1905.02244), and Tan and Le, [EfficientNet](https://arxiv.org/abs/1905.11946). The two smaller models in the comparison.
- [timm documentation](https://huggingface.co/docs/timm/index). Where the pretrained models come from.

## ONNX and quantization

- [ONNX Runtime: quantize models](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html). Static quantization and the QDQ format used here.
- [Exporting a PyTorch model to ONNX](https://pytorch.org/docs/stable/onnx.html).

## Containers

- [Docker: multi-stage builds](https://docs.docker.com/build/building/multi-stage/).
- [Docker: resource constraints](https://docs.docker.com/engine/containers/resource_constraints/). What `--cpus` and `--memory` do.
- [uv: using uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/).

## Terraform and Azure

- [Terraform: state](https://developer.hashicorp.com/terraform/language/state), and [Terraform tests](https://developer.hashicorp.com/terraform/language/tests), including mock providers.
- [Azure Container Apps: scaling](https://learn.microsoft.com/en-us/azure/container-apps/scale-app), and [IP restrictions](https://learn.microsoft.com/en-us/azure/container-apps/ip-restrictions).
- [Supported metrics for Container Apps](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-app-containerapps-metrics).

## Deployment

- [GitHub: OpenID Connect in Azure](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure). Signing in without a stored key.
- [Azure: workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation). The Azure side of it.

## Cost

- [Azure spending limit](https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/spending-limit), and [budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets). Including the delays described in this guide.
- [Container Apps billing](https://learn.microsoft.com/en-us/azure/container-apps/billing). What counts as active and idle.

## Monitoring and load

- Beyer et al., [Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/), from Google's SRE book. The four golden signals: latency, traffic, errors and saturation.
- [Little's law](https://en.wikipedia.org/wiki/Little%27s_law).
- [Locust documentation](https://docs.locust.io/).
