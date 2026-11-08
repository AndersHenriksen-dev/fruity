"""The baselines, through the command line, on a made-up Food-101 folder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from fruity import cli
from fruity.lib.evaluation import baselines, compare
from fruity.lib.training.data import Food101DataModule
from tests.evaluation.test_compare import CLASSES, _write_food101


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the baselines at made-up data, in this process, and at a saved final result."""
    _write_food101(tmp_path / "data")
    datamodule = Food101DataModule(str(tmp_path / "data"), 32, 0.25, 42, 4, 0)
    datamodule.setup()
    monkeypatch.setattr(compare, "load_datamodule", lambda: datamodule)
    final = {"model": "convnext_tiny", "validation": {"top1": 0.88, "top5": 0.97}, "test": {"top1": 0.91, "top5": 0.98}}
    (tmp_path / "final.json").write_text(json.dumps(final), encoding="utf-8")
    overrides = {
        # Worker processes take seconds each to start on Windows. The real run uses them.
        "workers": 1,
        "features_dir": tmp_path / "features",
        "results_path": tmp_path / "baselines.json",
        "report_path": tmp_path / "BASELINES.md",
        "final_results": tmp_path / "final.json",
    }
    for name, value in overrides.items():
        monkeypatch.setattr(baselines.CONFIG, name, value)
    monkeypatch.setattr("sys.argv", ["fruity", "baselines"])
    return tmp_path


def test_every_baseline_is_scored_on_the_validation_images(workspace: Path) -> None:
    cli.main()
    results = json.loads((workspace / "baselines.json").read_text(encoding="utf-8"))
    assert results["val_images"] == 4
    names = [baseline["name"] for baseline in results["baselines"]]
    assert names[0] == "Guessing"
    assert results["baselines"][0]["top1"] == pytest.approx(1 / len(CLASSES))
    assert all(0 <= baseline["top1"] <= 1 for baseline in results["baselines"])
    report = (workspace / "BASELINES.md").read_text(encoding="utf-8")
    assert "88.00%" in report
    assert "50.76%" in report


def test_saved_results_are_reported_without_measuring_again(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cli.main()

    def fail() -> None:
        raise AssertionError("The baselines were measured again.")

    monkeypatch.setattr(baselines, "measure", fail)
    (workspace / "BASELINES.md").unlink()
    cli.main()
    assert (workspace / "BASELINES.md").exists()


def test_the_features_hold_colour_then_shape_then_texture() -> None:
    image = Image.fromarray(np.random.default_rng(0).integers(0, 255, (150, 200, 3), dtype=np.uint8))
    features = baselines.all_features(image)
    colours = int(np.prod(baselines.CONFIG.color_bins))
    assert features[:colours].sum() == pytest.approx(1.0)
    assert features.dtype == np.float32
    assert len(features) == len(baselines.all_features(image.resize((400, 300))))


def test_a_red_image_and_a_green_image_have_different_colours() -> None:
    red = baselines.color_features(Image.new("RGB", (64, 64), "red"))
    green = baselines.color_features(Image.new("RGB", (64, 64), "green"))
    assert not np.allclose(red, green)
