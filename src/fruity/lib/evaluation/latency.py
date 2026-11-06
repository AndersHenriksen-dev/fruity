"""CPU latency as one vCPU would see it: one core and one thread, one image at a time."""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import psutil
import torch


@dataclass(frozen=True)
class Latency:
    """How long one call took, in milliseconds."""

    p50_ms: float
    p95_ms: float


@contextmanager
def one_core(core: int) -> Iterator[None]:
    """Keep this process on one CPU core and PyTorch on one thread until the block ends."""
    process = psutil.Process()
    cores = process.cpu_affinity()
    threads = torch.get_num_threads()
    process.cpu_affinity([core])
    torch.set_num_threads(1)
    try:
        yield
    finally:
        process.cpu_affinity(cores)
        torch.set_num_threads(threads)


def time_calls(call: Callable[[int], object], items: Sequence[int], warmup: int) -> Latency:
    """Time a function on each item.

    Args:
        call: The work to time.
        items: What to call it with.
        warmup: How many items run first without being counted, since the first calls fill caches.

    Returns:
        The median and the 95th percentile.
    """
    for item in items[:warmup]:
        call(item)
    seconds = []
    for item in items[warmup:]:
        started = time.perf_counter()
        call(item)
        seconds.append(time.perf_counter() - started)
    return Latency(statistics.median(seconds) * 1000, statistics.quantiles(seconds, n=20)[-1] * 1000)
