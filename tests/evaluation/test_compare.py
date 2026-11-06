"""The whole comparison, through the command line, on a made-up Food-101 folder and untrained models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import timm
import torch
from PIL import Image

from fruity import cli
from fruity.lib.evaluation import compare
from fruity.lib.training.data import Food101DataModule

CLASSES = ["apple_pie", "pizza"]
IMAGES_PER_CLASS = 8
MODELS = {"tiny": "mobilenetv3_small_050", "small": "mobilenetv3_small_100"}


def _write_food101(root: Path) -> None:
    """Lay out the folder that torchvision expects, with random images."""
    meta = root / "food-101" / "meta"
    meta.mkdir(parents=True)
    names = {label: [f"{label}/{number}" for number in range(IMAGES_PER_CLASS)] for label in CLASSES}
    for split in ("train", "test"):
        (meta / f"{split}.json").write_text(json.dumps(names), encoding="utf-8")
    for label, files in names.items():
        (root / "food-101" / "images" / label).mkdir(parents=True)
        for file in files:
            pixels = torch.randint(0, 255, (48, 48, 3), dtype=torch.uint8).numpy()
            Image.fromarray(pixels).save(root / "food-101" / "images" / f"{file}.jpg")


def _write_run(runs: Path, experiment: str, model_name: str) -> None:
    """Save what a finished training run leaves behind."""
    serving = runs / f"final_{experiment}" / "serving"
    serving.mkdir(parents=True)
    net = timm.create_model(model_name, pretrained=False, num_classes=len(CLASSES))
    torch.save(net.state_dict(), serving / "model.pth")
    (serving / "labels.json").write_text(json.dumps(dict(enumerate(CLASSES))), encoding="utf-8")
    summary = {"model": model_name, "fit_seconds": 60.0}
    (serving.parent / "metrics.json").write_text(json.dumps(summary), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the comparison at made-up data and runs, with small samples."""
    _write_food101(tmp_path / "data")
    for experiment, model_name in MODELS.items():
        _write_run(tmp_path / "runs", experiment, model_name)
    probes = {experiment: {"0.001": 0.5, "0.0003": 0.4} for experiment in MODELS}
    (tmp_path / "probes.json").write_text(json.dumps(probes), encoding="utf-8")
    datamodule = Food101DataModule(str(tmp_path / "data"), 32, 0.25, 42, 4, 0)
    datamodule.setup()
    monkeypatch.setattr(compare, "_load_datamodule", lambda: datamodule)
    overrides = {
        "runs_dir": tmp_path / "runs",
        "experiments": list(MODELS),
        "probes_path": tmp_path / "probes.json",
        "results_path": tmp_path / "comparison.json",
        "report_path": tmp_path / "RESULTS.md",
        "chart_path": tmp_path / "comparison.png",
        "core": 0,
        "latency_images": 3,
        "latency_warmup": 1,
        "calibration_images": 2,
        "worst_classes": 1,
    }
    for name, value in overrides.items():
        monkeypatch.setattr(compare.CONFIG, name, value)
    monkeypatch.setattr("sys.argv", ["fruity", "compare"])
    return tmp_path


def test_it_measures_every_model_in_every_form_and_writes_the_results(workspace: Path) -> None:
    cli.main()
    results = json.loads((workspace / "comparison.json").read_text(encoding="utf-8"))
    assert [result["experiment"] for result in results] == list(MODELS)
    for result in results:
        assert result["learning_rate"] == pytest.approx(0.001)
        for form in ("pytorch", "onnx", "onnx_quantized"):
            assert 0 <= result[form]["top1"] <= 1
            assert result[form]["latency_p95_ms"] > 0
        assert result["onnx_quantized"]["size_mb"] < result["onnx"]["size_mb"]
        assert result["onnx"]["top1"] == pytest.approx(result["pytorch"]["top1"])
    report = (workspace / "RESULTS.md").read_text(encoding="utf-8")
    assert all(model_name in report for model_name in MODELS.values())
    assert (workspace / "comparison.png").stat().st_size > 0


def test_a_restart_keeps_the_models_already_measured(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cli.main()
    before = (workspace / "comparison.json").read_bytes()

    def fail(*_: object) -> None:
        raise AssertionError("A finished model was measured again.")

    monkeypatch.setattr(compare, "_measure_model", fail)
    cli.main()
    assert (workspace / "comparison.json").read_bytes() == before
