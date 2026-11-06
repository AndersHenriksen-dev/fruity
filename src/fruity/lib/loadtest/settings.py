"""What `run.py` tells the Locust process.

A module of its own, because importing Locust patches the whole process's networking, so `run.py` must never import
`locustfile.py`.
"""

from __future__ import annotations

PHOTOS_VARIABLE = "FRUITY_LOADTEST_PHOTOS"
