"""Timing, with a clock that the test controls."""

from __future__ import annotations

import pytest
import torch

from fruity.lib.evaluation.latency import one_core, time_calls


def test_warmup_calls_run_but_are_not_counted(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    called: list[int] = []
    monkeypatch.setattr("time.perf_counter", lambda: now[0])

    def call(item: int) -> None:
        called.append(item)
        now[0] += item / 1000

    latency = time_calls(call, [500, 500, 10, 20, 30], warmup=2)
    assert called == [500, 500, 10, 20, 30]
    assert latency.p50_ms == pytest.approx(20)
    assert latency.p95_ms < 500


def test_one_core_limits_the_process_and_then_lets_go() -> None:
    threads = torch.get_num_threads()
    with one_core(0):
        assert torch.get_num_threads() == 1
    assert torch.get_num_threads() == threads
