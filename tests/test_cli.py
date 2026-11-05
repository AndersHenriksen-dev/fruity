"""The command line."""

from __future__ import annotations

from pathlib import Path

import pytest

from fruity import cli


def test_it_needs_a_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["fruity"])
    with pytest.raises(SystemExit):
        cli.main()


def test_serve_hands_over_to_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, int]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, host, port: calls.append((app, host, port)))
    monkeypatch.setattr("sys.argv", ["fruity", "serve", "--port", "9000"])
    cli.main()
    assert calls == [("fruity.lib.serving.api:app", "127.0.0.1", 9000)]


def test_train_composes_the_real_config_with_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[str] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("fruity.lib.training.train.train", lambda config: seen.append(config.model.net.model_name))
    monkeypatch.setattr("sys.argv", ["fruity", "train", "experiment=convnext"])
    cli.main()
    assert seen == ["convnext_large"]
