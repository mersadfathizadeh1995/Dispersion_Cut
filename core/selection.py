from __future__ import annotations

import numpy as np
from typing import Tuple


def box_mask_freq(freq: np.ndarray, vel: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> np.ndarray:
    """Return boolean mask of points inside a frequency-velocity box."""
    return ((freq >= xmin) & (freq <= xmax) & (vel >= ymin) & (vel <= ymax))


def box_mask_wave(wave: np.ndarray, vel: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> np.ndarray:
    """Return boolean mask of points inside a wavelength-velocity box."""
    return ((wave >= xmin) & (wave <= xmax) & (vel >= ymin) & (vel <= ymax))


def remove_in_freq_box(v: np.ndarray, f: np.ndarray, w: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points inside the freq/vel selection box, return filtered arrays."""
    keep = ~box_mask_freq(f, v, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    return v[keep], f[keep], w[keep]


def remove_in_wave_box(v: np.ndarray, f: np.ndarray, w: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points inside the wave/vel selection box, return filtered arrays."""
    keep = ~box_mask_wave(w, v, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax)
    return v[keep], f[keep], w[keep]











