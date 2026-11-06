"""The classifier's steps, on a small model with no download."""

from __future__ import annotations

import pytest
import timm
import torch

from fruity.lib.training.model import Classifier, build_schedule


def test_the_rate_rises_to_its_peak_and_falls_towards_zero() -> None:
    parameter = torch.nn.Parameter(torch.zeros(1))
    optimizer = torch.optim.SGD([parameter], lr=1.0)
    schedule = build_schedule(optimizer, total_steps=100, warmup_fraction=0.1)
    rates = []
    for _ in range(100):
        rates.append(schedule.get_last_lr()[0])
        optimizer.step()
        schedule.step()
    assert rates[0] == pytest.approx(0.01)
    assert max(rates) == pytest.approx(1.0)
    assert rates.index(max(rates)) == 10
    assert rates[-1] < 0.01


def _classifier() -> Classifier:
    net = timm.create_model("resnet18", pretrained=False, in_chans=3, num_classes=10)
    return Classifier(net, torch.optim.SGD, num_classes=10, warmup_fraction=0.1)


def test_it_scores_every_class_for_every_image() -> None:
    assert _classifier()(torch.randn(4, 3, 32, 32)).shape == torch.Size([4, 10])


def test_each_stage_returns_one_loss() -> None:
    classifier = _classifier()
    batch = (torch.randn(8, 3, 32, 32), torch.randint(0, 10, (8,)))
    for step in (classifier.training_step, classifier.validation_step, classifier.test_step):
        assert step(batch, 0).shape == torch.Size([])
