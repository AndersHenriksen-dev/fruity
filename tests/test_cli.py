"""The command line."""

from __future__ import annotations

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
