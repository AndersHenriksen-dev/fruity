"""Fix the final model and score it on the test set, once.

The saved results are the lock: when they exist, the test set is not read again and only the report is rewritten.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

from pydantic import BaseModel

from fruity.lib.evaluation import compare
from fruity.lib.evaluation.onnx_model import OnnxModel, export_onnx
from fruity.lib.evaluation.scoring import Scores, score
from fruity.lib.evaluation.selection import ClassAccuracy
from fruity.lib.serving.inference import load_classifier
from fruity.lib.shared.settings import config_for, read_config

_Z_95 = 1.96


class FinalizeConfig(BaseModel):
    """The runs that compete, and where the final model and its results go."""

    comparison_results: Path
    comparison_experiment: str
    comparison_run: Path
    sweep_runs: list[Path]
    output_dir: Path
    results_path: Path
    report_path: Path
    max_export_gap: float


CONFIG = config_for(__name__, FinalizeConfig)


class _OptimizerSettings(BaseModel):
    lr: float
    weight_decay: float


class _ModelSettings(BaseModel):
    optimizer: _OptimizerSettings


class _RunSettings(BaseModel):
    """The part of a run's saved Hydra config that the results report."""

    model: _ModelSettings


class Candidate(BaseModel):
    """One trained run that could become the final model."""

    run: Path
    learning_rate: float
    weight_decay: float
    val_top1: float


class Scored(BaseModel):
    """Accuracy on one set of images."""

    images: int
    top1: float
    top5: float


class FinalResult(BaseModel):
    """Everything measured about the final model."""

    model: str
    run: str
    sha256: str
    size_mb: float
    pytorch_validation: Scored
    validation: Scored
    test: Scored
    latency_p50_ms: float
    latency_p95_ms: float
    worst_classes: list[ClassAccuracy]
    candidates: list[Candidate]


def _read_candidate(run: Path, val_top1: float) -> Candidate:
    """Combine a run's score with the settings it was trained with."""
    settings = read_config(run / ".hydra" / "config.yaml", _RunSettings).model.optimizer
    return Candidate(run=run, learning_rate=settings.lr, weight_decay=settings.weight_decay, val_top1=val_top1)


def _read_candidates() -> list[Candidate]:
    """Read every competing run: the one from the comparison and those from the sweep."""
    compared = json.loads(CONFIG.comparison_results.read_text(encoding="utf-8"))
    baseline = next(entry for entry in compared if entry["experiment"] == CONFIG.comparison_experiment)
    candidates = [_read_candidate(CONFIG.comparison_run, baseline["pytorch"]["top1"])]
    for run in CONFIG.sweep_runs:
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        candidates.append(_read_candidate(run, metrics["val/acc"]))
    return candidates


def choose_run(candidates: list[Candidate]) -> Candidate:
    """Take the run with the best validation accuracy, the only score that may decide this."""
    return max(candidates, key=lambda candidate: candidate.val_top1)


def check_export(pytorch: Scores, onnx: Scores, max_gap: float) -> None:
    """Stop before the test set is used if the exported file does not behave like the trained model.

    Raises:
        RuntimeError: If the two differ by more than `max_gap`.
    """
    gap = abs(pytorch.top1 - onnx.top1)
    if gap > max_gap:
        raise RuntimeError(f"ONNX and PyTorch differ by {gap:.2%} on validation data. The test set was not used.")


def _summarize(scores: Scores) -> Scored:
    """Keep what the results file needs from a score."""
    return Scored(images=scores.images, top1=scores.top1, top5=scores.top5)


def _measure(chosen: Candidate, candidates: list[Candidate]) -> FinalResult:
    """Export the chosen run, confirm the file on validation data, time it, then score it on the test set."""
    datamodule = compare.load_datamodule()
    saved = json.loads((chosen.run / "metrics.json").read_text(encoding="utf-8"))
    labels_path = chosen.run / "serving" / "labels.json"
    classifier = load_classifier(
        saved["model"],
        chosen.run / "serving" / "model.pth",
        labels_path,
        datamodule.image_size,
    )
    num_classes = len(classifier.labels)

    validation = datamodule.val_dataloader()
    pytorch_scores = score(compare.gpu_predictor(classifier.net), validation, num_classes)
    onnx_path = CONFIG.output_dir / "model.onnx"
    export_onnx(classifier.net, datamodule.image_size, onnx_path)
    shutil.copy(labels_path, CONFIG.output_dir / "labels.json")
    onnx_scores = score(OnnxModel(onnx_path), validation, num_classes)
    check_export(pytorch_scores, onnx_scores, CONFIG.max_export_gap)

    raw, indices = compare.image_reader(datamodule)
    latency = compare.time_onnx(
        onnx_path,
        classifier,
        raw,
        indices[: compare.CONFIG.latency_warmup + compare.CONFIG.latency_images],
    )

    test_scores = score(OnnxModel(onnx_path), datamodule.test_dataloader(), num_classes)
    return FinalResult(
        model=saved["model"],
        run=chosen.run.name,
        sha256=hashlib.sha256(onnx_path.read_bytes()).hexdigest(),
        size_mb=onnx_path.stat().st_size / 1_000_000,
        pytorch_validation=_summarize(pytorch_scores),
        validation=_summarize(onnx_scores),
        test=_summarize(test_scores),
        latency_p50_ms=latency.p50_ms,
        latency_p95_ms=latency.p95_ms,
        worst_classes=compare.worst_classes(test_scores, classifier.labels),
        candidates=candidates,
    )


def _margin_points(scored: Scored) -> float:
    """How far sampling alone could move an accuracy, in points, at 95% confidence."""
    return _Z_95 * math.sqrt(scored.top1 * (1 - scored.top1) / scored.images) * 100


def _candidate_table(result: FinalResult) -> list[str]:
    """One row per competing run, best first."""
    rows = ["| Run | Learning rate | Weight decay | Validation top-1 |", "|---|---:|---:|---:|"]
    for candidate in sorted(result.candidates, key=lambda candidate: -candidate.val_top1):
        name = f"**`{candidate.run.name}`**" if candidate.run.name == result.run else f"`{candidate.run.name}`"
        rows.append(
            f"| {name} | {candidate.learning_rate:.2e} | {candidate.weight_decay:.3f} | {candidate.val_top1:.2%} |",
        )
    return rows


def _write_report(result: FinalResult, path: Path) -> None:
    """Write the final results file from the saved measurements."""
    lines = [
        "# The final model",
        "",
        "Generated by `fruity finalize` from `evals/final.json`. Do not edit by hand.",
        "",
        f"The deployed model is `{result.model}` as plain ONNX. The run, its settings and its form were all fixed on "
        "validation data before the test set was read. The command reads the test set once and refuses a second time.",
        "",
        "## Accuracy",
        "",
        "| Data | Images | Top-1 | Top-5 |",
        "|---|---:|---:|---:|",
        f"| Test | {result.test.images:,} | {result.test.top1:.2%} | {result.test.top5:.2%} |",
        f"| Validation | {result.validation.images:,} | {result.validation.top1:.2%} | {result.validation.top5:.2%} |",
        "",
        f"Latency is one image from file to answer on one CPU core: p50 {result.latency_p50_ms:.0f} ms, "
        f"p95 {result.latency_p95_ms:.0f} ms.",
        "",
        "## Which run",
        "",
        "One run comes from the model comparison, and six from a Weights & Biases sweep of learning rate and weight "
        "decay. The best validation top-1 decides.",
        "",
        *_candidate_table(result),
        "",
        "## Worst classes on the test set",
        "",
        "| Class | Top-1 |",
        "|---|---:|",
        *[f"| {entry.label.replace('_', ' ')} | {entry.top1:.1%} |" for entry in result.worst_classes],
        "",
        "## The file",
        "",
        f"`model.onnx`, {result.size_mb:.1f} MB, SHA-256 `{result.sha256}`.",
        "",
        "## Limits",
        "",
        "- Test accuracy is above validation accuracy, most likely because the data differs. "
        "The dataset's authors reviewed the test images by hand and left noise, including some wrong labels, "
        "in the training images on purpose. "
        "Validation images come from the training images, and real uploads may be messier than the test set too.",
        f"- Sampling alone could move the test top-1 by about {_margin_points(result.test):.2f} points at 95% "
        f"confidence, and a validation top-1 by about {_margin_points(result.validation):.2f} points. "
        "Gaps between runs smaller than that may be noise.",
        "- Every run used one seed.",
        "- Latency comes from one core of a desktop CPU, which may be faster than a vCPU in the cloud.",
        "",
    ]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def main() -> None:
    """Measure the final model unless it has been measured, then write the report."""
    if CONFIG.results_path.exists():
        print(f"{CONFIG.results_path} exists, so the test set stays closed. Rewriting the report only.", flush=True)
        result = FinalResult.model_validate_json(CONFIG.results_path.read_text(encoding="utf-8"))
    else:
        candidates = _read_candidates()
        chosen = choose_run(candidates)
        print(f"final run: {chosen.run} at {chosen.val_top1:.2%} on validation", flush=True)
        result = _measure(chosen, candidates)
        CONFIG.results_path.write_bytes(result.model_dump_json(indent=2).encode("utf-8"))
    _write_report(result, CONFIG.report_path)
    print(f"test top-1 {result.test.top1:.2%}, top-5 {result.test.top5:.2%}", flush=True)
