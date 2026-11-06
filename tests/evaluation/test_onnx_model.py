"""Exporting and quantizing a real, small model."""

from __future__ import annotations

from pathlib import Path

import pytest
import timm
import torch

from fruity.lib.evaluation.onnx_model import OnnxModel, export_onnx, quantize_onnx

IMAGE_SIZE = 32


@pytest.fixture
def net() -> torch.nn.Module:
    torch.manual_seed(0)
    return timm.create_model("mobilenetv3_small_050", pretrained=False, num_classes=3).eval()


def test_the_export_gives_the_same_answers_at_any_batch_size(net: torch.nn.Module, tmp_path: Path) -> None:
    path = tmp_path / "model.onnx"
    export_onnx(net, IMAGE_SIZE, path)
    batch = torch.randn(3, 3, IMAGE_SIZE, IMAGE_SIZE)
    with torch.no_grad():
        expected = net(batch)
    assert OnnxModel(path)(batch).numpy() == pytest.approx(expected.numpy(), abs=1e-3)


def test_quantizing_gives_a_smaller_model_that_still_runs(net: torch.nn.Module, tmp_path: Path) -> None:
    plain = tmp_path / "model.onnx"
    quantized = tmp_path / "quantized.onnx"
    export_onnx(net, IMAGE_SIZE, plain)
    quantize_onnx(plain, quantized, [torch.randn(3, IMAGE_SIZE, IMAGE_SIZE) for _ in range(4)])
    assert quantized.stat().st_size < plain.stat().st_size
    assert list(tmp_path.glob("*_prepared.onnx")) == []
    assert OnnxModel(quantized)(torch.randn(2, 3, IMAGE_SIZE, IMAGE_SIZE)).shape == (2, 3)
