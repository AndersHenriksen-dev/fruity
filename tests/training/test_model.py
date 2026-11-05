"""The classifier's steps, on a small model with no download."""

from __future__ import annotations

import timm
import torch

from fruity.lib.training.model import Classifier


def _classifier() -> Classifier:
    net = timm.create_model("resnet18", pretrained=False, in_chans=3, num_classes=10)
    return Classifier(net, torch.optim.SGD, num_classes=10)


def test_it_scores_every_class_for_every_image() -> None:
    assert _classifier()(torch.randn(4, 3, 32, 32)).shape == torch.Size([4, 10])


def test_each_stage_returns_one_loss() -> None:
    classifier = _classifier()
    batch = (torch.randn(8, 3, 32, 32), torch.randint(0, 10, (8,)))
    for step in (classifier.training_step, classifier.validation_step, classifier.test_step):
        assert step(batch, 0).shape == torch.Size([])
