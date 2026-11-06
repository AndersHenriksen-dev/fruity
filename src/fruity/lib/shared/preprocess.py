"""The fixed preprocessing of an image, shared so that training and serving can never disagree on it.

It needs only Pillow and NumPy, so the serving image can use it without PyTorch.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
_RESIZE_RATIO = 256 / 224


def prepare_image(image: Image.Image, image_size: int) -> np.ndarray:
    """Resize the short side, crop the center and normalize: the input for validation, testing and serving.

    Args:
        image: An RGB image.
        image_size: The side of the square the model takes.

    Returns:
        A float32 array of shape (3, image_size, image_size).
    """
    short = int(image_size * _RESIZE_RATIO)
    width, height = image.size
    resized_size = (short, int(short * height / width)) if width <= height else (int(short * width / height), short)
    resized = image.resize(resized_size, Image.Resampling.BILINEAR)
    left = round((resized.width - image_size) / 2)
    top = round((resized.height - image_size) / 2)
    cropped = resized.crop((left, top, left + image_size, top + image_size))
    pixels = np.asarray(cropped, dtype=np.float32).transpose(2, 0, 1) / 255
    mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(3, 1, 1)
    std = np.array(IMAGENET_STD, dtype=np.float32).reshape(3, 1, 1)
    return (pixels - mean) / std
