"""
LRU cache for downsampled spectrum arrays.

Avoids re-downsampling the same power arrays on every render when
only style/legend/curve settings change (spectrum data unchanged).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Tuple

import numpy as np


def _array_key(arr: np.ndarray) -> int:
    """Fast hash key from array data pointer + shape + dtype."""
    return hash((arr.ctypes.data, arr.shape, arr.dtype.str))


@lru_cache(maxsize=64)
def _cached_downsample(
    key: int,
    shape: Tuple[int, int],
    max_rows: int,
    max_cols: int,
) -> Tuple[int, int]:
    """Return stride steps for the given shape. Cached by array identity."""
    r, c = shape
    return max(1, r // max_rows), max(1, c // max_cols)


def get_downsampled(
    power: np.ndarray,
    max_px: int = 200,
) -> np.ndarray:
    """
    Return a downsampled view of *power* for draft-quality rendering.

    Uses an LRU cache keyed on the array's memory address + shape so
    repeated renders of the same data skip the stride computation.
    For arrays that fit within *max_px* on both axes, returns the
    original array unchanged.
    """
    if power.ndim != 2:
        return power
    r, c = power.shape
    if r <= max_px and c <= max_px:
        return power

    key = _array_key(power)
    rs, cs = _cached_downsample(key, power.shape, max_px, max_px)
    return power[::rs, ::cs]


def clear_cache():
    """Clear the downsample cache (call when spectrum data changes)."""
    _cached_downsample.cache_clear()
