"""Using the deployed model: loading it and naming the food in an image. The API and the command line share this.

The model runs on ONNX Runtime, so the serving image needs no PyTorch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime
from PIL import Image

from fruity.lib.shared.preprocess import prepare_image


@dataclass(frozen=True)
class Prediction:
    """One possible answer and how sure the model is of it."""

    label: str
    probability: float


@dataclass(frozen=True)
class Classifier:
    """A loaded model with what it takes to use it."""

    session: onnxruntime.InferenceSession
    labels: dict[int, str]
    image_size: int


def load_classifier(model_path: Path, labels_path: Path, image_size: int, threads: int) -> Classifier:
    """Load the model file and its labels.

    Args:
        model_path: The ONNX file.
        labels_path: The saved class names, by output index.
        image_size: The image size the model takes.
        threads: How many threads one call may use. A container should say, because ONNX Runtime counts the host's
            cores and not the container's share of them. Zero lets ONNX Runtime decide.

    Returns:
        The model, ready to run on the CPU.
    """
    saved = json.loads(labels_path.read_text(encoding="utf-8"))
    labels = {int(index): str(label) for index, label in saved.items()}
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = threads
    session = onnxruntime.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
    return Classifier(session, labels, image_size)


def classify(classifier: Classifier, image: Image.Image, top_k: int) -> list[Prediction]:
    """Name the most likely foods in one image, most likely first.

    Args:
        classifier: The loaded model.
        image: The image, in any color mode: a PNG with transparency or a grayscale photo works too.
        top_k: How many answers to return.

    Returns:
        The answers, with the probability of each.
    """
    batch = prepare_image(image.convert("RGB"), classifier.image_size)[np.newaxis]
    input_name = classifier.session.get_inputs()[0].name
    logits: np.ndarray = classifier.session.run(None, {input_name: batch})[0][0]
    shifted = np.exp(logits - logits.max())
    probabilities = shifted / shifted.sum()
    top = np.argsort(probabilities)[::-1][:top_k]
    return [Prediction(classifier.labels[int(index)], float(probabilities[index])) for index in top]
