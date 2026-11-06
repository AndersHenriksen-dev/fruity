"""Exporting a model to ONNX, quantizing it, and running it."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import numpy as np
import onnxruntime
import torch
from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quantize_static
from onnxruntime.quantization.shape_inference import quant_pre_process

_INPUT = "image"
# Rounding the normalization, activation and add layers too took convnext_tiny from 88% to about 20% top-1.
# The saved comparison is in evals/quantization_settings.json.
_QUANTIZED_LAYERS = ["Conv", "MatMul", "Gemm"]


def export_onnx(net: torch.nn.Module, image_size: int, path: Path) -> None:
    """Save a model as one ONNX file that takes a batch of any size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        net.cpu().eval(),
        (torch.zeros(2, 3, image_size, image_size),),
        path,
        input_names=[_INPUT],
        output_names=["logits"],
        dynamic_axes={_INPUT: {0: "batch"}, "logits": {0: "batch"}},
        dynamo=True,
        external_data=False,
        # The progress lines hold emoji, which crash a Windows process whose output goes to a file.
        verbose=False,
    )


class _Calibration(CalibrationDataReader):
    """Feeds the images that decide how the numbers in the model are rounded."""

    def __init__(self, images: Iterable[torch.Tensor]) -> None:
        self._images: Iterator[torch.Tensor] = iter(images)

    def get_next(self) -> dict[str, np.ndarray] | None:
        image = next(self._images, None)
        return None if image is None else {_INPUT: image.unsqueeze(0).numpy()}


def quantize_onnx(source: Path, target: Path, calibration_images: Iterable[torch.Tensor]) -> None:
    """Store the model's numbers as 8-bit integers, with rounding fitted to real images.

    Args:
        source: The ONNX file to quantize.
        target: Where to save the result.
        calibration_images: Preprocessed single images, from outside the data the model will be scored on.
    """
    prepared = target.with_name(f"{target.stem}_prepared.onnx")
    quant_pre_process(str(source), str(prepared))
    quantize_static(
        str(prepared),
        str(target),
        _Calibration(calibration_images),
        quant_format=QuantFormat.QDQ,
        per_channel=True,
        op_types_to_quantize=_QUANTIZED_LAYERS,
        activation_type=QuantType.QUInt8,
        weight_type=QuantType.QInt8,
    )
    prepared.unlink()


class OnnxModel:
    """An ONNX file ready to run on the CPU."""

    def __init__(self, path: Path, threads: int = 0) -> None:
        """Open the file.

        Args:
            path: The ONNX file.
            threads: How many threads one call may use. Zero lets ONNX Runtime decide.
        """
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = threads
        self._session = onnxruntime.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])

    def __call__(self, batch: torch.Tensor) -> torch.Tensor:
        """Turn a batch of images into logits."""
        return torch.from_numpy(self._session.run(None, {_INPUT: batch.numpy()})[0])
