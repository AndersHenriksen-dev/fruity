"""What was measured about each model, and the rule that picks one. The rule is explained in docs/decisions.md."""

from __future__ import annotations

from pydantic import BaseModel


class RuntimeResult(BaseModel):
    """One way of running a model, and what it was measured to do."""

    size_mb: float
    top1: float
    top5: float
    latency_p50_ms: float
    latency_p95_ms: float


class ClassAccuracy(BaseModel):
    """How often a model was right about one class."""

    label: str
    top1: float


class ModelResult(BaseModel):
    """Everything measured about one trained model."""

    name: str
    experiment: str
    learning_rate: float
    fit_seconds: float
    pytorch: RuntimeResult
    onnx: RuntimeResult
    onnx_quantized: RuntimeResult
    worst_classes: list[ClassAccuracy]


def within_margin(results: list[ModelResult], margin: float) -> list[ModelResult]:
    """Keep the models close enough to the best validation accuracy, smallest first."""
    best = max(result.pytorch.top1 for result in results)
    return sorted(
        (result for result in results if round(best - result.pytorch.top1, 9) <= margin),
        key=lambda result: result.pytorch.size_mb,
    )


def choose_model(results: list[ModelResult], margin: float, max_p95_ms: float) -> ModelResult:
    """Apply the selection rule, judging each model as PyTorch, which is the form every model has.

    Args:
        results: The measured models.
        margin: How far below the best validation accuracy a model may be, as a fraction.
        max_p95_ms: The slowest 95th percentile latency allowed at one vCPU.

    Returns:
        The smallest model that is both close enough to the best and fast enough.

    Raises:
        ValueError: If no model meets both limits.
    """
    for result in within_margin(results, margin):
        if result.pytorch.latency_p95_ms <= max_p95_ms:
            return result
    raise ValueError("No model is both accurate enough and fast enough.")
