"""Downloading the published model, from local files so that no test needs the network."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from fruity.lib.serving import fetch


@pytest.fixture
def release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Publish one file at a file URL, and point the download at it."""
    published = tmp_path / "release"
    published.mkdir()
    (published / "model.onnx").write_bytes(b"the model")
    monkeypatch.setattr(fetch.CONFIG, "base_url", published.as_uri())
    monkeypatch.setattr(fetch.CONFIG, "target_dir", tmp_path / "models")
    monkeypatch.setattr(fetch.CONFIG, "files", {"model.onnx": hashlib.sha256(b"the model").hexdigest()})
    return tmp_path / "models" / "model.onnx"


def test_it_saves_a_file_with_the_right_checksum(release: Path) -> None:
    fetch.main()
    assert release.read_bytes() == b"the model"


def test_it_refuses_a_file_with_the_wrong_checksum_and_saves_nothing(
    release: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetch.CONFIG, "files", {"model.onnx": "0" * 64})
    with pytest.raises(ValueError, match="SHA-256"):
        fetch.main()
    assert not release.exists()


def test_it_replaces_a_damaged_local_file(release: Path) -> None:
    release.parent.mkdir()
    release.write_bytes(b"damaged")
    fetch.main()
    assert release.read_bytes() == b"the model"


def test_it_keeps_a_correct_local_file_without_downloading(release: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fetch.main()
    monkeypatch.setattr(fetch.CONFIG, "base_url", "file:///does/not/exist")
    fetch.main()
    assert release.read_bytes() == b"the model"
