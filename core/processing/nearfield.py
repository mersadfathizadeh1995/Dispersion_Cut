"""Pure near-field / NACD computation functions.

No framework imports. No controller references. No side effects.
"""
from __future__ import annotations

from typing import Iterable, List, Dict, Optional
import numpy as np


def compute_nacd(array_positions: Iterable[float], freq: float, velocity: float, *, eps: float = 1e-12) -> float:
    """Approximate NACD: normalized array coherence distance.

    Simple heuristic fallback: ratio of inter-sensor wavelength to array aperture.
    NACD = (min_aperture / wavelength). Values < 1 often indicate near-field risk.
    """
    try:
        arr = np.asarray(array_positions, float)
        if arr.size < 2 or not np.isfinite(freq) or not np.isfinite(velocity) or freq <= 0 or velocity <= 0:
            return 0.0
        aperture = float(np.nanmax(arr) - np.nanmin(arr))
        wavelength = float(velocity / freq)
        if wavelength <= 0:
            return 0.0
        nacd = aperture / max(wavelength, eps)
        return float(nacd)
    except Exception:
        return 0.0


def compute_nacd_array(array_positions: Iterable[float], freqs: np.ndarray, velocities: np.ndarray, *, eps: float = 1e-12) -> np.ndarray:
    """Vectorised NACD (NumPy array) using the heuristic fallback."""
    freqs = np.asarray(freqs, float); velocities = np.asarray(velocities, float)
    out = np.zeros_like(velocities, dtype=float)
    for i in range(out.size):
        out[i] = compute_nacd(array_positions, freqs[i], velocities[i], eps=eps)
    return out


def compute_nacd_for_all_data(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    array_positions: Iterable[float],
    *,
    eps: float = 1e-12,
) -> List[np.ndarray]:
    """Compute NACD arrays for each offset's data."""
    results = []
    for v, f in zip(velocity_arrays, frequency_arrays):
        results.append(compute_nacd_array(array_positions, f, v, eps=eps))
    return results


def detect_nearfield_picks(picks: List[Dict[str, float]], array_positions: Iterable[float], *, threshold_nacd: Optional[float] = None, source_type: str = "hammer") -> List[Dict[str, float | bool]]:
    """Flag picks with NACD metadata and nearfield boolean.

    Standalone fallback: sets nacd=0.0 and nearfield=False for all picks.
    """
    out: List[Dict[str, float | bool]] = []
    thr = float(threshold_nacd) if threshold_nacd is not None else 1.0
    for p in picks:
        q = dict(p)
        q['nacd'] = 0.0
        q['nearfield'] = False
        q['source_type'] = source_type
        out.append(q)
    return out
