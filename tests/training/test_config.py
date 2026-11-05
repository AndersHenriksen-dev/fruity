"""The training config composes, and an experiment really overrides it."""

from __future__ import annotations

import hydra
import pytest
from omegaconf import DictConfig

from fruity.lib.shared.settings import CONFIG_DIR


def _compose(*overrides: str) -> DictConfig:
    with hydra.initialize_config_dir(str(CONFIG_DIR / "training"), version_base="1.3"):
        return hydra.compose("train.yaml", overrides=list(overrides))


def test_the_default_config_composes() -> None:
    config = _compose()
    assert config.model.net.num_classes == 101
    assert config.datamodule.image_size == 224


@pytest.mark.parametrize(
    ("experiment", "model"),
    [
        ("mobilenet", "mobilenetv3_large_100"),
        ("efficientnet", "efficientnet_b0"),
        ("convnext_tiny", "convnext_tiny"),
        ("convnext_large", "convnext_large"),
    ],
)
def test_an_experiment_overrides_the_model(experiment: str, model: str) -> None:
    assert _compose(f"experiment={experiment}").model.net.model_name == model
