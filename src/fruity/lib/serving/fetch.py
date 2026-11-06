"""Download the published model and refuse any file whose checksum differs from the one measured."""

from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from fruity.lib.shared.settings import config_for


class FetchConfig(BaseModel):
    """Where the release is, and what its files must hash to."""

    model_config = ConfigDict(extra="forbid")

    base_url: str
    target_dir: Path
    timeout_seconds: int
    files: dict[str, str]


CONFIG = config_for(__name__, FetchConfig)


def _download(url: str, expected_sha256: str, target: Path) -> None:
    """Save one file, keeping it only if its checksum matches.

    Raises:
        ValueError: If the checksum differs. Nothing is left at `target`.
    """
    with urllib.request.urlopen(url, timeout=CONFIG.timeout_seconds) as response:  # the URL comes from config
        content = response.read()
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"{url} has SHA-256 {actual}, expected {expected_sha256}.")
    target.write_bytes(content)


def main() -> None:
    """Download every file of the release that is not already there with the right checksum."""
    CONFIG.target_dir.mkdir(parents=True, exist_ok=True)
    for name, expected_sha256 in CONFIG.files.items():
        target = CONFIG.target_dir / name
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected_sha256:
            print(f"{target} is already correct.", flush=True)
            continue
        target.unlink(missing_ok=True)
        _download(f"{CONFIG.base_url}/{name}", expected_sha256, target)
        print(f"{target} downloaded and verified.", flush=True)
