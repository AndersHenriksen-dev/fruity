"""Run the published ONNX model in the two ways the graphics need: on many images at once, and for its features.

The features are the numbers the final layer reads, so two photos the model sees as alike have features that are close.
They are read from the published file itself, by also returning the final layer's input, so no training files are
needed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
import onnxruntime

_FINAL_LAYERS = {"Gemm", "MatMul"}


def feature_name(model: onnx.ModelProto) -> str:
    """Find the tensor the final layer reads, walking back from the output through any bias additions.

    Raises:
        ValueError: If the output does not come from a final layer this can recognise.
    """
    producers = {output: node for node in model.graph.node for output in node.output}
    weights = {initializer.name for initializer in model.graph.initializer}
    node = producers.get(model.graph.output[0].name)
    while node is not None and node.op_type == "Add":
        node = next((producers[name] for name in node.input if name in producers), None)
    if node is None or node.op_type not in _FINAL_LAYERS:
        raise ValueError("The model's output does not come from a Gemm or MatMul layer.")
    return str(next(name for name in node.input if name not in weights))


class Network:
    """The ONNX model, returning both the logits and the features the final layer reads."""

    def __init__(self, path: Path) -> None:
        """Load the model and add its features as a second output."""
        model = onnx.load(str(path))
        name = feature_name(model)
        model.graph.output.append(onnx.helper.make_tensor_value_info(name, onnx.TensorProto.FLOAT, None))
        self._session = onnxruntime.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def run(self, batch: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Turn a batch of prepared images into logits and features."""
        logits, features = self._session.run(None, {self._input: batch})
        return np.asarray(logits), np.asarray(features).reshape(len(batch), -1)


def softmax(logits: np.ndarray) -> np.ndarray:
    """Turn logits into probabilities, one row per image."""
    shifted = np.exp(logits - logits.max(axis=1, keepdims=True))
    return np.asarray(shifted / shifted.sum(axis=1, keepdims=True))
