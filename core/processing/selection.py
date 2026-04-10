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


def side_of_line(
    x: np.ndarray,
    y: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> np.ndarray:
    """Compute which side of a line each point lies on.
    
    Parameters
    ----------
    x, y : array-like
        Point coordinates to test.
    x1, y1 : float
        First point defining the line.
    x2, y2 : float
        Second point defining the line.
    
    Returns
    -------
    np.ndarray
        +1 if point is above/left of line (counter-clockwise side),
        -1 if below/right (clockwise side), 0 if on line.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
    return np.sign(cross)


def line_mask(
    x: np.ndarray,
    y: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    side: str = "above",
) -> np.ndarray:
    """Return boolean mask for points on one side of a line.
    
    Parameters
    ----------
    x, y : array-like
        Point coordinates (e.g., frequency and velocity).
    x1, y1, x2, y2 : float
        Two points defining the line.
    side : str
        'above' for points above/left of line (positive cross product),
        'below' for points below/right of line (negative cross product).
    
    Returns
    -------
    np.ndarray
        Boolean mask, True for points on the specified side.
    """
    signs = side_of_line(x, y, x1, y1, x2, y2)
    if side == "above":
        return signs > 0
    elif side == "below":
        return signs < 0
    else:
        raise ValueError(f"side must be 'above' or 'below', got {side!r}")


def remove_above_line(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points above/left of a line defined by two points.
    
    Line is defined in (x, y) = (f or w, v) space. Points with positive
    cross-product (counter-clockwise from line direction) are removed.
    """
    mask = line_mask(f, v, x1, y1, x2, y2, side="above")
    keep = ~mask
    return v[keep], f[keep], w[keep]


def remove_below_line(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points below/right of a line defined by two points.
    
    Line is defined in (x, y) = (f or w, v) space. Points with negative
    cross-product (clockwise from line direction) are removed.
    """
    mask = line_mask(f, v, x1, y1, x2, y2, side="below")
    keep = ~mask
    return v[keep], f[keep], w[keep]


def remove_on_side_of_line(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    side: str = "above",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points on the specified side of a line.
    
    Parameters
    ----------
    v, f, w : np.ndarray
        Velocity, frequency, wavelength arrays.
    x1, y1, x2, y2 : float
        Two points defining the line in (x=frequency, y=velocity) space.
    side : str
        'above' to remove points above the line,
        'below' to remove points below the line.
    
    Returns
    -------
    Tuple of filtered (v, f, w) arrays.
    """
    mask = line_mask(f, v, x1, y1, x2, y2, side=side)
    keep = ~mask
    return v[keep], f[keep], w[keep]











