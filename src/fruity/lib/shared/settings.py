"""Reading a module's config file, which sits at the same path under config/ as the module sits under lib/.

`lib/serving/api.py` reads `config/serving/api.yaml`. Pydantic checks the file as it is read, so a typo fails loudly
when the module loads. Training is the exception: it composes many files with Hydra, which is built for experiments.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import TypeAdapter

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
_LIB_PREFIX = "fruity.lib."


def config_path(module: str) -> Path:
    """Where a module's config file is: `fruity.lib.serving.api` reads `config/serving/api.yaml`."""
    return CONFIG_DIR.joinpath(*module.removeprefix(_LIB_PREFIX).split(".")).with_suffix(".yaml")


def read_config[T](path: Path, shape: type[T]) -> T:
    """Read one YAML file and check it against a shape, so the rest of the code works with typed objects."""
    with path.open(encoding="utf-8") as file:
        return TypeAdapter(shape).validate_python(yaml.safe_load(file))


def config_for[T](module: str, shape: type[T]) -> T:
    """Read a module's own config file. Pass `__name__`, which keeps the two paths matched."""
    return read_config(config_path(module), shape)
