"""A whole training run on made-up images, through the real config, ending in a model that serving can load."""

from __future__ import annotations

import json
from pathlib import Path

import hydra
import pytest
import torch
from lightning.pytorch import LightningDataModule, Trainer
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

from fruity.lib.evaluation.pytorch_model import classify, load_classifier
from fruity.lib.shared.settings import CONFIG_DIR
from fruity.lib.training.train import train

CLASSES = ["apple_pie", "pizza", "sushi"]


class TinyImages(LightningDataModule):
    """A few random images, so a whole run takes seconds and needs no download."""

    classes = CLASSES

    def _loader(self) -> DataLoader:
        images = torch.randn(8, 3, 32, 32)
        return DataLoader(TensorDataset(images, torch.randint(0, len(CLASSES), (8,))), batch_size=4)

    def train_dataloader(self) -> DataLoader:
        return self._loader()

    def val_dataloader(self) -> DataLoader:
        return self._loader()

    def test_dataloader(self) -> DataLoader:
        return self._loader()


def test_a_run_trains_tests_and_saves_a_model_that_serving_can_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[str] = []
    real_validate = Trainer.validate

    def validate(trainer: Trainer, **arguments: object) -> object:
        validated.append(str(arguments["ckpt_path"]))
        return real_validate(trainer, **arguments)

    monkeypatch.setattr(Trainer, "validate", validate)
    with hydra.initialize_config_dir(str(CONFIG_DIR / "training"), version_base="1.3"):
        config = hydra.compose(
            "train.yaml",
            overrides=[
                f"paths.output_dir={tmp_path.as_posix()}",
                "datamodule._target_=tests.training.test_train.TinyImages",
                "~datamodule.data_dir",
                "~datamodule.image_size",
                "~datamodule.val_fraction",
                "~datamodule.split_seed",
                "~datamodule.batch_size",
                "~datamodule.num_workers",
                "model.num_classes=3",
                "model.net.pretrained=false",
                "trainer.max_epochs=1",
                "trainer.accelerator=cpu",
                "trainer.precision=32",
                "~callbacks.rich_progress_bar",
                "test=true",
            ],
        )

    metrics = train(config)

    assert 0.0 <= metrics["test/acc"] <= 1.0
    assert [Path(checkpoint).parent.name for checkpoint in validated] == ["checkpoints"]
    summary = json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))
    assert summary["model"] == "resnet18"
    assert summary["fit_seconds"] > 0
    classifier = load_classifier("resnet18", tmp_path / "serving/model.pth", tmp_path / "serving/labels.json", 64)
    assert classifier.labels == dict(enumerate(CLASSES))
    assert classify(classifier, Image.new("RGB", (80, 60)), top_k=1)[0].label in CLASSES
