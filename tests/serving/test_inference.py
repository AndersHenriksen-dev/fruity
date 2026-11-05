"""Loading a model and naming the food in an image."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fruity.lib.serving.inference import classify, load_classifier
from tests.serving.conftest import LABELS, MODEL_NAME


def test_the_number_of_classes_comes_from_the_saved_labels(saved_model: tuple[Path, Path]) -> None:
    classifier = load_classifier(MODEL_NAME, *saved_model, image_size=64)
    assert len(classifier.labels) == len(LABELS)


def test_the_model_is_ready_for_inference(saved_model: tuple[Path, Path]) -> None:
    assert not load_classifier(MODEL_NAME, *saved_model, image_size=64).net.training


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
def test_any_color_mode_works(saved_model: tuple[Path, Path], mode: str) -> None:
    classifier = load_classifier(MODEL_NAME, *saved_model, image_size=64)
    assert len(classify(classifier, Image.new(mode, (80, 60)), top_k=2)) == 2


def test_answers_are_probabilities_with_the_most_likely_first(saved_model: tuple[Path, Path]) -> None:
    classifier = load_classifier(MODEL_NAME, *saved_model, image_size=64)
    answers = classify(classifier, Image.new("RGB", (80, 60), "red"), top_k=3)
    probabilities = [answer.probability for answer in answers]
    assert probabilities == sorted(probabilities, reverse=True)
    assert sum(probabilities) == pytest.approx(1.0)
    assert {answer.label for answer in answers} == set(LABELS.values())


def test_asking_for_more_answers_than_classes_is_fine(saved_model: tuple[Path, Path]) -> None:
    classifier = load_classifier(MODEL_NAME, *saved_model, image_size=64)
    assert len(classify(classifier, Image.new("RGB", (80, 60)), top_k=50)) == len(LABELS)
