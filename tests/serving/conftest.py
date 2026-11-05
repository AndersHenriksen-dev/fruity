"""A small untrained model, saved the way training saves one, so no test needs a download."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import timm
import torch

MODEL_NAME = "resnet18"
LABELS = {"0": "apple_pie", "1": "pizza", "2": "sushi"}


@pytest.fixture
def saved_model(tmp_path: Path) -> tuple[Path, Path]:
    """Save weights and labels, and return their paths."""
    net = timm.create_model(MODEL_NAME, pretrained=False, in_chans=3, num_classes=len(LABELS))
    weights = tmp_path / "model.pth"
    labels = tmp_path / "labels.json"
    torch.save(net.state_dict(), weights)
    labels.write_text(json.dumps(LABELS), encoding="utf-8")
    return weights, labels
