from __future__ import annotations

from typing import Tuple
import numpy as np


def filter_velocity_range(v: np.ndarray, *, vmin: float | None = None, vmax: float | None = None) -> np.ndarray:
    """Return mask for velocities within optional [vmin, vmax]."""
    m = np.ones_like(v, dtype=bool)
    if vmin is not None:
        m &= (v >= float(vmin))
    if vmax is not None:
        m &= (v <= float(vmax))
    return m


def filter_frequency_range(f: np.ndarray, *, fmin: float | None = None, fmax: float | None = None) -> np.ndarray:
    m = np.ones_like(f, dtype=bool)
    if fmin is not None:
        m &= (f >= float(fmin))
    if fmax is not None:
        m &= (f <= float(fmax))
    return m


def filter_wavelength_range(w: np.ndarray, *, wmin: float | None = None, wmax: float | None = None) -> np.ndarray:
    m = np.ones_like(w, dtype=bool)
    if wmin is not None:
        m &= (w >= float(wmin))
    if wmax is not None:
        m &= (w <= float(wmax))
    return m


def apply_filters(v: np.ndarray, f: np.ndarray, w: np.ndarray,
                  *, vmin: float | None = None, vmax: float | None = None,
                  fmin: float | None = None, fmax: float | None = None,
                  wmin: float | None = None, wmax: float | None = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply combined range filters and return filtered arrays."""
    mv = filter_velocity_range(v, vmin=vmin, vmax=vmax)
    mf = filter_frequency_range(f, fmin=fmin, fmax=fmax)
    mw = filter_wavelength_range(w, wmin=wmin, wmax=wmax)
    keep = mv & mf & mw
    return v[keep], f[keep], w[keep]


def apply_nacd_filter(v: np.ndarray, f: np.ndarray, w: np.ndarray, array_positions: np.ndarray, *, threshold: float = 1.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Filter out picks that are near-field according to NACD threshold."""
    from dc_cut.core.nearfield import compute_nacd_array
    nacd = compute_nacd_array(array_positions, f, v)
    keep = np.isfinite(nacd) & (nacd >= float(threshold))
    return v[keep], f[keep], w[keep]











