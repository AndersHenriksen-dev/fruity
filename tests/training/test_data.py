"""The Food-101 split."""

from __future__ import annotations

from fruity.lib.training.data import split_indices


def test_the_same_seed_gives_the_same_split() -> None:
    assert split_indices(1_000, 0.1, 42) == split_indices(1_000, 0.1, 42)


def test_another_seed_gives_another_split() -> None:
    assert split_indices(1_000, 0.1, 42) != split_indices(1_000, 0.1, 43)


def test_no_image_is_in_both_sets_and_none_is_lost() -> None:
    train, val = split_indices(1_000, 0.1, 42)
    assert len(val) == 100
    assert sorted(train + val) == list(range(1_000))
