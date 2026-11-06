"""The selection rule, and the results written from it."""

from __future__ import annotations

from pathlib import Path

import pytest

from fruity.lib.evaluation.report import draw_chart, write_results
from fruity.lib.evaluation.selection import ClassAccuracy, ModelResult, RuntimeResult, choose_model


def _model(name: str, size_mb: float, top1: float, p95_ms: float) -> ModelResult:
    run = RuntimeResult(size_mb=size_mb, top1=top1, top5=0.99, latency_p50_ms=p95_ms / 2, latency_p95_ms=p95_ms)
    return ModelResult(
        name=name,
        experiment=name,
        learning_rate=0.001,
        fit_seconds=600.0,
        pytorch=run,
        onnx=run,
        onnx_quantized=run,
        worst_classes=[ClassAccuracy(label="apple_pie", top1=0.5)],
    )


def test_it_takes_the_smallest_model_within_the_margin() -> None:
    results = [_model("big", 800, 0.90, 900), _model("medium", 100, 0.88, 200), _model("small", 20, 0.80, 50)]
    assert choose_model(results, margin=0.03, max_p95_ms=1000).name == "medium"


def test_a_model_exactly_on_the_margin_counts() -> None:
    results = [_model("big", 800, 0.90, 900), _model("small", 20, 0.875, 50)]
    assert choose_model(results, margin=0.025, max_p95_ms=1000).name == "small"


def test_a_model_that_is_too_slow_passes_to_the_next_smallest() -> None:
    results = [_model("big", 800, 0.90, 900), _model("medium", 100, 0.88, 1200)]
    assert choose_model(results, margin=0.03, max_p95_ms=1000).name == "big"


def test_it_refuses_when_nothing_is_fast_enough() -> None:
    with pytest.raises(ValueError, match="No model"):
        choose_model([_model("big", 800, 0.90, 1200)], margin=0.03, max_p95_ms=1000)


def test_the_results_name_the_chosen_model_and_its_numbers(tmp_path: Path) -> None:
    results = [_model("big", 800, 0.90, 900), _model("medium", 100, 0.88, 200)]
    path = tmp_path / "RESULTS.md"
    write_results(results, results[1], 0.03, 1000, path)
    text = path.read_text(encoding="utf-8")
    assert "**`medium`**" in text
    assert "88.00%" in text
    assert "apple pie" in text


def test_the_chart_is_drawn(tmp_path: Path) -> None:
    results = [_model("big", 800, 0.90, 900), _model("medium", 100, 0.88, 200)]
    path = tmp_path / "chart.png"
    draw_chart(results, results[1], 1000, path)
    assert path.stat().st_size > 0
