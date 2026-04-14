"""Pure computation functions for constant-wavelength (lambda) reference lines.

Each lambda line represents V_phase = lambda * f on the dispersion plot.
The maximum resolved wavelength (lambda_max) is derived from the NACD criterion:
    lambda_max = x_bar / NACD_threshold
where x_bar is the mean source-to-receiver distance.

No framework imports. No controller references. No side effects.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import numpy as np


def compute_x_bar(source_offset: float, receiver_positions: np.ndarray) -> float:
    """Compute the mean source-to-receiver distance (array center distance).

    Parameters
    ----------
    source_offset : float
        Position of the source relative to the first receiver.
        Negative means the source is *before* the array start,
        positive means the source is *past* the array end.
        E.g. -2 => source 2 m before first receiver,
             +66 => source 66 m after first receiver.
    receiver_positions : np.ndarray
        Positions of each receiver relative to the first receiver
        (e.g. [0, 2, 4, ..., 46] for 24 geophones at 2 m spacing).

    Returns
    -------
    float
        Mean absolute distance from source to all receivers.
    """
    distances = np.abs(np.asarray(receiver_positions, float) - float(source_offset))
    return float(np.mean(distances))


def compute_lambda_max(
    source_offset: float,
    receiver_positions: np.ndarray,
    nacd_threshold: float = 1.0,
) -> float:
    """Compute the maximum resolved wavelength for a given source offset.

    lambda_max = x_bar / NACD_threshold

    Returns 0.0 if the threshold is non-positive.
    """
    if nacd_threshold <= 0:
        return 0.0
    x_bar = compute_x_bar(source_offset, receiver_positions)
    return x_bar / nacd_threshold


def compute_wavelength_line(
    lambda_val: float,
    fmin: float,
    fmax: float,
    num_points: int = 300,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate (f_curve, v_curve) for a constant-wavelength line V = lambda * f.

    Both axes are suitable for semilogx plotting (f is log-spaced).
    """
    fmin = max(fmin, 1e-6)
    fmax = max(fmax, fmin * 1.1)
    f_curve = np.logspace(np.log10(fmin), np.log10(fmax), num_points)
    v_curve = lambda_val * f_curve
    return f_curve, v_curve


def compute_wavelength_lines_batch(
    source_offsets: List[float],
    receiver_positions: np.ndarray,
    fmin: float,
    fmax: float,
    nacd_threshold: float = 1.0,
    labels: Optional[List[str]] = None,
    num_points: int = 300,
) -> List[Dict]:
    """Compute wavelength lines for multiple source offsets.

    Returns a list of dicts, each with:
        source_offset, label, x_bar, lambda_max, f_curve, v_curve
    """
    results: List[Dict] = []
    for i, so in enumerate(source_offsets):
        lbl = labels[i] if labels and i < len(labels) else f"{so:+g} m"
        x_bar = compute_x_bar(so, receiver_positions)
        lam = x_bar / nacd_threshold if nacd_threshold > 0 else 0.0
        if lam <= 0:
            continue
        f_curve, v_curve = compute_wavelength_line(lam, fmin, fmax, num_points)
        results.append({
            "source_offset": so,
            "label": lbl,
            "x_bar": x_bar,
            "lambda_max": lam,
            "f_curve": f_curve,
            "v_curve": v_curve,
        })
    return results


def compute_lambda_max_manual(
    x_bar: float,
    nacd_threshold: float = 1.0,
) -> float:
    """Compute lambda_max from a user-provided x_bar directly."""
    if nacd_threshold <= 0 or x_bar <= 0:
        return 0.0
    return x_bar / nacd_threshold


_OFFSET_RE = re.compile(r"[_/]([+-]?\d+(?:\.\d+)?)\s*$")


def parse_source_offset_from_label(label: str) -> Optional[float]:
    """Try to extract a signed numeric source offset from a layer label.

    Handles patterns like:
        "Rayleigh/fdbf_+66"  -> +66.0  (source 66 m past the array)
        "Rayleigh/fdbf_-2"   -> -2.0   (source 2 m before the array)
        "fdbf_+5"            -> +5.0

    The sign is preserved so that x_bar is computed correctly.
    Returns None if no numeric offset can be extracted.
    """
    m = _OFFSET_RE.search(label)
    if m:
        return float(m.group(1))
    return None
