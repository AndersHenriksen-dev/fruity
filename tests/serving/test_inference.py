"""Loading the model and naming the food in an image."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from fruity.lib.evaluation.onnx_model import OnnxModel
from fruity.lib.serving.inference import Classifier, classify, load_classifier
from fruity.lib.shared.preprocess import prepare_image
from tests.serving.conftest import IMAGE_SIZE, LABELS


@pytest.fixture
def classifier(saved_model: tuple[Path, Path]) -> Classifier:
    return load_classifier(*saved_model, image_size=IMAGE_SIZE, threads=1)


def test_serving_never_loads_pytorch() -> None:
    code = "import sys, fruity.lib.serving.api; sys.exit('torch' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_the_number_of_classes_comes_from_the_saved_labels(classifier: Classifier) -> None:
    assert len(classifier.labels) == len(LABELS)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
def test_any_color_mode_works(classifier: Classifier, mode: str) -> None:
    assert len(classify(classifier, Image.new(mode, (80, 60)), top_k=2)) == 2


def test_answers_are_probabilities_with_the_most_likely_first(classifier: Classifier) -> None:
    answers = classify(classifier, Image.new("RGB", (80, 60), "red"), top_k=3)
    probabilities = [answer.probability for answer in answers]
    assert probabilities == sorted(probabilities, reverse=True)
    assert sum(probabilities) == pytest.approx(1.0)
    assert {answer.label for answer in answers} == set(LABELS.values())


def test_asking_for_more_answers_than_classes_is_fine(classifier: Classifier) -> None:
    assert len(classify(classifier, Image.new("RGB", (80, 60)), top_k=50)) == len(LABELS)


def test_it_gives_the_same_probabilities_as_the_model_that_was_measured(
    classifier: Classifier,
    saved_model: tuple[Path, Path],
) -> None:
    pixels = np.random.default_rng(0).integers(0, 255, (90, 120, 3), dtype=np.uint8)
    image = Image.fromarray(pixels)
    batch = torch.from_numpy(prepare_image(image, IMAGE_SIZE)).unsqueeze(0)
    measured = OnnxModel(saved_model[0])(batch).softmax(dim=1)[0]
    for answer in classify(classifier, image, top_k=3):
        index = int(next(key for key, label in LABELS.items() if label == answer.label))
        assert answer.probability == pytest.approx(float(measured[index]), abs=1e-5)
