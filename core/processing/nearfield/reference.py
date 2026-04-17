"""Reference curve helpers for near-field analysis.

Functions for selecting, computing, and loading reference dispersion
curves used in V_R normalisation.

No framework imports, no controller references.
"""
from __future__ import annotations

import pathlib
from typing import List, Optional, Tuple, Union
import numpy as np


def select_reference_by_largest_xbar(
    source_offsets: List[float],
    receiver_positions: np.ndarray,
) -> int:
    """Return the index of the offset with the largest x̄."""
    from dc_cut.core.processing.wavelength_lines import compute_x_bar

    best_idx, best_xbar = 0, -1.0
    recv = np.asarray(receiver_positions, float)
    for i, so in enumerate(source_offsets):
        xb = compute_x_bar(so, recv)
        if xb > best_xbar:
            best_xbar = xb
            best_idx = i
    return best_idx


def compute_composite_reference(
    frequency_arrays: List[np.ndarray],
    velocity_arrays: List[np.ndarray],
    *,
    source_offsets: Optional[List[float]] = None,
    receiver_positions: Optional[np.ndarray] = None,
    nacd_threshold: float = 1.0,
    num_bins: int = 200,
    method: str = "median",
    weighting: str = "equal",
    trim_fraction: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Build a reference curve as the median (or mean) across offsets.

    When *source_offsets* and *receiver_positions* are provided, only
    data from offsets that are NF-clean (λ < λ_max) at each frequency
    bin are included, preventing contaminated data from biasing the
    reference.

    Parameters
    ----------
    weighting : str
        ``"equal"`` — all offsets weighted equally (original behaviour).
        ``"nacd"`` — weight by NACD value (higher NACD = cleaner = more weight).
        ``"xbar"`` — weight by x̄ (larger x̄ = more reliable at long λ).
    trim_fraction : float
        Fraction of extreme values to trim at each bin (0.0–0.4).
        0.0 = no trimming (original behaviour).
        0.1 = trim 10% of highest and lowest values.
    """
    from dc_cut.core.processing.wavelength_lines import compute_x_bar

    lambda_maxes: Optional[List[float]] = None
    xbars: Optional[List[float]] = None
    if source_offsets is not None and receiver_positions is not None:
        recv = np.asarray(receiver_positions, float)
        xbars = [compute_x_bar(so, recv) for so in source_offsets]
        lambda_maxes = [
            xb / max(nacd_threshold, 1e-12)
            for xb in xbars
        ]

    all_f = np.concatenate([np.asarray(a, float) for a in frequency_arrays])
    if all_f.size == 0:
        return np.array([]), np.array([])

    fmin, fmax = float(np.nanmin(all_f[all_f > 0])), float(np.nanmax(all_f))
    f_grid = np.linspace(fmin, fmax, num_bins)
    df = (fmax - fmin) / num_bins * 0.6

    v_ref = np.full(num_bins, np.nan)
    for k in range(num_bins):
        vals = []
        weights = []
        for i, (fa, va) in enumerate(zip(frequency_arrays, velocity_arrays)):
            fa = np.asarray(fa, float)
            va = np.asarray(va, float)
            freq_mask = np.abs(fa - f_grid[k]) < df
            if not np.any(freq_mask):
                continue
            if lambda_maxes is not None:
                v_at_f = float(np.median(va[freq_mask]))
                lam_at_f = v_at_f / max(f_grid[k], 1e-12)
                if lam_at_f > lambda_maxes[i]:
                    continue

            bin_vals = va[freq_mask].tolist()
            vals.extend(bin_vals)

            # Compute weight for this offset's contribution
            if weighting == "nacd" and xbars is not None:
                nacd_at_f = xbars[i] / max(float(np.median(va[freq_mask])) / max(f_grid[k], 1e-12), 1e-12)
                weights.extend([nacd_at_f] * len(bin_vals))
            elif weighting == "xbar" and xbars is not None:
                weights.extend([xbars[i]] * len(bin_vals))
            else:
                weights.extend([1.0] * len(bin_vals))

        if vals:
            arr = np.array(vals)
            # Apply trimming
            if trim_fraction > 0 and len(arr) >= 4:
                n_trim = max(1, int(len(arr) * trim_fraction))
                order = np.argsort(arr)
                keep = order[n_trim:-n_trim] if n_trim < len(arr) // 2 else order
                arr = arr[keep]
                if weights:
                    w = np.array(weights)
                    w = w[keep]
                    weights = w.tolist()

            if method == "median":
                v_ref[k] = float(np.median(arr))
            elif weighting != "equal" and weights:
                # Weighted mean
                w = np.array(weights[:len(arr)])
                w_sum = np.sum(w)
                if w_sum > 0:
                    v_ref[k] = float(np.sum(arr * w) / w_sum)
                else:
                    v_ref[k] = float(np.mean(arr))
            else:
                v_ref[k] = float(np.mean(arr))

    valid = np.isfinite(v_ref)
    return f_grid[valid], v_ref[valid]


def load_reference_curve(
    path: Union[str, pathlib.Path],
) -> Tuple[np.ndarray, np.ndarray]:
    """Load a reference dispersion curve from CSV or NPZ.

    CSV must have two columns (frequency, velocity).
    NPZ must contain keys ``frequency`` and ``velocity``.
    """
    p = pathlib.Path(path)
    if p.suffix.lower() == ".npz":
        d = np.load(p)
        return np.asarray(d["frequency"], float), np.asarray(d["velocity"], float)
    data = np.loadtxt(p, delimiter=",", comments="#")
    if data.ndim == 1:
        raise ValueError("Reference file must have two columns (freq, vel).")
    return data[:, 0].astype(float), data[:, 1].astype(float)
