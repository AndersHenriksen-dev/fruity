"""What one simulated visitor does: send a food photo, wait a moment, send another. `run.py` starts this with Locust."""

from __future__ import annotations

import os
import random
from pathlib import Path

from locust import HttpUser, between, task

from fruity.lib.loadtest.settings import PHOTOS_VARIABLE

_PHOTOS = [Path(path).read_bytes() for path in os.environ.get(PHOTOS_VARIABLE, "").split(os.pathsep) if path]


class Visitor(HttpUser):
    """Someone using the demo: a person looks at each answer before sending the next photo."""

    wait_time = between(0.5, 1.5)

    @task
    def classify(self) -> None:
        """Send one photo."""
        files = {"file": ("photo.jpg", random.choice(_PHOTOS), "image/jpeg")}
        self.client.post("/image/classification", files=files, name="classify")
