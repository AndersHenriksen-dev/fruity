"""The load test, with real Locust runs against a small local server that stands in for the service."""

from __future__ import annotations

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from fruity import cli
from fruity.lib.loadtest import run
from fruity.lib.loadtest.run import check_host, read_locust_stats, read_max_replicas


class _Service(BaseHTTPRequestHandler):
    """Answers every upload with a success."""

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"[]")

    def log_message(self, format: str, *args: object) -> None:
        """Stay quiet."""


@pytest.fixture
def service() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Service)
    Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def small_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use one small photo and short stages."""
    images = tmp_path / "images" / "pizza"
    images.mkdir(parents=True)
    (images / "1.jpg").write_bytes(b"photo")
    (tmp_path / "train.json").write_text(json.dumps({"pizza": ["pizza/1"]}), encoding="utf-8")
    overrides = {
        "photos_meta": tmp_path / "train.json",
        "photos_dir": tmp_path / "images",
        "stages": [1, 2],
        "stage_seconds": 2,
        "soak_users": 1,
        "soak_seconds": 2,
        "cold_starts": 2,
        "idle_seconds": 0,
    }
    for name, value in overrides.items():
        monkeypatch.setattr(run.CONFIG, name, value)
    return tmp_path / "results"


def test_it_measures_every_stage_through_the_command_line(
    service: str,
    small_test: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["fruity", "loadtest", "--host", service, "--output", str(small_test)])
    cli.main()
    results = json.loads((small_test / "load_test.json").read_text(encoding="utf-8"))
    assert [stage["users"] for stage in results["stages"]] == [1, 2]
    assert all(stage["requests"] > 0 and stage["failures"] == 0 for stage in results["stages"])
    assert "| 2 |" in (small_test / "LOAD.md").read_text(encoding="utf-8")
    assert (small_test / "load_test.png").stat().st_size > 0


def test_cold_starts_add_to_the_stages_already_measured(service: str, small_test: Path) -> None:
    run.measure_stages(service, small_test, None)
    run.measure_cold_starts(service, small_test)
    results = json.loads((small_test / "load_test.json").read_text(encoding="utf-8"))
    assert len(results["stages"]) == 2
    assert len(results["cold_starts_seconds"]) == 2
    assert "Cold starts" in (small_test / "LOAD.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "host",
    [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "https://fruity-api.nicecoast-1.swedencentral.azurecontainerapps.io",
    ],
)
def test_it_allows_this_projects_own_service(host: str) -> None:
    assert check_host(host, run.CONFIG.allowed_hosts)


def test_a_steady_load_is_saved_beside_the_stages(service: str, small_test: Path) -> None:
    run.measure_stages(service, small_test, None)
    run.measure_soak(service, small_test, None)
    results = json.loads((small_test / "load_test.json").read_text(encoding="utf-8"))
    assert len(results["stages"]) == 2
    assert results["soak"]["requests"] > 0
    assert "Steady load" in (small_test / "LOAD.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "host",
    [
        "https://example.com",
        "https://other-app.nicecoast-1.swedencentral.azurecontainerapps.io",
        "https://fruity-api.azurecontainerapps.io.example.com",
        "not a url",
    ],
)
def test_it_refuses_every_other_host(host: str) -> None:
    with pytest.raises(ValueError, match="will not be load tested"):
        check_host(host, run.CONFIG.allowed_hosts)


def test_a_refused_host_gets_no_requests(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="will not be load tested"):
        run.measure_stages("https://example.com", tmp_path, None)
    assert not (tmp_path / "load_test.json").exists()


def test_it_needs_the_azure_cli_before_a_run_that_reads_replicas(
    service: str,
    small_test: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(run.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="Azure CLI"):
        run.measure_stages(service, small_test, "some/resource")
    assert not small_test.exists()


def test_it_reads_the_totals_from_locust(tmp_path: Path) -> None:
    path = tmp_path / "stats.csv"
    path.write_text(
        "Type,Name,Request Count,Failure Count,Requests/s,50%,95%,99%\n"
        "POST,classify,4,0,1.0,90,100,110\n"
        ",Aggregated,4,1,1.0,90,100,110\n",
        encoding="utf-8",
    )
    assert read_locust_stats(path)["Failure Count"] == 1


def test_a_run_where_no_request_finished_counts_as_zero_and_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "stats.csv"
    path.write_text(
        "Type,Name,Request Count,Failure Count,Requests/s,50%,95%,99%\n,Aggregated,0,0,0.0,N/A,N/A,N/A\n",
        encoding="utf-8",
    )
    assert read_locust_stats(path)["95%"] == 0


def test_it_finds_the_most_replicas_and_allows_for_empty_points() -> None:
    answer = {"value": [{"timeseries": [{"data": [{"maximum": 1.0}, {"maximum": 2.0}, {}]}]}]}
    assert read_max_replicas(answer) == 2.0
    assert read_max_replicas({"value": [{"timeseries": []}]}) is None
