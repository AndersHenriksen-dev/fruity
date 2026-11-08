"""How well food can be named without deep learning, so the model's accuracy has something fair to stand against.

With 101 classes, guessing is right about 1% of the time, not 50%. The classical methods use hand-made features: colour
for the simple one, and colour, shape and texture for the strong one. All of them are scored on the validation images
the models were scored on, so the test set stays closed.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import BaseModel
from skimage.feature import hog, local_binary_pattern
from sklearn.kernel_approximation import AdditiveChi2Sampler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torchvision import datasets

from fruity.lib.evaluation import compare
from fruity.lib.shared.settings import config_for
from fruity.lib.training.data import split_indices


class Published(BaseModel):
    """The best published result without deep learning."""

    name: str
    url: str
    top1: float


class BaselinesConfig(BaseModel):
    """The features, the classifier, and where results go."""

    image_size: int
    color_bins: list[int]
    hog_cell: int
    lbp_points: int
    lbp_radius: int
    lbp_grid: int
    max_iter: int
    chi2_steps: int
    workers: int
    features_dir: Path
    results_path: Path
    report_path: Path
    final_results: Path
    published: Published


CONFIG = config_for(__name__, BaselinesConfig)


class Baseline(BaseModel):
    """One way of naming the food, and how often it was right on validation images."""

    name: str
    top1: float
    top5: float | None
    fit_seconds: float | None


class BaselineResults(BaseModel):
    """Every baseline, and the counts they were measured on."""

    classes: int
    train_images: int
    val_images: int
    baselines: list[Baseline]


def _square(image: Image.Image, size: int) -> Image.Image:
    """Resize the short side and crop the center, the way the models see an image."""
    width, height = image.size
    scale = size / min(width, height)
    resized = image.convert("RGB").resize((max(size, round(width * scale)), max(size, round(height * scale))))
    left, top = (resized.width - size) // 2, (resized.height - size) // 2
    return resized.crop((left, top, left + size, top + size))


def color_features(image: Image.Image) -> np.ndarray:
    """A histogram of hue, saturation and brightness: what colours the food has, not where they are."""
    hsv = np.asarray(image.convert("HSV")).reshape(-1, 3)
    bins = CONFIG.color_bins
    counts, _ = np.histogramdd(hsv, bins=bins, range=[(0, 256)] * 3)
    return np.asarray(counts.ravel() / hsv.shape[0], dtype=np.float32)


def shape_features(gray: np.ndarray) -> np.ndarray:
    """Histograms of edge directions in small cells (HOG): the outlines and layout in the image."""
    cell = CONFIG.hog_cell
    described = hog(gray, pixels_per_cell=(cell, cell), cells_per_block=(2, 2), feature_vector=True)
    return np.asarray(described, dtype=np.float32)


def texture_features(gray: np.ndarray) -> np.ndarray:
    """Histograms of local binary patterns (LBP) in a grid: fine texture, such as crumbs, foam or grain."""
    points = CONFIG.lbp_points
    codes = local_binary_pattern((gray * 255).astype(np.uint8), points, CONFIG.lbp_radius, method="uniform")
    grid = CONFIG.lbp_grid
    height, width = codes.shape
    histograms = []
    for row in range(grid):
        for column in range(grid):
            block = codes[
                row * height // grid : (row + 1) * height // grid,
                column * width // grid : (column + 1) * width // grid,
            ]
            counts, _ = np.histogram(block, bins=points + 2, range=(0, points + 2))
            histograms.append(counts / block.size)
    return np.concatenate(histograms).astype(np.float32)


def all_features(image: Image.Image) -> np.ndarray:
    """Colour first, then shape, then texture. The simple baseline uses the colour part alone."""
    square = _square(image, CONFIG.image_size)
    gray = np.asarray(square.convert("L"), dtype=np.float32) / 255
    return np.concatenate([color_features(square), shape_features(gray), texture_features(gray)])


_DATASET: datasets.Food101 | None = None


def _open(data_dir: str) -> None:
    """Open the dataset once in each worker process."""
    global _DATASET
    _DATASET = datasets.Food101(data_dir, split="train")


def _features_of(index: int) -> tuple[np.ndarray, int]:
    """Read one image by index and describe it."""
    assert _DATASET is not None
    image, label = _DATASET[index]
    return all_features(image), label


def _extract(data_dir: str, indices: list[int], path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Describe every image once and keep the result, because extracting takes minutes and fitting needs it often."""
    if path.exists():
        saved = np.load(path)
        return saved["features"], saved["labels"]
    if CONFIG.workers <= 1:
        _open(data_dir)
        pairs = [_features_of(index) for index in indices]
    else:
        with Pool(CONFIG.workers, initializer=_open, initargs=(data_dir,)) as pool:
            pairs = pool.map(_features_of, indices, chunksize=64)
    features = np.stack([pair[0] for pair in pairs])
    labels = np.array([pair[1] for pair in pairs])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, features=features, labels=labels)
    return features, labels


def _fit_and_score(
    name: str,
    train: tuple[np.ndarray, np.ndarray],
    val: tuple[np.ndarray, np.ndarray],
    chi2_kernel: bool = False,
) -> Baseline:
    """Fit a logistic regression on standardized features and score it like the models: top-1 and top-5.

    Args:
        name: What the report calls it.
        train: Features and labels to fit on.
        val: Features and labels to score on.
        chi2_kernel: First map the features so that a linear model compares histograms with a chi-squared kernel,
            the usual way to compare histograms before deep learning.
    """
    started = time.perf_counter()
    steps = [AdditiveChi2Sampler(sample_steps=CONFIG.chi2_steps)] if chi2_kernel else []
    model = make_pipeline(*steps, StandardScaler(), LogisticRegression(max_iter=CONFIG.max_iter))
    model.fit(*train)
    seconds = time.perf_counter() - started
    probabilities = model.predict_proba(val[0])
    classes = model.classes_
    ranked = classes[np.argsort(-probabilities, axis=1)]
    top1 = float(np.mean(ranked[:, 0] == val[1]))
    top5 = float(np.mean((ranked[:, :5] == val[1][:, None]).any(axis=1)))
    return Baseline(name=name, top1=top1, top5=top5, fit_seconds=seconds)


def _color_columns() -> int:
    """How many of the feature columns are the colour histogram."""
    return int(np.prod(CONFIG.color_bins))


def measure() -> BaselineResults:
    """Describe the images, then score every baseline on the validation images."""
    datamodule = compare.load_datamodule()
    raw = datasets.Food101(datamodule.data_dir, split="train")
    train_indices, val_indices = split_indices(len(raw), datamodule.val_fraction, datamodule.split_seed)
    folder = CONFIG.features_dir
    train = _extract(datamodule.data_dir, train_indices, folder / "train.npz")
    val = _extract(datamodule.data_dir, val_indices, folder / "val.npz")
    classes = len(raw.classes)

    most_common, _ = Counter(train[1].tolist()).most_common(1)[0]
    colours = _color_columns()
    baselines = [
        Baseline(name="Guessing", top1=1 / classes, top5=5 / classes, fit_seconds=None),
        Baseline(
            name="Always the most common class",
            top1=float(np.mean(val[1] == most_common)),
            top5=None,
            fit_seconds=None,
        ),
        _fit_and_score(
            "Colour histogram, logistic regression",
            (train[0][:, :colours], train[1]),
            (val[0][:, :colours], val[1]),
        ),
        _fit_and_score("Colour, shape and texture, logistic regression", train, val),
        _fit_and_score("Colour, shape and texture, chi-squared kernel", train, val, chi2_kernel=True),
    ]
    return BaselineResults(
        classes=classes,
        train_images=len(train_indices),
        val_images=len(val_indices),
        baselines=baselines,
    )


def write_report(results: BaselineResults, path: Path) -> None:
    """Write the comparison: the baselines, the published best without deep learning, and this repo's model."""
    final = json.loads(CONFIG.final_results.read_text(encoding="utf-8"))
    rows = [
        "| Method | Data | Top-1 | Top-5 |",
        "|---|---|---:|---:|",
    ]
    for baseline in results.baselines:
        top5 = "" if baseline.top5 is None else f"{baseline.top5:.2%}"
        rows.append(f"| {baseline.name} | Validation | {baseline.top1:.2%} | {top5} |")
    published = CONFIG.published
    rows.append(f"| [{published.name}]({published.url}) | Test, published | {published.top1:.2%} | |")
    model = final["model"]
    for data, key in (("Validation", "validation"), ("Test", "test")):
        rows.append(f"| **`{model}`, this repo** | {data} | **{final[key]['top1']:.2%}** | {final[key]['top5']:.2%} |")
    lines = [
        "# Baselines",
        "",
        "Generated by `fruity baselines` from `evals/baselines.json` and `evals/final.json`. Do not edit by hand.",
        "",
        f"How often each method names the food right, out of {results.classes} classes. "
        f"The methods here were fitted on {results.train_images:,} training images and scored on the same "
        f"{results.val_images:,} validation images as the models. The test set was not used for them.",
        "",
        *rows,
        "",
        "## What each method is",
        "",
        "- **Guessing:** a random answer. With 101 classes, that is right about 1% of the time, and 5% for top-5.",
        "- **Always the most common class:** the class with the most training images. It can score below guessing, "
        "because the largest class in training need not be the largest in validation.",
        "- **Colour histogram:** how much of each colour the image has, ignoring where. Logistic regression then "
        "learns which colours go with which food.",
        f"- **Colour, shape and texture:** the colour histogram, plus edge directions (HOG) and fine texture (LBP), on "
        f"{CONFIG.image_size} by {CONFIG.image_size} pixel images. These are the kind of hand-made features image "
        "classification used before deep learning.",
        "- **Chi-squared kernel:** the same features, mapped so that a linear model compares histograms the way a "
        "chi-squared kernel does, which suits histograms better than comparing raw numbers. It has one fixed setting "
        "and was not tuned on these images.",
        "- **Random forests on mined image parts:** the best result without deep learning that the dataset's authors "
        "published. It is on the test set, so it compares with this repo's test score, not its validation score.",
        "",
        "## Limits",
        "",
        "- The classical methods here use one simple classifier with default settings. More tuning, or a stronger "
        "classifier such as a kernel SVM, could score higher. The published result shows what a stronger method reached.",
        "- The published number is from a different implementation and was measured on the test set.",
        "",
    ]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def main() -> None:
    """Measure the baselines unless they are saved, then write the report."""
    if CONFIG.results_path.exists():
        results = BaselineResults.model_validate_json(CONFIG.results_path.read_text(encoding="utf-8"))
    else:
        results = measure()
        CONFIG.results_path.write_bytes(results.model_dump_json(indent=2).encode("utf-8"))
    write_report(results, CONFIG.report_path)
    for baseline in results.baselines:
        print(f"{baseline.name}: {baseline.top1:.2%}", flush=True)
