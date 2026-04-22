"""
LRU cache for downsampled spectrum arrays.

This module used to own the downsampling helper, but the logic has been
lifted into :mod:`dc_cut.core.rendering.spectrum_render` so the main
DC-cut canvas and Report Studio share one implementation. The public
surface (:func:`get_downsampled`, :func:`clear_cache`) is preserved as a
thin re-export so every existing caller in Report Studio keeps working
without modification.
"""

from __future__ import annotations

from dc_cut.core.rendering.spectrum_render import (
    clear_rgba_cache as _clear_rgba_cache,
    downsample_power,
)


def get_downsampled(power, max_px: int = 200):
    """Return a downsampled stride view of ``power`` fitting inside
    ``max_px × max_px`` — zero-copy when the input is already small
    enough.
    """
    return downsample_power(power, max_px=max_px)


def clear_cache() -> None:
    """Drop cached downsample stride info and the shared RGBA cache.

    Historically this only cleared the stride LRU; it now also clears
    the RGBA cache introduced by the shared rendering helper since
    both caches become stale together when a spectrum is reloaded.
    """
    _clear_rgba_cache()


__all__ = ["get_downsampled", "clear_cache"]
