"""Edit operations: delete, filter, undo/redo.

Wraps core processing functions with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple

import numpy as np

from dc_cut.api.config import FilterConfig


def apply_filters(
    velocity: np.ndarray,
    frequency: np.ndarray,
    wavelength: np.ndarray,
    config: FilterConfig,
) -> Dict[str, Any]:
    """Apply range filters to dispersion arrays.

    Returns {"success": bool, "errors": [...], "velocity": ..., "frequency": ..., "wavelength": ...}
    """
    try:
        from dc_cut.core.processing.filters import apply_filters as _apply_filters

        v, f, w = _apply_filters(
            velocity, frequency, wavelength,
            vmin=config.velocity_min,
            vmax=config.velocity_max,
            fmin=config.frequency_min,
            fmax=config.frequency_max,
            wmin=config.wavelength_min,
            wmax=config.wavelength_max,
        )
        removed = velocity.size - v.size
        return {
            "success": True,
            "errors": [],
            "velocity": v,
            "frequency": f,
            "wavelength": w,
            "removed_count": removed,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def remove_in_box(
    velocity: np.ndarray,
    frequency: np.ndarray,
    wavelength: np.ndarray,
    *,
    domain: str = "frequency",
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
) -> Dict[str, Any]:
    """Remove points inside a selection box.

    domain: "frequency" or "wavelength"
    """
    try:
        if domain == "frequency":
            from dc_cut.core.processing.selection import remove_in_freq_box
            v, f, w = remove_in_freq_box(velocity, frequency, wavelength,
                                          xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        else:
            from dc_cut.core.processing.selection import remove_in_wave_box
            v, f, w = remove_in_wave_box(velocity, frequency, wavelength,
                                          xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
        removed = velocity.size - v.size
        return {
            "success": True,
            "errors": [],
            "velocity": v,
            "frequency": f,
            "wavelength": w,
            "removed_count": removed,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def remove_on_side_of_line(
    velocity: np.ndarray,
    frequency: np.ndarray,
    wavelength: np.ndarray,
    *,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    side: str = "above",
) -> Dict[str, Any]:
    """Remove points on one side of a line."""
    try:
        from dc_cut.core.processing.selection import remove_on_side_of_line as _remove
        v, f, w = _remove(velocity, frequency, wavelength,
                          x1=x1, y1=y1, x2=x2, y2=y2, side=side)
        removed = velocity.size - v.size
        return {
            "success": True,
            "errors": [],
            "velocity": v,
            "frequency": f,
            "wavelength": w,
            "removed_count": removed,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}
