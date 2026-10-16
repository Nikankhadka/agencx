"""Slice 1 (latency): the percentile rule.

Pins the linear-interpolation rule from ``app/observability/percentile.py`` and
the four ways a latency percentile is commonly got wrong: a single sample, a
100-point sample that is not its mean, unsorted input, and duplicates.
"""

from __future__ import annotations

import pytest

from app.observability.percentile import percentile


def test_single_sample_returns_that_sample_for_any_p() -> None:
    assert percentile([42.0], 95) == 42.0
    assert percentile([42.0], 0) == 42.0
    assert percentile([42.0], 100) == 42.0


def test_p95_of_100_is_near_the_top_not_the_mean() -> None:
    values = [float(n) for n in range(1, 101)]  # 1..100, mean 50.5
    result = percentile(values, 95)
    assert result == pytest.approx(95.05)
    assert result != pytest.approx(50.5)


def test_linear_interpolation_between_the_two_closest_ranks() -> None:
    # A hand-computed known array: [1..10], p95. rank = (10-1)*0.95 = 8.55,
    # between v[8]=9 and v[9]=10 -> 9 + (10-9)*0.55 = 9.55.
    assert percentile([float(n) for n in range(1, 11)], 95) == pytest.approx(9.55)
    # n=2: rank = 0.95 between 10 and 20 -> 10 + 10*0.95 = 19.5.
    assert percentile([10.0, 20.0], 95) == pytest.approx(19.5)


def test_unsorted_input_matches_sorted() -> None:
    unsorted = [5, 1, 4, 2, 3]
    sorted_ = [1, 2, 3, 4, 5]
    for p in (0, 25, 50, 90, 95, 100):
        assert percentile(unsorted, p) == percentile(sorted_, p)


def test_duplicates_are_preserved() -> None:
    assert percentile([5.0, 5.0, 5.0, 5.0], 95) == 5.0
    # [1,5,5,5,9], p95: rank = 4*0.95 = 3.8, between v[3]=5 and v[4]=9 -> 8.2.
    assert percentile([1.0, 5.0, 5.0, 5.0, 9.0], 95) == pytest.approx(8.2)


def test_endpoints_are_min_and_max() -> None:
    values = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0]
    assert percentile(values, 0) == 1.0
    assert percentile(values, 100) == 9.0


def test_empty_sample_and_p_out_of_range_raise() -> None:
    with pytest.raises(ValueError):
        percentile([], 95)
    with pytest.raises(ValueError):
        percentile([1.0], 101)
    with pytest.raises(ValueError):
        percentile([1.0], -0.1)
