from __future__ import annotations

import numpy as np
from typing import Tuple


def remove_in_freq_box(v: np.ndarray, f: np.ndarray, w: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    keep = ~(((f >= xmin) & (f <= xmax)) & ((v >= ymin) & (v <= ymax)))
    return v[keep], f[keep], w[keep]


def remove_in_wave_box(v: np.ndarray, f: np.ndarray, w: np.ndarray, *, xmin: float, xmax: float, ymin: float, ymax: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    keep = ~(((w >= xmin) & (w <= xmax)) & ((v >= ymin) & (v <= ymax)))
    return v[keep], f[keep], w[keep]










