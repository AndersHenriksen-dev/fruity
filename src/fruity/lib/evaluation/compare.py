"""Measure every trained model on validation data, apply the selection rule and write the results.

Finished models are kept in the results file, so a stopped comparison can simply be started again.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import hydra
import torch
from PIL import Image
from pydantic import BaseModel
from torchvision import datasets

from fruity.lib.evaluation.latency import Latency, one_core, time_calls
from fruity.lib.evaluation.onnx_model import OnnxModel, export_onnx, quantize_onnx
from fruity.lib.evaluation.report import draw_chart, write_results
from fruity.lib.evaluation.scoring import Predict, Scores, score
from fruity.lib.evaluation.selection import ClassAccuracy, ModelResult, RuntimeResult, choose_model
from fruity.lib.serving.inference import Classifier, classify, load_classifier
from fruity.lib.shared.preprocess import evaluation_transform
from fruity.lib.shared.settings import CONFIG_DIR, config_for, read_config
from fruity.lib.training.data import Food101DataModule, split_indices


class CompareConfig(BaseModel):
    """The models to measure and how."""

    runs_dir: Path
    experiments: list[str]
    probes_path: Path
    results_path: Path
    report_path: Path
    chart_path: Path
    margin: float
    max_p95_ms: float
    core: int
    latency_images: int
    latency_warmup: int
    calibration_images: int
    worst_classes: int


CONFIG = config_for(__name__, CompareConfig)
_TOP_K = 3


def load_datamodule() -> Food101DataModule:
    """Build the data as training does, from the same config file."""
    settings = read_config(CONFIG_DIR / "training" / "datamodule" / "foods_101.yaml", dict[str, object])
    datamodule: Food101DataModule = hydra.utils.instantiate(settings)
    datamodule.setup()
    return datamodule


def gpu_predictor(net: torch.nn.Module) -> Predict:
    """Run a PyTorch model on the GPU if there is one, which only speeds up scoring."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    net.to(device)

    def predict(batch: torch.Tensor) -> torch.Tensor:
        with torch.inference_mode():
            logits: torch.Tensor = net(batch.to(device))
        return logits.cpu()

    return predict


def image_reader(datamodule: Food101DataModule) -> tuple[datasets.Food101, list[int]]:
    """Give the raw validation images, in a fixed random order, without the labels or preprocessing."""
    raw = datasets.Food101(datamodule.data_dir, split="train")
    _, val = split_indices(len(raw), datamodule.val_fraction, datamodule.split_seed)
    return raw, val


def _time_pytorch(classifier: Classifier, raw: datasets.Food101, indices: list[int]) -> Latency:
    """Time a PyTorch model from image file to answer, the path a request takes."""
    classifier.net.cpu()

    def call(index: int) -> object:
        return classify(classifier, raw[index][0], top_k=_TOP_K)

    with one_core(CONFIG.core):
        return time_calls(call, indices, CONFIG.latency_warmup)


def time_onnx(path: Path, classifier: Classifier, raw: datasets.Food101, indices: list[int]) -> Latency:
    """Time an ONNX model from image file to answer. The thread limit must be set as the session opens."""

    def call(index: int) -> object:
        image: Image.Image = raw[index][0]
        logits = model(classifier.preprocess(image.convert("RGB")).unsqueeze(0))
        return logits.softmax(dim=1).topk(min(_TOP_K, len(classifier.labels)))

    with one_core(CONFIG.core):
        model = OnnxModel(path, threads=1)
        return time_calls(call, indices, CONFIG.latency_warmup)


def _runtime_result(path: Path, scores: Scores, latency: Latency) -> RuntimeResult:
    """Combine what was measured about one form of a model."""
    return RuntimeResult(
        size_mb=path.stat().st_size / 1_000_000,
        top1=scores.top1,
        top5=scores.top5,
        latency_p50_ms=latency.p50_ms,
        latency_p95_ms=latency.p95_ms,
    )


def _calibration_images(datamodule: Food101DataModule) -> Iterator[torch.Tensor]:
    """Yield preprocessed training images, so quantization never sees the images it is scored on."""
    plain = datasets.Food101(
        datamodule.data_dir,
        split="train",
        transform=evaluation_transform(datamodule.image_size),
    )
    train, _ = split_indices(len(plain), datamodule.val_fraction, datamodule.split_seed)
    for index in train[: CONFIG.calibration_images]:
        yield plain[index][0]


def worst_classes(scores: Scores, labels: dict[int, str]) -> list[ClassAccuracy]:
    """Name the classes a model gets wrong most often, worst first."""
    worst = sorted(labels, key=lambda index: scores.per_class[index])[: CONFIG.worst_classes]
    return [ClassAccuracy(label=labels[index], top1=scores.per_class[index]) for index in worst]


def _measure_model(experiment: str, learning_rate: float, datamodule: Food101DataModule) -> ModelResult:
    """Score and time one trained model as PyTorch, as ONNX and as quantized ONNX."""
    run = CONFIG.runs_dir / f"final_{experiment}"
    saved = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    weights = run / "serving" / "model.pth"
    classifier = load_classifier(saved["model"], weights, run / "serving" / "labels.json", datamodule.image_size)
    num_classes = len(classifier.labels)
    raw, indices = image_reader(datamodule)
    sample = indices[: CONFIG.latency_warmup + CONFIG.latency_images]

    # One loader for all three forms, because its workers stay alive and take over a minute to start.
    batches = datamodule.val_dataloader()

    scores = score(gpu_predictor(classifier.net), batches, num_classes)
    pytorch = _runtime_result(weights, scores, _time_pytorch(classifier, raw, sample))

    plain_path = run / "onnx" / "model.onnx"
    export_onnx(classifier.net, datamodule.image_size, plain_path)
    plain_scores = score(OnnxModel(plain_path), batches, num_classes)
    onnx = _runtime_result(plain_path, plain_scores, time_onnx(plain_path, classifier, raw, sample))

    quantized_path = run / "onnx" / "model_quantized.onnx"
    quantize_onnx(plain_path, quantized_path, _calibration_images(datamodule))
    quantized_scores = score(OnnxModel(quantized_path), batches, num_classes)
    quantized = _runtime_result(quantized_path, quantized_scores, time_onnx(quantized_path, classifier, raw, sample))

    return ModelResult(
        name=saved["model"],
        experiment=experiment,
        learning_rate=learning_rate,
        fit_seconds=saved["fit_seconds"],
        pytorch=pytorch,
        onnx=onnx,
        onnx_quantized=quantized,
        worst_classes=worst_classes(scores, classifier.labels),
    )


def _save(results: list[ModelResult]) -> None:
    """Keep what has been measured so far."""
    payload = [result.model_dump() for result in results]
    CONFIG.results_path.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))


def main() -> None:
    """Measure what is not measured yet, then choose a model and write the results."""
    results = []
    if CONFIG.results_path.exists():
        saved = json.loads(CONFIG.results_path.read_text(encoding="utf-8"))
        results = [ModelResult.model_validate(entry) for entry in saved]
    done = {result.experiment for result in results}
    probes = json.loads(CONFIG.probes_path.read_text(encoding="utf-8"))
    datamodule = load_datamodule()
    for experiment in CONFIG.experiments:
        if experiment in done:
            continue
        rates: dict[str, float] = probes[experiment]
        results.append(_measure_model(experiment, float(max(rates, key=lambda rate: rates[rate])), datamodule))
        _save(results)
        print(f"{experiment}: {results[-1].pytorch}", flush=True)
    chosen = choose_model(results, CONFIG.margin, CONFIG.max_p95_ms)
    write_results(results, chosen, CONFIG.margin, CONFIG.max_p95_ms, CONFIG.report_path)
    draw_chart(results, chosen, CONFIG.max_p95_ms, CONFIG.chart_path)
    print(f"chosen: {chosen.name}", flush=True)
