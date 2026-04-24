"""Pure rendering helpers for spectrum heatmaps.

Three small pieces live here:

1. :func:`downsample_power` — stride-based zero-copy downsampling of a 2D
   power array so matplotlib's ``imshow`` has much less data to resample
   on every :func:`~matplotlib.figure.Figure.canvas.draw_idle` call.
2. :func:`build_rgba_cache` — pre-bake a colormap into a ``(H, W, 4)``
   uint8 RGBA array so matplotlib can skip the per-draw normalize +
   colormap step. Cached by array identity.
3. :func:`resolve_interpolation` — pick a fast interpolation mode when
   the caller passes ``"auto"`` based on the ratio between the input
   array resolution and the final displayed pixel size.

All three functions are pure and safely importable from anywhere in the
codebase (no Qt / matplotlib backend dependencies besides the colormap
object itself).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Downsampling
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def _stride_for_shape(
    key: int,
    shape: Tuple[int, int],
    max_rows: int,
    max_cols: int,
) -> Tuple[int, int]:
    """Compute the (row_stride, col_stride) required to fit ``shape`` inside
    ``max_rows × max_cols``. Cached by the caller-provided ``key`` so we
    don't recompute for the same input array on repeated renders.
    """
    r, c = shape
    return max(1, r // max(1, max_rows)), max(1, c // max(1, max_cols))


def _array_identity_key(arr: np.ndarray) -> int:
    """Stable hash key based on array memory address + shape + dtype."""
    try:
        data_ptr = arr.ctypes.data
    except Exception:
        data_ptr = id(arr)
    return hash((data_ptr, arr.shape, arr.dtype.str))


def downsample_power(power: np.ndarray, max_px: int = 400) -> np.ndarray:
    """Return a zero-copy stride slice of ``power`` fitting inside
    ``max_px × max_px``.

    * Arrays already within the budget are returned unchanged.
    * Non-2D inputs are passed through unchanged (the caller is
      responsible for handling malformed spectra).
    * The result is a numpy view when a stride is applied, so no extra
      memory is allocated.

    Parameters
    ----------
    power
        Power array with shape ``(n_vel, n_freq)``.
    max_px
        Target maximum number of samples along either axis.
    """
    if power.ndim != 2:
        return power
    if max_px <= 0:
        return power
    r, c = power.shape
    if r <= max_px and c <= max_px:
        return power

    key = _array_identity_key(power)
    rs, cs = _stride_for_shape(key, power.shape, max_px, max_px)
    if rs <= 1 and cs <= 1:
        return power
    return power[::rs, ::cs]


# ---------------------------------------------------------------------------
# RGBA cache
# ---------------------------------------------------------------------------


# Cache shape: {cache_key: rgba_uint8_array}. Bounded so we don't pin GB
# of RGBA when a user cycles through many spectra; the hard cap mirrors
# the downsampler cache.
_RGBA_CACHE: "dict[object, np.ndarray]" = {}
_RGBA_CACHE_LIMIT = 16


def build_rgba_cache(
    power: np.ndarray,
    cmap,
    vmin: float,
    vmax: float,
) -> np.ndarray:
    """Return a ``(H, W, 4) uint8`` RGBA image for ``power`` rendered
    with ``cmap`` between ``vmin`` and ``vmax``.

    Repeated calls with the same inputs hit an in-process cache keyed on
    array identity + colormap name + vmin/vmax. Callers that rebuild a
    spectrum layer in-place (e.g. on alpha slider changes) can therefore
    re-use the expensive normalize + colormap path. The cache is bounded
    to :data:`_RGBA_CACHE_LIMIT` entries on an LRU-ish basis.
    """
    if power.ndim != 2:
        raise ValueError(
            f"build_rgba_cache expects a 2D array, got shape {power.shape}"
        )

    cmap_name = getattr(cmap, "name", repr(cmap))
    key = (_array_identity_key(power), cmap_name, float(vmin), float(vmax))

    cached = _RGBA_CACHE.get(key)
    if cached is not None:
        # Touch the entry so a later insert at the limit evicts the
        # least-recently-used one first.
        _RGBA_CACHE[key] = _RGBA_CACHE.pop(key)
        return cached

    denom = float(vmax) - float(vmin)
    if denom <= 0 or not np.isfinite(denom):
        normalized = np.zeros_like(power, dtype=np.float32)
    else:
        normalized = np.clip(
            (power.astype(np.float32, copy=False) - float(vmin)) / denom,
            0.0,
            1.0,
        )

    rgba_float = cmap(normalized)  # (H, W, 4) float64
    rgba = (np.asarray(rgba_float) * 255.0).clip(0, 255).astype(np.uint8)

    _RGBA_CACHE[key] = rgba
    while len(_RGBA_CACHE) > _RGBA_CACHE_LIMIT:
        _RGBA_CACHE.pop(next(iter(_RGBA_CACHE)))

    return rgba


def clear_rgba_cache() -> None:
    """Drop every cached RGBA image. Call on spectrum data reload or
    colormap preference change.
    """
    _RGBA_CACHE.clear()
    _stride_for_shape.cache_clear()


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------


def resolve_interpolation(
    mode: str,
    input_shape: Tuple[int, int],
    output_shape: Tuple[int, int],
) -> str:
    """Translate the caller's preference into a matplotlib-compatible
    interpolation name.

    * ``"bilinear"`` and ``"nearest"`` pass through unchanged.
    * ``"auto"`` picks ``"nearest"`` when the input resolution is
      already close to or larger than the display resolution (no visible
      gain from bilinear interpolation), and ``"bilinear"`` otherwise.
    * Anything else is returned unchanged so rarely used matplotlib
      modes (``"none"``, ``"antialiased"``, …) still work if a user sets
      the pref directly.
    """
    mode = (mode or "auto").strip().lower()
    if mode in ("bilinear", "nearest"):
        return mode
    if mode != "auto":
        return mode

    try:
        in_r, in_c = int(input_shape[0]), int(input_shape[1])
        out_r, out_c = int(output_shape[0]), int(output_shape[1])
    except Exception:
        return "bilinear"

    if out_r <= 0 or out_c <= 0:
        return "bilinear"

    # When the input is already within 1.5x of the output on both axes,
    # bilinear interpolation only smears crisp features without adding
    # detail. Nearest is faster and looks the same at this ratio.
    if in_r >= out_r / 1.5 and in_c >= out_c / 1.5:
        return "nearest"
    return "bilinear"


__all__ = [
    "build_rgba_cache",
    "clear_rgba_cache",
    "downsample_power",
    "resolve_interpolation",
]
