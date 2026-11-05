"""The limit on requests per minute."""

from __future__ import annotations

from fruity.lib.serving.limits import RateLimiter


def test_it_allows_up_to_the_limit_and_no_more() -> None:
    limiter = RateLimiter(2, clock=lambda: 0.0)
    assert [limiter.allow() for _ in range(3)] == [True, True, False]


def test_requests_are_allowed_again_when_the_window_has_passed() -> None:
    now = [0.0]
    limiter = RateLimiter(1, clock=lambda: now[0])
    assert limiter.allow()
    now[0] = 59.0
    assert not limiter.allow()
    now[0] = 60.0
    assert limiter.allow()


def test_a_refused_request_does_not_extend_the_wait() -> None:
    now = [0.0]
    limiter = RateLimiter(1, clock=lambda: now[0])
    limiter.allow()
    now[0] = 30.0
    limiter.allow()
    now[0] = 60.0
    assert limiter.allow()
