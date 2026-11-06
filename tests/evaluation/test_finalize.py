"""The final step, through the command line, on a made-up Food-101 folder and untrained models."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import timm
import torch

from fruity import cli
from fruity.lib.evaluation import compare, finalize
from fruity.lib.evaluation.finalize import Candidate, check_export, choose_run
from fruity.lib.evaluation.scoring import Scores
from fruity.lib.training.data import Food101DataModule
from tests.evaluation.test_compare import CLASSES, IMAGES_PER_CLASS, _write_food101

MODEL = "mobilenetv3_small_050"
SWEEP_SCORES = {"sweep_a": 0.60, "sweep_b": 0.70}


def _write_run(run: Path, top1: float, learning_rate: float) -> None:
    """Save what a finished training run leaves behind."""
    (run / "serving").mkdir(parents=True)
    (run / ".hydra").mkdir()
    net = timm.create_model(MODEL, pretrained=False, num_classes=len(CLASSES))
    torch.save(net.state_dict(), run / "serving" / "model.pth")
    (run / "serving" / "labels.json").write_text(json.dumps(dict(enumerate(CLASSES))), encoding="utf-8")
    metrics = {"model": MODEL, "val/acc": top1}
    (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    settings = f"model:\n  optimizer:\n    lr: {learning_rate}\n    weight_decay: 0.05\n"
    (run / ".hydra" / "config.yaml").write_text(settings, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the final step at made-up data and runs, with one comparison run scoring below the sweep's best."""
    _write_food101(tmp_path / "data")
    _write_run(tmp_path / "comparison_run", 0.65, 0.0001)
    for name, top1 in SWEEP_SCORES.items():
        _write_run(tmp_path / name, top1, 0.0002)
    compared = [{"experiment": "tiny", "pytorch": {"top1": 0.65}}]
    (tmp_path / "comparison.json").write_text(json.dumps(compared), encoding="utf-8")
    datamodule = Food101DataModule(str(tmp_path / "data"), 32, 0.25, 42, 4, 0)
    datamodule.setup()
    monkeypatch.setattr(compare, "load_datamodule", lambda: datamodule)
    for name, value in {"core": 0, "latency_images": 3, "latency_warmup": 1, "worst_classes": 1}.items():
        monkeypatch.setattr(compare.CONFIG, name, value)
    overrides = {
        "comparison_results": tmp_path / "comparison.json",
        "comparison_experiment": "tiny",
        "comparison_run": tmp_path / "comparison_run",
        "sweep_runs": [tmp_path / name for name in SWEEP_SCORES],
        "output_dir": tmp_path / "final",
        "results_path": tmp_path / "final.json",
        "report_path": tmp_path / "FINAL.md",
    }
    for name, value in overrides.items():
        monkeypatch.setattr(finalize.CONFIG, name, value)
    monkeypatch.setattr("sys.argv", ["fruity", "finalize"])
    return tmp_path


def test_it_scores_the_best_run_on_every_test_image_and_writes_the_results(workspace: Path) -> None:
    cli.main()
    result = json.loads((workspace / "final.json").read_text(encoding="utf-8"))
    assert result["run"] == "sweep_b"
    assert result["test"]["images"] == IMAGES_PER_CLASS * len(CLASSES)
    assert result["validation"]["images"] == IMAGES_PER_CLASS * len(CLASSES) // 4
    assert result["validation"]["top1"] == pytest.approx(result["pytorch_validation"]["top1"])
    assert len(result["candidates"]) == 3
    assert (workspace / "final" / "labels.json").exists()
    report = (workspace / "FINAL.md").read_text(encoding="utf-8")
    assert "**`sweep_b`**" in report
    assert result["sha256"] in report


def test_a_second_run_never_reads_the_test_set_and_restores_the_report(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli.main()
    before = (workspace / "final.json").read_bytes()
    report = (workspace / "FINAL.md").read_bytes()
    (workspace / "FINAL.md").unlink()

    def fail(*_: object) -> None:
        raise AssertionError("The test set was scored a second time.")

    monkeypatch.setattr(finalize, "score", fail)
    cli.main()
    assert (workspace / "final.json").read_bytes() == before
    assert (workspace / "FINAL.md").read_bytes() == report


def test_a_broken_export_stops_before_the_test_set_and_saves_nothing(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_: object) -> None:
        raise RuntimeError("ONNX and PyTorch differ.")

    monkeypatch.setattr(finalize, "check_export", fail)
    with pytest.raises(RuntimeError, match="differ"):
        cli.main()
    assert not (workspace / "final.json").exists()


def test_the_best_validation_score_chooses_the_run() -> None:
    low = Candidate(run=Path("low"), learning_rate=0.1, weight_decay=0.1, val_top1=0.1)
    high = Candidate(run=Path("high"), learning_rate=0.1, weight_decay=0.1, val_top1=0.2)
    assert choose_run([low, high]) == high


def test_check_export_allows_a_tiny_gap_and_rejects_a_larger_one() -> None:
    trained = Scores(100, 0.880, 0.97, [])
    check_export(trained, Scores(100, 0.8805, 0.97, []), 0.001)
    with pytest.raises(RuntimeError, match="test set was not used"):
        check_export(trained, Scores(100, 0.870, 0.97, []), 0.001)
