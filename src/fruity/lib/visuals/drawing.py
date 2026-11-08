"""Drawing helpers shared by the graphics: square photos and text."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def square(image: Image.Image, size: int) -> Image.Image:
    """Crop the center square of a photo and resize it, the way the model sees it."""
    image = image.convert("RGB")
    side = min(image.size)
    left, top = (image.width - side) // 2, (image.height - side) // 2
    return image.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A font that exists on every machine, at a given size."""
    return ImageFont.load_default(size=size)


def label(dish: str) -> str:
    """Write a class name the way a reader would."""
    return dish.replace("_", " ")


def fit(draw: ImageDraw.ImageDraw, text: str, width: int, size: int) -> str:
    """Shorten text with an ellipsis until it fits a width."""
    if draw.textlength(text, font=font(size)) <= width:
        return text
    while text and draw.textlength(text + "...", font=font(size)) > width:
        text = text[:-1]
    return text.rstrip() + "..."
