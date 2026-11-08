"""The cloud report, from saved files and from a stand-in for the Azure CLI."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from fruity import cli
from fruity.lib.loadtest import cloud

STEADY = {"started": "2026-11-06T12:10:00+00:00", "finished": "2026-11-06T13:10:00+00:00"}


def _stage(started: str, finished: str) -> dict[str, object]:
    return {
        "users": 10,
        "seconds": 3600,
        "requests": 100,
        "failures": 0,
        "requests_per_second": 1.0,
        "p50_ms": 1.0,
        "p95_ms": 2.0,
        "p99_ms": 3.0,
        "started": started,
        "finished": finished,
    }


def _series(values: list[float]) -> list[dict[str, object]]:
    return [{"time": f"2026-11-06T{12 + minutes // 60:02d}:{minutes % 60:02d}:00Z", "value": value}
            for minutes, value in zip(range(0, 5 * len(values), 5), values, strict=True)]  # fmt: skip


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    """Saved files for a one-hour steady load on two replicas, with flat memory."""
    count = 16
    metrics = {name: _series([1.0] * count) for name in cloud.CONFIG.metrics}
    metrics["Replicas"] = _series([1.0] * 2 + [2.0] * 12 + [1.0] * 2)
    metrics["MemoryPercentage"] = _series([40.0] * count)
    metrics["RestartCount"] = _series([0.0] * count)
    saved = {"read_at": "2026-11-06T13:30:00Z", "interval": "PT5M", "apps": {"fruity-api": metrics}}
    (tmp_path / "azure_metrics.json").write_text(json.dumps(saved), encoding="utf-8")
    alert = {
        "name": "fruity-api-slow-answers",
        "severity": "Sev2",
        "condition": "Resolved",
        "started": "2026-11-06T12:20:00Z",
        "resolved": "2026-11-06T12:30:00Z",
    }
    (tmp_path / "azure_alerts.json").write_text(json.dumps([alert]), encoding="utf-8")
    load = {"target": "localhost", "stages": [], "soak": _stage(**STEADY), "cold_starts_seconds": []}
    (tmp_path / "load_test.json").write_text(json.dumps(load), encoding="utf-8")
    return tmp_path


def test_the_report_comes_from_the_saved_files(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud.CONFIG, "apps", ["fruity-api"])
    monkeypatch.setattr(cloud.CONFIG, "sizes", {"fruity-api": cloud.AppSize(vcpu=0.5, memory_gib=1.0)})
    monkeypatch.setattr("sys.argv", ["fruity", "cloud-report", "--folder", str(folder)])
    cli.main()
    report = (folder / "CLOUD.md").read_text(encoding="utf-8")
    assert "16 requests to the API. Replica restarts recorded: 0." in report
    assert "2 replicas in 12 of 13 steps" in report
    assert "40% of the limit in the first hour and 40% in the last" in report
    assert "| `fruity-api-slow-answers` | Sev2 | 2026-11-06 12:20 | 2026-11-06 12:30 |" in report
    assert "| vCPU-seconds | 4,200 | 180,000 | 2% |" in report
    assert (folder / "cloud_metrics.png").stat().st_size > 0


def test_fetch_keeps_the_values_and_drops_every_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = "00000000-0000-0000-0000-000000000000"

    def azure(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[1:3] == ["account", "show"]:
            answer: object = {"id": subscription}
        elif command[1] == "rest":
            essentials = {"severity": "Sev2", "monitorCondition": "Fired", "startDateTime": "2026-11-06T12:20:00Z"}
            answer = {
                "value": [
                    {
                        "name": "slow",
                        "id": f"/subscriptions/{subscription}/x",
                        "properties": {"essentials": essentials},
                    },
                ],
            }
        else:
            aggregation = command[command.index("--aggregation") + 1].lower()
            data = [{"timeStamp": "2026-11-06T12:00:00Z", aggregation: 3.0}, {"timeStamp": "2026-11-06T12:05:00Z"}]
            answer = {"value": [{"id": f"/subscriptions/{subscription}/y", "timeseries": [{"data": data}]}]}
        return subprocess.CompletedProcess(command, 0, json.dumps(answer), "")

    monkeypatch.setattr(cloud.shutil, "which", lambda _: "az")
    monkeypatch.setattr(cloud.subprocess, "run", azure)
    cloud.fetch(tmp_path)
    saved = (tmp_path / "azure_metrics.json").read_text(encoding="utf-8")
    assert subscription not in saved + (tmp_path / "azure_alerts.json").read_text(encoding="utf-8")
    assert json.loads(saved)["apps"]["fruity-api"]["Requests"] == [{"time": "2026-11-06T12:00:00Z", "value": 3.0}]


def test_fetch_needs_the_azure_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cloud.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Azure CLI"):
        cloud.fetch(tmp_path)
