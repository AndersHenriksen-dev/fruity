"""The preprocessing, checked against the torchvision pipeline that produced the numbers in evals/."""

from __future__ import annotations

import numpy as np
import pytest
import torch
from PIL import Image
from torchvision import transforms

from fruity.lib.shared.preprocess import IMAGENET_MEAN, IMAGENET_STD, prepare_image
from fruity.lib.training.data import evaluation_transform

IMAGE_SIZE = 224
TORCHVISION = transforms.Compose(
    [
        transforms.Resize(256),
        transforms.CenterCrop(IMAGE_SIZE),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ],
)


def _random_image(width: int, height: int) -> Image.Image:
    pixels = np.random.default_rng(width * height).integers(0, 255, (height, width, 3), dtype=np.uint8)
    return Image.fromarray(pixels)


@pytest.mark.parametrize(
    ("width", "height"),
    [(512, 512), (512, 384), (384, 512), (512, 341), (333, 512), (257, 256), (101, 77), (1000, 3), (225, 511)],
)
def test_it_gives_exactly_the_same_numbers_as_torchvision(width: int, height: int) -> None:
    image = _random_image(width, height)
    assert np.array_equal(prepare_image(image, IMAGE_SIZE), TORCHVISION(image).numpy())


def test_training_validates_with_the_same_preprocessing() -> None:
    image = _random_image(400, 300)
    transformed = evaluation_transform(IMAGE_SIZE)(image)
    assert isinstance(transformed, torch.Tensor)
    assert np.array_equal(transformed.numpy(), prepare_image(image, IMAGE_SIZE))
