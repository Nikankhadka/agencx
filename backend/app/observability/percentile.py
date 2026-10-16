"""Slice 1 (latency): percentile math for the latency evidence.

One rule everywhere: **linear interpolation between the two closest ranks**
(the ``numpy`` default, the Hyndman-Fan type 7 rule). For a sample of ``n``
values sorted ascending and a percentile ``p`` in ``[0, 100]``:

    rank = (n - 1) * p / 100
    result = v[floor(rank)] + (v[ceil(rank)] - v[floor(rank)]) * (rank - floor(rank))

Consequences the tests pin, because each is a way a latency percentile is
commonly got wrong:

- ``n == 1`` returns that single sample for any ``p`` - never a zero, never an
  error.
- ``n == 100`` returns the interpolated value near the top of the sample, not
  the mean.
- The input need not be sorted; this function sorts a copy and never mutates
  its argument.
- Duplicates survive: a sample of identical values returns that value.

The input is a sequence of seconds-scaled numbers (milliseconds in this repo);
the function is unit-agnostic.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def percentile(values: Sequence[float], p: float) -> float:
    """The ``p``-th percentile of ``values`` by linear interpolation.

    Raises ``ValueError`` on an empty sample or a ``p`` outside ``[0, 100]`` -
    a percentile of nothing is a bug in the caller, not a number to return.
    """
    if not values:
        raise ValueError("percentile of an empty sample is undefined")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"percentile must be in [0, 100], got {p!r}")

    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])

    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * weight)
