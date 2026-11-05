"""Using a trained model: loading it and naming the food in an image. The API and the command line share this."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import timm
import torch
from PIL import Image
from torchvision import transforms

from fruity.lib.shared.preprocess import evaluation_transform


@dataclass(frozen=True)
class Prediction:
    """One possible answer and how sure the model is of it."""

    label: str
    probability: float


@dataclass(frozen=True)
class Classifier:
    """A loaded model with what it takes to use it."""

    net: torch.nn.Module
    labels: dict[int, str]
    preprocess: transforms.Compose


def load_classifier(model_name: str, weights_path: Path, labels_path: Path, image_size: int) -> Classifier:
    """Load the weights and labels that one training run saved together.

    Args:
        model_name: The timm architecture the weights belong to.
        weights_path: The saved weights.
        labels_path: The saved class names, which also say how many classes there are.
        image_size: The image size the model was trained on.

    Returns:
        The model in evaluation mode, with its labels and preprocessing.
    """
    saved = json.loads(labels_path.read_text(encoding="utf-8"))
    labels = {int(index): str(label) for index, label in saved.items()}
    net = timm.create_model(model_name, pretrained=False, in_chans=3, num_classes=len(labels))
    net.load_state_dict(torch.load(weights_path, map_location="cpu"))
    net.eval()
    return Classifier(net, labels, evaluation_transform(image_size))


def classify(classifier: Classifier, image: Image.Image, top_k: int) -> list[Prediction]:
    """Name the most likely foods in one image, most likely first.

    Args:
        classifier: The loaded model.
        image: The image, in any color mode: a PNG with transparency or a grayscale photo works too.
        top_k: How many answers to return.

    Returns:
        The answers, with the probability of each.
    """
    batch = classifier.preprocess(image.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        probabilities = classifier.net(batch).softmax(dim=1)[0]
    top = probabilities.topk(min(top_k, len(classifier.labels)))
    return [
        Prediction(classifier.labels[int(index)], float(probability))
        for probability, index in zip(top.values, top.indices, strict=True)
    ]
