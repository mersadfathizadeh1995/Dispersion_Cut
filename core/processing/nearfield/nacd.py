"""NACD (Normalized Array-Center Distance) computation functions.

Implements x̄-based NACD (Yoon & Rix 2009, Rahimi et al. 2022).
NACD = x̄ / λ  where  x̄ = (1/M) Σ|xₘ − source_offset|.
Values below the threshold indicate near-field contamination risk.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional
import numpy as np


def compute_nacd(
    array_positions: Iterable[float],
    freq: float,
    velocity: float,
    *,
    source_offset: Optional[float] = None,
    eps: float = 1e-12,
) -> float:
    """Compute NACD for a single (f, V) pick.

    When *source_offset* is provided the characteristic distance is the
    mean source-to-receiver distance (x̄), consistent with the
    λ-line criterion.  Otherwise falls back to the array aperture.

    NACD = x̄ / λ         (source_offset given)
    NACD = aperture / λ   (no source_offset — legacy fallback)
    """
    try:
        arr = np.asarray(array_positions, float)
        if arr.size < 2 or not np.isfinite(freq) or not np.isfinite(velocity):
            return 0.0
        if freq <= 0 or velocity <= 0:
            return 0.0

        wavelength = float(velocity / freq)
        if wavelength <= 0:
            return 0.0

        if source_offset is not None:
            x_bar = float(np.mean(np.abs(arr - float(source_offset))))
        else:
            x_bar = float(np.nanmax(arr) - np.nanmin(arr))

        return float(x_bar / max(wavelength, eps))
    except Exception:
        return 0.0


def compute_nacd_array(
    array_positions: Iterable[float],
    freqs: np.ndarray,
    velocities: np.ndarray,
    *,
    source_offset: Optional[float] = None,
    eps: float = 1e-12,
) -> np.ndarray:
    """Vectorised NACD over arrays of (f, V) picks."""
    freqs = np.asarray(freqs, float)
    velocities = np.asarray(velocities, float)
    out = np.zeros_like(velocities, dtype=float)
    for i in range(out.size):
        out[i] = compute_nacd(
            array_positions, freqs[i], velocities[i],
            source_offset=source_offset, eps=eps,
        )
    return out


def compute_nacd_for_all_data(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    array_positions: Iterable[float],
    *,
    source_offsets: Optional[List[float]] = None,
    eps: float = 1e-12,
) -> List[np.ndarray]:
    """Compute NACD arrays for each offset's data."""
    results = []
    for idx, (v, f) in enumerate(zip(velocity_arrays, frequency_arrays)):
        so = source_offsets[idx] if source_offsets and idx < len(source_offsets) else None
        results.append(compute_nacd_array(array_positions, f, v, source_offset=so, eps=eps))
    return results


def detect_nearfield_picks(
    picks: List[Dict[str, float]],
    array_positions: Iterable[float],
    *,
    threshold_nacd: Optional[float] = None,
    source_offset: Optional[float] = None,
    source_type: str = "hammer",
) -> List[Dict[str, float | bool]]:
    """Flag picks with NACD metadata and nearfield boolean.

    Each pick dict must have ``frequency`` and ``velocity`` keys.
    """
    recv = np.asarray(list(array_positions), float)
    thr = float(threshold_nacd) if threshold_nacd is not None else 1.0
    out: List[Dict[str, float | bool]] = []
    for p in picks:
        q = dict(p)
        f = float(p.get('frequency', 0))
        v = float(p.get('velocity', 0))
        nacd_val = compute_nacd(recv, f, v, source_offset=source_offset)
        q['nacd'] = nacd_val
        q['nearfield'] = nacd_val < thr
        q['source_type'] = source_type
        out.append(q)
    return out
