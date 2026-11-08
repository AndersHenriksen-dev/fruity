"""Save what Azure measured while the service ran, and write a report and chart from it.

Azure stops showing a container app's metrics once the app is deleted, so they are saved while it runs, with no IDs
in them, and the report is written from the saved copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from pydantic import BaseModel

from fruity.lib.loadtest.run import LoadResults
from fruity.lib.shared.palette import ACCENT, BACKGROUND, BORDER, MUTED, TEXT
from fruity.lib.shared.settings import config_for


class AppSize(BaseModel):
    """What one replica of an app is given, as set in infra/main.tf."""

    vcpu: float
    memory_gib: float


class FreeGrant(BaseModel):
    """What Azure gives each subscription free every month."""

    vcpu_seconds: float
    gib_seconds: float
    requests: float


class CloudConfig(BaseModel):
    """Which metrics to save, and where the results go."""

    resource_group: str
    apps: list[str]
    chart_app: str
    window_start: str
    interval: str
    metrics: dict[str, str]
    metrics_file: str
    alerts_file: str
    load_file: str
    report_file: str
    chart_file: str
    sizes: dict[str, AppSize]
    free_grant: FreeGrant


CONFIG = config_for(__name__, CloudConfig)
_PANELS = (
    ("Requests per minute", "Requests"),
    ("Average response time (ms)", "ResponseTime"),
    ("Replicas", "Replicas"),
    ("Memory used (% of limit)", "MemoryPercentage"),
)


class Point(BaseModel):
    """One value of a metric."""

    time: datetime
    value: float


class SavedMetrics(BaseModel):
    """Every saved metric, by app and name."""

    read_at: datetime
    interval: str
    apps: dict[str, dict[str, list[Point]]]


class Alert(BaseModel):
    """One time an alert fired."""

    name: str
    severity: str
    condition: str
    started: datetime
    resolved: datetime | None


def _azure(az: str, *args: str) -> object:
    """Run the Azure CLI and read its JSON answer."""
    answer = subprocess.run([az, *args, "-o", "json", "--only-show-errors"], check=True, capture_output=True, text=True)
    return json.loads(answer.stdout)


def _points(answer: dict[str, list[dict[str, list[dict[str, list[dict[str, object]]]]]]], key: str) -> list[Point]:
    """Keep the values from an answer of `az monitor metrics list`, without the IDs it carries."""
    return [
        Point(time=point["timeStamp"], value=point[key])  # type: ignore[arg-type]
        for line in answer["value"][0]["timeseries"]
        for point in line["data"]
        if point.get(key) is not None
    ]


def fetch(output: Path) -> None:
    """Save the apps' metrics and the alerts that fired. Run it while the apps exist.

    Raises:
        RuntimeError: If the Azure CLI is missing.
    """
    az = shutil.which("az")
    if az is None:
        raise RuntimeError("Saving metrics needs the Azure CLI.")
    subscription = _azure(az, "account", "show")["id"]  # type: ignore[index]
    now = datetime.now(UTC)
    apps: dict[str, dict[str, list[Point]]] = {}
    group = f"/subscriptions/{subscription}/resourceGroups/{CONFIG.resource_group}"
    for app in CONFIG.apps:
        resource = f"{group}/providers/Microsoft.App/containerApps/{app}"
        apps[app] = {}
        for metric, aggregation in CONFIG.metrics.items():
            answer = _azure(
                az, "monitor", "metrics", "list", "--resource", resource, "--metric", metric,
                "--aggregation", aggregation, "--interval", CONFIG.interval,
                "--start-time", CONFIG.window_start, "--end-time", now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )  # fmt: skip
            apps[app][metric] = _points(answer, aggregation.lower())  # type: ignore[arg-type]
    saved = SavedMetrics(read_at=now, interval=CONFIG.interval, apps=apps)
    output.mkdir(parents=True, exist_ok=True)
    (output / CONFIG.metrics_file).write_bytes(saved.model_dump_json(indent=1).encode("utf-8"))
    url = f"/subscriptions/{subscription}/providers/Microsoft.AlertsManagement/alerts?api-version=2019-03-01"
    fired = _azure(az, "rest", "--method", "get", "--url", url)["value"]  # type: ignore[index]
    alerts = [
        Alert(
            name=alert["name"],
            severity=alert["properties"]["essentials"]["severity"],
            condition=alert["properties"]["essentials"]["monitorCondition"],
            started=alert["properties"]["essentials"]["startDateTime"],
            resolved=alert["properties"]["essentials"].get("monitorConditionResolvedDateTime"),
        )
        for alert in fired
    ]
    payload = [alert.model_dump(mode="json") for alert in alerts]
    (output / CONFIG.alerts_file).write_bytes(json.dumps(payload, indent=1).encode("utf-8"))


def _between(points: list[Point], start: datetime, end: datetime) -> list[float]:
    """The values measured from start to end."""
    return [point.value for point in points if start <= point.time <= end]


def _draw_chart(series: dict[str, list[Point]], load: LoadResults, minutes_per_point: float, path: Path) -> None:
    """Draw each metric in its own panel over the whole deployment, with the steady load shaded."""
    figure, axes = plt.subplots(len(_PANELS), 1, figsize=(10, 9), dpi=200, sharex=True, facecolor=BACKGROUND)
    for axis, (title, metric) in zip(axes, _PANELS, strict=True):
        points = series[metric]
        values = [point.value / minutes_per_point if metric == "Requests" else point.value for point in points]
        axis.set_facecolor(BACKGROUND)
        if load.soak is not None:
            axis.axvspan(
                datetime.fromisoformat(load.soak.started),
                datetime.fromisoformat(load.soak.finished),
                color=BORDER,
                alpha=0.35,
                linewidth=0,
            )
        axis.plot([point.time for point in points], values, color=ACCENT, linewidth=1.5)
        axis.set_title(title, color=TEXT, loc="left", fontsize=10)
        axis.set_ylim(bottom=0)
        if metric == "Replicas":
            axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        axis.tick_params(colors=MUTED, labelsize=8)
        axis.grid(color=BORDER, linewidth=0.5, alpha=0.5)
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axis.spines[side].set_color(BORDER)
    axes[-1].set_xlabel("Time (UTC). The shaded span is the steady load.", color=MUTED)
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, facecolor=BACKGROUND)
    plt.close(figure)


def _alert_rows(alerts: list[Alert]) -> list[str]:
    """One row per time an alert fired, oldest first."""
    rows = ["| Alert | Severity | Fired (UTC) | Resolved (UTC) |", "|---|---|---|---|"]
    for alert in sorted(alerts, key=lambda alert: alert.started):
        resolved = alert.resolved.strftime("%Y-%m-%d %H:%M") if alert.resolved else "not resolved"
        rows.append(f"| `{alert.name}` | {alert.severity} | {alert.started:%Y-%m-%d %H:%M} | {resolved} |")
    return rows


def _usage_lines(saved: SavedMetrics) -> list[str]:
    """Estimate what the apps used against the free grant, from replica counts and each replica's size.

    Each step counts the most replicas seen in its 5 minutes, so this is an upper estimate.
    """
    step_seconds = 300
    vcpu = gib = requests = 0.0
    for app, size in CONFIG.sizes.items():
        replica_seconds = sum(point.value for point in saved.apps[app]["Replicas"]) * step_seconds
        vcpu += replica_seconds * size.vcpu
        gib += replica_seconds * size.memory_gib
        requests += sum(point.value for point in saved.apps[app]["Requests"])
    grant = CONFIG.free_grant
    return [
        "## Use against the free grant",
        "",
        "| What | Used | Free each month | Share |",
        "|---|---:|---:|---:|",
        f"| vCPU-seconds | {vcpu:,.0f} | {grant.vcpu_seconds:,.0f} | {vcpu / grant.vcpu_seconds:.0%} |",
        f"| GiB-seconds | {gib:,.0f} | {grant.gib_seconds:,.0f} | {gib / grant.gib_seconds:.0%} |",
        f"| Requests | {requests:,.0f} | {grant.requests:,.0f} | {requests / grant.requests:.0%} |",
        "",
        "Worked out from the most replicas seen in each 5-minute step and each replica's size, so it is an upper "
        "estimate. It is not a bill: Azure's own figures are what count.",
        "",
    ]


def write_report(folder: Path) -> None:
    """Write the cloud report and chart from the files saved in a folder."""
    saved = SavedMetrics.model_validate_json((folder / CONFIG.metrics_file).read_text(encoding="utf-8"))
    alerts = [
        Alert.model_validate(entry) for entry in json.loads((folder / CONFIG.alerts_file).read_text(encoding="utf-8"))
    ]
    load = LoadResults.model_validate_json((folder / CONFIG.load_file).read_text(encoding="utf-8"))
    series = saved.apps[CONFIG.chart_app]
    minutes_per_point = 5.0
    _draw_chart(series, load, minutes_per_point, folder / CONFIG.chart_file)

    replicas = series["Replicas"]
    restarts = max(point.value for app in saved.apps.values() for point in app["RestartCount"])
    lines = [
        "# The service on Azure",
        "",
        f"Generated by `fruity cloud-report` from `{CONFIG.metrics_file}` and `{CONFIG.alerts_file}`, which were saved "
        "from Azure while the service ran. Do not edit by hand.",
        "",
        f"From {replicas[0].time:%Y-%m-%d %H:%M} to {replicas[-1].time:%Y-%m-%d %H:%M} UTC, in "
        f"{len(replicas)} steps of 5 minutes, Azure counted "
        f"{sum(point.value for point in series['Requests']):,.0f} requests to the API. "
        f"Replica restarts recorded: {restarts:.0f}.",
        "",
        f"![Requests, response time, replicas and memory of the API over the deployment]({CONFIG.chart_file})",
        "",
    ]
    if load.soak is not None:
        start, end = datetime.fromisoformat(load.soak.started), datetime.fromisoformat(load.soak.finished)
        during = _between(replicas, start, end)
        memory = _between(series["MemoryPercentage"], start, end)
        steps_per_hour = 12
        lines += [
            "## During the steady load",
            "",
            f"- The API ran 2 replicas in {sum(1 for value in during if value >= 2)} of {len(during)} steps.",
            f"- Memory averaged {sum(memory[:steps_per_hour]) / steps_per_hour:.0f}% of the limit in the first hour "
            f"and {sum(memory[-steps_per_hour:]) / steps_per_hour:.0f}% in the last, "
            f"with a peak of {max(memory):.0f}%. A leak would show as a climb.",
            "",
        ]
    lines += _usage_lines(saved)
    lines += [
        "## Alerts that fired",
        "",
        *_alert_rows(alerts),
        "",
        "## Limits",
        "",
        "- Each point is a 5-minute total or average, so short spikes are smoothed out.",
        "- Azure's response time is an average. The percentiles are in `LOAD.md`.",
        "",
    ]
    (folder / CONFIG.report_file).write_bytes("\n".join(lines).encode("utf-8"))
