"""Accuracy of any model that turns a batch of images into logits, so PyTorch and ONNX are scored by the same code."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import torch

Predict = Callable[[torch.Tensor], torch.Tensor]


@dataclass(frozen=True)
class Scores:
    """How often a model was right, overall and for each class."""

    images: int
    top1: float
    top5: float
    per_class: list[float]


def score(predict: Predict, batches: Iterable[tuple[torch.Tensor, torch.Tensor]], num_classes: int) -> Scores:
    """Score a model on labelled batches.

    Args:
        predict: Turns a batch of images into logits on the CPU.
        batches: Pairs of images and labels.
        num_classes: How many classes there are.

    Returns:
        How many images were scored, top-1 and top-5 accuracy, and the top-1 accuracy of each class.
    """
    top5_hits = 0
    per_class_hits = torch.zeros(num_classes)
    per_class_seen = torch.zeros(num_classes)
    for images, labels in batches:
        ranked = predict(images).topk(min(5, num_classes), dim=1).indices
        top5_hits += int((ranked == labels.unsqueeze(1)).any(dim=1).sum())
        per_class_hits += torch.bincount(labels[ranked[:, 0] == labels], minlength=num_classes)
        per_class_seen += torch.bincount(labels, minlength=num_classes)
    seen = float(per_class_seen.sum())
    per_class = per_class_hits / per_class_seen.clamp(min=1)
    return Scores(int(seen), float(per_class_hits.sum()) / seen, top5_hits / seen, per_class.tolist())
