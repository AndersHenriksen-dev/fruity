"""The training config composes, and an experiment really overrides it."""

from __future__ import annotations

import hydra
from omegaconf import DictConfig

from fruity.lib.shared.settings import CONFIG_DIR


def _compose(*overrides: str) -> DictConfig:
    with hydra.initialize_config_dir(str(CONFIG_DIR / "training"), version_base="1.3"):
        return hydra.compose("train.yaml", overrides=list(overrides))


def test_the_default_config_composes() -> None:
    config = _compose()
    assert config.model.net.num_classes == 101
    assert config.datamodule.image_size == 224


def test_an_experiment_overrides_the_model() -> None:
    assert _compose("experiment=convnext").model.net.model_name == "convnext_large"
