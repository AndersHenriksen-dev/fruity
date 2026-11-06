"""A small untrained model, exported the way the release was, so no test needs a download."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import timm

from fruity.lib.evaluation.onnx_model import export_onnx

MODEL_NAME = "resnet18"
IMAGE_SIZE = 64
LABELS = {"0": "apple_pie", "1": "pizza", "2": "sushi"}


@pytest.fixture(scope="session")
def saved_model(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Export a model and save its labels once, because exporting takes seconds. Return their paths."""
    folder = tmp_path_factory.mktemp("model")
    net = timm.create_model(MODEL_NAME, pretrained=False, in_chans=3, num_classes=len(LABELS))
    model = folder / "model.onnx"
    labels = folder / "labels.json"
    export_onnx(net, IMAGE_SIZE, model)
    labels.write_text(json.dumps(LABELS), encoding="utf-8")
    return model, labels
