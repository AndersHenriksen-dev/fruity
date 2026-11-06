"""Scoring, on logits small enough to work out by hand."""

from __future__ import annotations

import pytest
import torch

from fruity.lib.evaluation.scoring import score


def test_scores_count_the_top_answers_overall_and_per_class() -> None:
    logits = torch.tensor([[9.0, 1.0, 0.0], [9.0, 1.0, 0.0], [0.0, 9.0, 1.0], [9.0, 1.0, 0.0]])
    labels = torch.tensor([0, 1, 1, 2])
    result = score(lambda _: logits, [(torch.zeros(4), labels)], num_classes=3)
    assert result.top1 == pytest.approx(0.5)
    assert result.top5 == pytest.approx(1.0)
    assert result.per_class == pytest.approx([1.0, 0.5, 0.0])


def test_batches_add_up_to_the_same_score() -> None:
    logits = torch.eye(4)
    labels = torch.tensor([0, 1, 2, 0])
    whole = score(lambda _: logits, [(torch.zeros(4), labels)], num_classes=4)
    split = iter((logits[:2], logits[2:]))
    parts = score(lambda _: next(split), [(torch.zeros(2), labels[:2]), (torch.zeros(2), labels[2:])], num_classes=4)
    assert parts == whole
