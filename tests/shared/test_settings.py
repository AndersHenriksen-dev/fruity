"""Finding and checking config files."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from fruity.lib.shared import settings


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: int


def _use_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    (tmp_path / "serving").mkdir()
    (tmp_path / "serving" / "api.yaml").write_text(text, encoding="utf-8")


def test_a_module_finds_its_file_at_the_same_path() -> None:
    assert settings.config_path("fruity.lib.serving.api") == settings.CONFIG_DIR / "serving" / "api.yaml"


def test_a_good_file_loads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_config_dir(monkeypatch, tmp_path, "size: 3\n")
    assert settings.config_for("fruity.lib.serving.api", Shape).size == 3


@pytest.mark.parametrize("text", ["size: big\n", "size: 3\nsizes: 4\n"], ids=["wrong-type", "misspelled-key"])
def test_a_bad_file_fails_loudly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    _use_config_dir(monkeypatch, tmp_path, text)
    with pytest.raises(ValidationError):
        settings.config_for("fruity.lib.serving.api", Shape)


@pytest.mark.parametrize("path", sorted(p for p in settings.CONFIG_DIR.rglob("*.yaml") if "training" not in p.parts))
def test_every_config_file_has_a_python_file(path: Path) -> None:
    relative = path.relative_to(settings.CONFIG_DIR).with_suffix(".py")
    assert (settings.CONFIG_DIR.parent / "lib" / relative).exists()
