"""The classifier as a Lightning module: a pretrained timm model with its loss and metrics."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import torch
from lightning.pytorch import LightningModule
from torchmetrics import MeanMetric
from torchmetrics.classification import MulticlassAccuracy

Batch = tuple[torch.Tensor, torch.Tensor]
OptimizerFactory = Callable[[Iterable[torch.nn.Parameter]], torch.optim.Optimizer]


class StageMetrics(torch.nn.Module):
    """The loss and accuracy of one stage: training, validation or testing."""

    def __init__(self, num_classes: int) -> None:
        """Set up the metrics."""
        super().__init__()
        self.loss = MeanMetric()
        self.top1 = MulticlassAccuracy(num_classes, average="micro")
        self.top5 = MulticlassAccuracy(num_classes, top_k=5, average="micro")


class Classifier(LightningModule):
    """Train, validate and test any model that turns images into class scores."""

    def __init__(self, net: torch.nn.Module, optimizer: OptimizerFactory, num_classes: int) -> None:
        """Set up the loss and the metrics.

        Args:
            net: The model to train.
            optimizer: Builds the optimizer from the model's parameters.
            num_classes: How many classes the model separates.
        """
        super().__init__()
        self.save_hyperparameters(logger=True, ignore=["net", "optimizer"])
        self.net = net
        self.optimizer = optimizer
        self.criterion = torch.nn.CrossEntropyLoss()
        self.train_metrics = StageMetrics(num_classes)
        self.val_metrics = StageMetrics(num_classes)
        self.test_metrics = StageMetrics(num_classes)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """Score each class for each image."""
        scores: torch.Tensor = self.net(images)
        return scores

    def _step(self, batch: Batch, stage: str, metrics: StageMetrics) -> torch.Tensor:
        """Run one batch, update the stage's metrics and return the loss."""
        images, targets = batch
        scores = self(images)
        loss: torch.Tensor = self.criterion(scores, targets)
        metrics.loss(loss)
        metrics.top1(scores, targets)
        metrics.top5(scores, targets)
        self.log(f"{stage}/loss", metrics.loss, on_step=False, on_epoch=True)
        self.log(f"{stage}/acc", metrics.top1, on_step=False, on_epoch=True, prog_bar=stage != "train")
        self.log(f"{stage}/top5", metrics.top5, on_step=False, on_epoch=True)
        return loss

    def training_step(self, batch: Batch, batch_idx: int) -> torch.Tensor:
        """Train on one batch."""
        return self._step(batch, "train", self.train_metrics)

    def validation_step(self, batch: Batch, batch_idx: int) -> torch.Tensor:
        """Validate on one batch."""
        return self._step(batch, "val", self.val_metrics)

    def test_step(self, batch: Batch, batch_idx: int) -> torch.Tensor:
        """Test on one batch."""
        return self._step(batch, "test", self.test_metrics)

    def configure_optimizers(self) -> torch.optim.Optimizer:
        """Build the optimizer."""
        return self.optimizer(self.parameters())
