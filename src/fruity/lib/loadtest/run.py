"""Run the load test against this project's own service, and write the results from what was measured.

Each number of users is a separate Locust run, so each stage has its own clean statistics. Finished results are saved
as they come, so a stopped measurement keeps what it has.
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from fruity.lib.loadtest.report import write_report
from fruity.lib.loadtest.settings import PHOTOS_VARIABLE
from fruity.lib.shared.settings import config_for

_LOCUSTFILE = Path(__file__).with_name("locustfile.py")
_RESULTS_FILE = "load_test.json"
_LOCUST_GRACE_SECONDS = 60
_COLD_START_RETRY_SECONDS = 1


class LoadConfig(BaseModel):
    """Which hosts may be tested, and how hard."""

    allowed_hosts: list[str]
    stages: list[int]
    stage_seconds: int
    soak_users: int
    soak_seconds: int
    photos_meta: Path
    photos_dir: Path
    photos: int
    cold_starts: int
    idle_seconds: int
    cold_start_timeout_seconds: int
    metrics_delay_seconds: int


CONFIG = config_for(__name__, LoadConfig)


class Stage(BaseModel):
    """What one number of users saw."""

    users: int
    seconds: int
    requests: int
    failures: int
    requests_per_second: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    started: str
    finished: str
    max_replicas: float | None = None


class LoadResults(BaseModel):
    """Everything measured about the service under load."""

    target: str
    stages: list[Stage] = []
    soak: Stage | None = None
    cold_starts_seconds: list[float] = []


def check_host(host: str, allowed: list[str]) -> str:
    """Return the host name of a URL if it may be tested.

    Raises:
        ValueError: If the URL is not this project's own service.
    """
    name = urlparse(host).hostname or ""
    if not any(re.fullmatch(pattern, name) for pattern in allowed):
        raise ValueError(f"{name or host} is not this project's service, so it will not be load tested.")
    return name


def _choose_photos() -> list[Path]:
    """Take one training photo from each of the first classes, so no test image is ever used."""
    listed: dict[str, list[str]] = json.loads(CONFIG.photos_meta.read_text(encoding="utf-8"))
    return [CONFIG.photos_dir / f"{names[0]}.jpg" for _, names in sorted(listed.items())[: CONFIG.photos]]


def read_locust_stats(path: Path) -> dict[str, float]:
    """Read the totals from the statistics file Locust writes.

    Raises:
        ValueError: If the file has no totals.
    """
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["Name"] == "Aggregated":
                # Locust writes N/A when no request finished, such as a short run during a cold start.
                return {
                    key: 0.0 if row[key] == "N/A" else float(row[key])
                    for key in ("Request Count", "Failure Count", "Requests/s", "50%", "95%", "99%")
                }
    raise ValueError(f"{path} has no totals.")


def _run_stage(host: str, users: int, seconds: int, photos: list[Path]) -> Stage:
    """Hold a number of users against the service and read what Locust measured."""
    started = datetime.now(UTC)
    with tempfile.TemporaryDirectory() as folder:
        prefix = Path(folder) / "stage"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "locust",
                "-f",
                str(_LOCUSTFILE),
                "--headless",
                "--only-summary",
                "--host",
                host,
                "--users",
                str(users),
                "--spawn-rate",
                str(users),
                "--run-time",
                f"{seconds}s",
                "--csv",
                str(prefix),
            ],
            # Locust exits with 1 when any request failed, and failures are a result here.
            check=False,
            timeout=seconds + _LOCUST_GRACE_SECONDS,
            env={**os.environ, PHOTOS_VARIABLE: os.pathsep.join(str(photo) for photo in photos)},
        )
        stats = read_locust_stats(Path(f"{prefix}_stats.csv"))
    return Stage(
        users=users,
        seconds=seconds,
        requests=int(stats["Request Count"]),
        failures=int(stats["Failure Count"]),
        requests_per_second=stats["Requests/s"],
        p50_ms=stats["50%"],
        p95_ms=stats["95%"],
        p99_ms=stats["99%"],
        started=started.isoformat(),
        finished=datetime.now(UTC).isoformat(),
    )


def read_max_replicas(metrics: dict[str, list[dict[str, list[dict[str, list[dict[str, float]]]]]]]) -> float | None:
    """Find the highest replica count in the answer of `az monitor metrics list`, if it has one."""
    points = [
        point["maximum"]
        for metric in metrics["value"]
        for series in metric["timeseries"]
        for point in series["data"]
        if "maximum" in point
    ]
    return max(points, default=None)


def _add_replica_counts(results: LoadResults, resource_id: str, az: str) -> None:
    """Ask Azure how many replicas ran in each stage. Its metrics arrive some minutes late, so wait for them first."""
    time.sleep(CONFIG.metrics_delay_seconds)
    for stage in [*results.stages, *([results.soak] if results.soak else [])]:
        finished = datetime.fromisoformat(stage.finished) + timedelta(minutes=1)
        answer = subprocess.run(
            [
                az,
                "monitor",
                "metrics",
                "list",
                "--resource",
                resource_id,
                "--metric",
                "Replicas",
                "--aggregation",
                "Maximum",
                "--interval",
                "PT1M",
                "--start-time",
                stage.started,
                "--end-time",
                finished.isoformat(),
                "--output",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        stage.max_replicas = read_max_replicas(json.loads(answer.stdout))


def _time_cold_start(host: str, photo: bytes) -> float:
    """Time one request to a service that has scaled to zero, until it gets an answer.

    Raises:
        TimeoutError: If no answer comes in time.
    """
    started = time.perf_counter()
    while time.perf_counter() - started < CONFIG.cold_start_timeout_seconds:
        try:
            files = {"file": ("photo.jpg", photo, "image/jpeg")}
            response = requests.post(
                f"{host}/image/classification",
                files=files,
                timeout=CONFIG.cold_start_timeout_seconds,
            )
            if response.ok:
                return time.perf_counter() - started
        except requests.RequestException:
            pass
        time.sleep(_COLD_START_RETRY_SECONDS)
    raise TimeoutError(f"{host} gave no answer in {CONFIG.cold_start_timeout_seconds} s.")


def _save(results: LoadResults, output: Path) -> None:
    """Keep what has been measured so far, and write the report from it."""
    output.mkdir(parents=True, exist_ok=True)
    (output / _RESULTS_FILE).write_bytes(results.model_dump_json(indent=2).encode("utf-8"))
    write_report(results, output)


def _load_results(output: Path, target: str) -> LoadResults:
    """Continue the results file for this target, so stages and cold starts can be measured on different runs."""
    path = output / _RESULTS_FILE
    if path.exists():
        saved = LoadResults.model_validate_json(path.read_text(encoding="utf-8"))
        if saved.target == target:
            return saved
    return LoadResults(target=target)


def measure_stages(host: str, output: Path, resource_id: str | None) -> None:
    """Measure every number of users, then add replica counts if the service runs on Azure.

    Args:
        host: The service's URL.
        output: The folder for the results.
        resource_id: The API's Azure resource ID, or None for a service that has no Azure metrics.

    Raises:
        RuntimeError: If replica counts are asked for and the Azure CLI is missing, so that this fails before the run.
    """
    az = shutil.which("az")
    if resource_id and az is None:
        raise RuntimeError("Reading replica counts needs the Azure CLI.")
    target = check_host(host, CONFIG.allowed_hosts)
    results = _load_results(output, target)
    results.stages = []
    photos = _choose_photos()
    for users in CONFIG.stages:
        results.stages.append(_run_stage(host, users, CONFIG.stage_seconds, photos))
        _save(results, output)
        stage = results.stages[-1]
        print(f"{users} users: {stage.p95_ms:.0f} ms p95, {stage.failures} failures", flush=True)
    if resource_id and az:
        _add_replica_counts(results, resource_id, az)
        _save(results, output)


def measure_soak(host: str, output: Path, resource_id: str | None) -> None:
    """Hold a steady load for most of the deployment, so the monitoring has a long, real record to show.

    Args:
        host: The service's URL.
        output: The folder for the results.
        resource_id: The API's Azure resource ID, or None for a service that has no Azure metrics.

    Raises:
        RuntimeError: If replica counts are asked for and the Azure CLI is missing, so that this fails before the run.
    """
    az = shutil.which("az")
    if resource_id and az is None:
        raise RuntimeError("Reading replica counts needs the Azure CLI.")
    target = check_host(host, CONFIG.allowed_hosts)
    results = _load_results(output, target)
    results.soak = _run_stage(host, CONFIG.soak_users, CONFIG.soak_seconds, _choose_photos())
    _save(results, output)
    print(f"{results.soak.requests} requests, {results.soak.failures} failures", flush=True)
    if resource_id and az:
        _add_replica_counts(results, resource_id, az)
        _save(results, output)


def measure_cold_starts(host: str, output: Path) -> None:
    """Let the service scale to zero before each request, and time how long the answer takes."""
    target = check_host(host, CONFIG.allowed_hosts)
    results = _load_results(output, target)
    results.cold_starts_seconds = []
    photo = _choose_photos()[0].read_bytes()
    for number in range(1, CONFIG.cold_starts + 1):
        time.sleep(CONFIG.idle_seconds)
        results.cold_starts_seconds.append(_time_cold_start(host, photo))
        _save(results, output)
        print(f"cold start {number}: {results.cold_starts_seconds[-1]:.1f} s", flush=True)
    print(f"median {statistics.median(results.cold_starts_seconds):.1f} s", flush=True)
