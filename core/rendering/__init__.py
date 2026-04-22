"""Rendering helpers shared between the main DC-cut app and Report Studio.

Today this module contains only spectrum-related helpers but it is the
natural home for any future pure-rendering utilities that both packages
need (pre-bake colormaps, downsample heatmaps, pick interpolation modes
based on screen DPI, etc.). Keeping these helpers in :mod:`dc_cut.core`
avoids pulling the Report Studio package into the main app just to reach
the downsampler.
"""

from .spectrum_render import (
    build_rgba_cache,
    clear_rgba_cache,
    downsample_power,
    resolve_interpolation,
)

__all__ = [
    "build_rgba_cache",
    "clear_rgba_cache",
    "downsample_power",
    "resolve_interpolation",
]
