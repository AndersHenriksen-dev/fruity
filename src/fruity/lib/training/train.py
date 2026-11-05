"""Training the classifier: everything it uses is composed from config by Hydra."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

import hydra
import torch
from lightning.pytorch import Callback, Trainer, seed_everything
from lightning.pytorch.callbacks import ModelCheckpoint
from omegaconf import DictConfig, OmegaConf

from fruity.lib.training.data import Food101DataModule
from fruity.lib.training.model import Classifier


def instantiate_callbacks(config: DictConfig | None) -> list[Callback]:
    """Build the callbacks named in the config."""
    if not config:
        return []
    return [
        hydra.utils.instantiate(callback)
        for callback in config.values()
        if isinstance(callback, DictConfig) and "_target_" in callback
    ]


def build_logger(config: DictConfig) -> object:
    """Log to Weights & Biases if the config asks for it, and otherwise not at all."""
    if not config.logging.run:
        return False
    from lightning.pytorch.loggers import WandbLogger

    logger = WandbLogger(entity=config.logging.entity, project=config.logging.project, tags=list(config.tags))
    logger.experiment.config.update(OmegaConf.to_container(config, resolve=True))
    return logger


def save_for_serving(checkpoint_path: str, classes: list[str], folder: Path) -> None:
    """Save the weights alone with their labels, which is all that serving needs."""
    folder.mkdir(parents=True, exist_ok=True)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    weights = {
        key.removeprefix("net."): value for key, value in checkpoint["state_dict"].items() if key.startswith("net.")
    }
    torch.save(weights, folder / "model.pth")
    (folder / "labels.json").write_text(json.dumps(dict(enumerate(classes)), indent=2), encoding="utf-8")


def train(config: DictConfig) -> dict[str, float]:
    """Train a model, save its best weights and evaluate them on the test set if the config says so.

    Args:
        config: The configuration composed by Hydra.

    Returns:
        The final metrics.
    """
    seed_everything(config.seed, workers=True)
    datamodule: Food101DataModule = hydra.utils.instantiate(config.datamodule)
    model: Classifier = hydra.utils.instantiate(config.model)
    trainer: Trainer = hydra.utils.instantiate(
        config.trainer,
        callbacks=instantiate_callbacks(config.get("callbacks")),
        logger=build_logger(config),
    )
    started = time.perf_counter()
    trainer.fit(model=model, datamodule=datamodule, ckpt_path=config.get("ckpt_path"))
    fit_seconds = time.perf_counter() - started
    best = cast(ModelCheckpoint, trainer.checkpoint_callback).best_model_path
    output = Path(config.paths.output_dir)
    save_for_serving(best, datamodule.classes, output / "serving")
    if config.get("test"):
        trainer.test(model=model, datamodule=datamodule, ckpt_path=best)
    metrics = {name: float(value) for name, value in trainer.callback_metrics.items()}
    summary = {
        "model": config.model.net.model_name,
        "epochs": trainer.current_epoch,
        "fit_seconds": fit_seconds,
        **metrics,
    }
    (output / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return metrics


@hydra.main(version_base="1.3", config_path="../../config/training", config_name="train.yaml")
def main(config: DictConfig) -> None:
    """Train from the command line."""
    train(config)


if __name__ == "__main__":
    main()
