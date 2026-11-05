"""Food-101: the official train and test split, with a validation set taken from train.

The test set stays untouched until the final numbers, so it cannot influence which model is chosen.
"""

from __future__ import annotations

import torch
from lightning.pytorch import LightningDataModule
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import datasets, transforms

from fruity.lib.shared.preprocess import IMAGENET_MEAN, IMAGENET_STD, evaluation_transform


def training_transform(image_size: int) -> transforms.Compose:
    """Build the random crops and flips used for training, which make the model less sensitive to framing."""
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(image_size),
            transforms.RandomHorizontalFlip(),
            transforms.TrivialAugmentWide(),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ],
    )


def split_indices(size: int, val_fraction: float, seed: int) -> tuple[list[int], list[int]]:
    """Choose which training images go to validation. The same seed always gives the same split."""
    shuffled: list[int] = torch.randperm(size, generator=torch.Generator().manual_seed(seed)).tolist()
    val_size = int(size * val_fraction)
    return shuffled[val_size:], shuffled[:val_size]


class Food101DataModule(LightningDataModule):
    """The data for training, validation and testing."""

    def __init__(
        self,
        data_dir: str,
        image_size: int,
        val_fraction: float,
        split_seed: int,
        batch_size: int,
        num_workers: int,
    ) -> None:
        """Keep the settings. The data loads in `setup`."""
        super().__init__()
        self.data_dir = data_dir
        self.image_size = image_size
        self.val_fraction = val_fraction
        self.split_seed = split_seed
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.data_train: Dataset[tuple[torch.Tensor, int]] | None = None
        self.data_val: Dataset[tuple[torch.Tensor, int]] | None = None
        self.data_test: Dataset[tuple[torch.Tensor, int]] | None = None
        self.classes: list[str] = []

    def prepare_data(self) -> None:
        """Download the data if it is not there yet, which is 5 GB."""
        datasets.Food101(self.data_dir, split="train", download=True)

    def setup(self, stage: str | None = None) -> None:
        """Build the three datasets. Validation uses training images with the evaluation preprocessing."""
        evaluate = evaluation_transform(self.image_size)
        augmented = datasets.Food101(self.data_dir, split="train", transform=training_transform(self.image_size))
        plain = datasets.Food101(self.data_dir, split="train", transform=evaluate)
        train, val = split_indices(len(augmented), self.val_fraction, self.split_seed)
        self.data_train = Subset(augmented, train)
        self.data_val = Subset(plain, val)
        self.data_test = datasets.Food101(self.data_dir, split="test", transform=evaluate)
        self.classes = list(augmented.classes)

    def _loader(self, data: Dataset[tuple[torch.Tensor, int]] | None, shuffle: bool) -> DataLoader:
        """Build a loader for one of the datasets."""
        if data is None:
            raise RuntimeError("Call setup() before asking for a dataloader.")
        return DataLoader(
            data,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            persistent_workers=self.num_workers > 0,
            pin_memory=True,
            shuffle=shuffle,
        )

    def train_dataloader(self) -> DataLoader:
        """Return the shuffled training data."""
        return self._loader(self.data_train, shuffle=True)

    def val_dataloader(self) -> DataLoader:
        """Return the validation data."""
        return self._loader(self.data_val, shuffle=False)

    def test_dataloader(self) -> DataLoader:
        """Return the test data."""
        return self._loader(self.data_test, shuffle=False)
