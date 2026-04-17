"""Higher-mode and mode-kissing detection.

Flags points where measured velocity deviates upward from the
reference, indicating potential higher-mode contamination or
mode-kissing artefacts.  Includes both reference-based and
standalone (reference-free) detection strategies.

Rahimi et al. (2021) Section 5.3: different transformation methods
have different sensitivities to higher modes.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy.signal import medfilt


def detect_mode_jump(
    f: np.ndarray,
    v: np.ndarray,
    f_ref: np.ndarray,
    v_ref: np.ndarray,
    *,
    relative_jump: float = 0.15,
    min_consecutive: int = 3,
) -> Dict[str, Any]:
    """Flag points where velocity jumps above the reference.

    Points where ``V_measured > V_ref × (1 + relative_jump)`` are
    flagged as potential higher-mode contamination.

    Parameters
    ----------
    f : array
        Measured frequencies.
    v : array
        Measured velocities.
    f_ref : array
        Reference curve frequencies.
    v_ref : array
        Reference curve velocities.
    relative_jump : float
        Fractional jump threshold above reference (0.15 = 15%).
    min_consecutive : int
        Minimum consecutive flagged points to confirm a mode jump.

    Returns
    -------
    dict
        ``has_mode_jump`` — whether a sustained mode jump was detected.
        ``jump_mask`` — boolean mask of flagged points.
        ``jump_indices`` — array of flagged indices.
        ``jump_frequencies`` — frequencies of flagged points.
        ``jump_magnitudes`` — (V_measured / V_ref) - 1 at flagged points.
        ``longest_run`` — longest consecutive flagged sequence.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    f_ref = np.asarray(f_ref, float)
    v_ref = np.asarray(v_ref, float)

    # Interpolate reference to measured frequencies
    sort = np.argsort(f_ref)
    v_interp = np.interp(f, f_ref[sort], v_ref[sort], left=np.nan, right=np.nan)

    valid = np.isfinite(v_interp) & np.isfinite(v) & (v_interp > 0)
    ratio = np.where(valid, v / v_interp, np.nan)
    jump_mask = valid & (ratio > 1.0 + relative_jump)

    # Find longest consecutive run
    indices = np.where(jump_mask)[0]
    longest = _longest_consecutive(indices)

    has_jump = longest >= min_consecutive

    magnitudes = np.where(jump_mask, ratio - 1.0, 0.0)

    return {
        "has_mode_jump": has_jump,
        "jump_mask": jump_mask,
        "jump_indices": indices,
        "jump_frequencies": f[jump_mask] if np.any(jump_mask) else np.array([]),
        "jump_magnitudes": magnitudes[jump_mask] if np.any(jump_mask) else np.array([]),
        "longest_run": longest,
        "n_flagged": int(np.sum(jump_mask)),
        "n_total": int(np.sum(valid)),
    }


def detect_mode_kissing(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 5,
    gradient_threshold: float = 2.0,
) -> Dict[str, Any]:
    """Detect mode-kissing from sudden velocity gradient changes.

    Mode kissing creates a characteristic "bump" in the dispersion curve
    where the fundamental and first higher mode approach each other.

    Parameters
    ----------
    f : array
        Frequency values (sorted ascending).
    v : array
        Velocity values.
    smoothing_window : int
        Window for gradient smoothing.
    gradient_threshold : float
        Multiple of the median gradient to flag as anomalous.

    Returns
    -------
    dict
        ``has_kissing`` — whether mode kissing was detected.
        ``kissing_frequencies`` — frequency locations of detected kissing.
        ``gradient_anomalies`` — indices where gradient is anomalous.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    valid = np.isfinite(f) & np.isfinite(v) & (f > 0)
    f, v = f[valid], v[valid]

    if len(f) < smoothing_window + 3:
        return {
            "has_kissing": False,
            "kissing_frequencies": np.array([]),
            "gradient_anomalies": np.array([], dtype=int),
        }

    # Sort by frequency
    order = np.argsort(f)
    f_s, v_s = f[order], v[order]

    # Compute velocity gradient dV/df
    dv = np.gradient(v_s, f_s)

    # Smooth
    if smoothing_window > 1:
        kernel = np.ones(smoothing_window) / smoothing_window
        dv_smooth = np.convolve(dv, kernel, mode="same")
    else:
        dv_smooth = dv

    # Flag where |gradient| exceeds threshold × median(|gradient|)
    med_grad = np.median(np.abs(dv_smooth))
    anomalies = np.abs(dv_smooth) > gradient_threshold * max(med_grad, 1e-6)

    # Look for sign changes in gradient (bump shape)
    sign_changes = np.diff(np.sign(dv_smooth)) != 0
    # Mode kissing = anomalous gradient + sign change nearby
    kissing_mask = np.zeros(len(f_s), dtype=bool)
    anomaly_idx = np.where(anomalies)[0]
    for idx in anomaly_idx:
        if idx > 0 and idx < len(sign_changes) and sign_changes[idx - 1]:
            kissing_mask[idx] = True
        if idx < len(sign_changes) and sign_changes[idx]:
            kissing_mask[idx] = True

    return {
        "has_kissing": bool(np.any(kissing_mask)),
        "kissing_frequencies": f_s[kissing_mask],
        "gradient_anomalies": np.where(anomalies)[0],
        "n_anomalies": int(np.sum(anomalies)),
    }


def _longest_consecutive(indices: np.ndarray) -> int:
    """Return the length of the longest consecutive run in sorted indices."""
    if len(indices) == 0:
        return 0
    longest = 1
    current = 1
    for i in range(1, len(indices)):
        if indices[i] == indices[i - 1] + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


# ──────────────────────────────────────────────────────────────────
#  Standalone (reference-free) mode jump detection
# ──────────────────────────────────────────────────────────────────

def _detect_median_deviation(
    f_s: np.ndarray,
    v_s: np.ndarray,
    *,
    kernel_size: int = 7,
    sigma_threshold: float = 2.5,
) -> np.ndarray:
    """Strategy 1: running-median deviation.

    Compare each velocity to a running median.  Points that jump
    *above* the local median by more than ``sigma_threshold × MAD``
    are flagged as potential higher-mode contamination.

    Returns boolean mask (same length as *f_s*).
    """
    if len(v_s) < kernel_size:
        return np.zeros(len(v_s), dtype=bool)
    ks = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
    v_med = medfilt(v_s, kernel_size=ks)
    residual = v_s - v_med
    mad = np.median(np.abs(residual))
    if mad < 1e-12:
        return np.zeros(len(v_s), dtype=bool)
    return residual > sigma_threshold * mad * 1.4826  # MAD→σ scale


def _detect_gradient_reversal(
    f_s: np.ndarray,
    v_s: np.ndarray,
    *,
    smoothing_window: int = 7,
    min_run: int = 3,
) -> np.ndarray:
    """Strategy 2: gradient reversal at mid/high frequencies.

    Normal Rayleigh-wave dispersion has dV/df < 0 (velocity decreases
    with increasing frequency).  A sustained region of dV/df > 0 at
    mid-to-high frequencies (NOT at the low-frequency NF tail)
    suggests higher-mode contamination.

    Returns boolean mask (same length as *f_s*).
    """
    mask = np.zeros(len(f_s), dtype=bool)
    if len(f_s) < smoothing_window + 3:
        return mask
    if smoothing_window > 1:
        kernel = np.ones(smoothing_window) / smoothing_window
        v_sm = np.convolve(v_s, kernel, mode="same")
    else:
        v_sm = v_s
    grad = np.gradient(v_sm, f_s)

    # Only look in the upper 75 % of the frequency range
    # (lower 25 % is where NF roll-off lives — not mode jumps)
    low_cutoff_idx = len(f_s) // 4
    run_start = None
    run_len = 0
    for i in range(low_cutoff_idx, len(grad)):
        if grad[i] > 0:
            if run_start is None:
                run_start = i
            run_len += 1
        else:
            if run_len >= min_run and run_start is not None:
                mask[run_start:run_start + run_len] = True
            run_start = None
            run_len = 0
    if run_len >= min_run and run_start is not None:
        mask[run_start:run_start + run_len] = True
    return mask


def _detect_segment_discontinuity(
    f_s: np.ndarray,
    v_s: np.ndarray,
    *,
    n_segments: int = 4,
    jump_threshold_pct: float = 10.0,
) -> np.ndarray:
    """Strategy 3: segment discontinuity.

    Split the curve into overlapping segments, fit local linear trends,
    and flag boundaries where adjacent segments have inconsistent
    velocity levels (intercept shift > ``jump_threshold_pct`` %).

    Returns boolean mask (same length as *f_s*).
    """
    mask = np.zeros(len(f_s), dtype=bool)
    n = len(f_s)
    if n < n_segments * 3:
        return mask
    seg_len = n // n_segments
    intercepts = []
    for s in range(n_segments):
        i0 = s * seg_len
        i1 = min(i0 + seg_len, n)
        seg_f = f_s[i0:i1]
        seg_v = v_s[i0:i1]
        if len(seg_f) < 2:
            intercepts.append(np.nan)
            continue
        # Simple linear fit: v = a*f + b
        coeffs = np.polyfit(seg_f, seg_v, 1)
        mid_f = 0.5 * (seg_f[0] + seg_f[-1])
        intercepts.append(float(np.polyval(coeffs, mid_f)))

    # Compare adjacent segments
    for s in range(len(intercepts) - 1):
        v_a, v_b = intercepts[s], intercepts[s + 1]
        if np.isnan(v_a) or np.isnan(v_b):
            continue
        mean_v = 0.5 * (abs(v_a) + abs(v_b))
        if mean_v < 1e-6:
            continue
        pct_change = abs(v_b - v_a) / mean_v * 100.0
        if pct_change > jump_threshold_pct:
            # Mark the boundary region
            boundary = (s + 1) * seg_len
            lo = max(0, boundary - 2)
            hi = min(n, boundary + 3)
            mask[lo:hi] = True
    return mask


def detect_mode_jump_standalone(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 7,
    jump_threshold_sigma: float = 2.5,
    min_consecutive: int = 3,
    n_segments: int = 4,
    jump_threshold_pct: float = 10.0,
) -> Dict[str, Any]:
    """Detect mode jumps without a reference curve.

    Combines three independent strategies:

    1. **Running-median deviation** — flags points that jump above the
       local running median by more than ``jump_threshold_sigma × MAD``.
    2. **Gradient reversal** — flags sustained positive dV/df regions
       at mid/high frequencies (distinct from low-f NF roll-off).
    3. **Segment discontinuity** — flags boundaries where adjacent
       curve segments have inconsistent velocity levels.

    A point is included in the ``consensus_mask`` if flagged by ≥ 2
    of the three strategies.

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays.
    smoothing_window : int
        Window for smoothing / median filter kernel.
    jump_threshold_sigma : float
        Sigma multiplier for the median-deviation strategy.
    min_consecutive : int
        Minimum consecutive flagged points for gradient-reversal.
    n_segments : int
        Number of segments for the discontinuity strategy.
    jump_threshold_pct : float
        Percentage velocity change to flag a segment boundary.

    Returns
    -------
    dict
        ``has_mode_jump`` — consensus detected a mode jump.
        ``jump_mask`` — boolean mask of consensus-flagged points.
        ``jump_indices`` — array of flagged indices.
        ``jump_frequencies`` — frequencies of flagged points.
        ``longest_run`` — longest consecutive flagged sequence.
        ``n_flagged`` — total number of flagged points.
        ``n_total`` — total number of valid points.
        ``detection_strategies`` — per-strategy boolean masks.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    valid = np.isfinite(f) & np.isfinite(v) & (f > 0) & (v > 0)
    f_v, v_v = f[valid], v[valid]

    _empty = {
        "has_mode_jump": False,
        "jump_mask": np.zeros(len(f), dtype=bool),
        "jump_indices": np.array([], dtype=int),
        "jump_frequencies": np.array([]),
        "longest_run": 0,
        "n_flagged": 0,
        "n_total": int(np.sum(valid)),
        "detection_strategies": {},
    }
    if len(f_v) < max(smoothing_window, 5):
        return _empty

    order = np.argsort(f_v)
    f_s, v_s = f_v[order], v_v[order]

    ks = smoothing_window if smoothing_window % 2 == 1 else smoothing_window + 1
    mask_median = _detect_median_deviation(
        f_s, v_s, kernel_size=ks, sigma_threshold=jump_threshold_sigma,
    )
    mask_grad = _detect_gradient_reversal(
        f_s, v_s, smoothing_window=smoothing_window, min_run=min_consecutive,
    )
    mask_seg = _detect_segment_discontinuity(
        f_s, v_s, n_segments=n_segments, jump_threshold_pct=jump_threshold_pct,
    )

    # Consensus: flagged by ≥ 2 strategies
    vote_count = mask_median.astype(int) + mask_grad.astype(int) + mask_seg.astype(int)
    consensus = vote_count >= 2

    indices = np.where(consensus)[0]
    longest = _longest_consecutive(indices)
    has_jump = longest >= min_consecutive

    # Map back to original (unsorted-valid) indexing
    full_mask = np.zeros(len(f), dtype=bool)
    valid_indices = np.where(valid)[0]
    sorted_valid_indices = valid_indices[order]
    full_mask[sorted_valid_indices[consensus]] = True

    return {
        "has_mode_jump": has_jump,
        "jump_mask": full_mask,
        "jump_indices": np.where(full_mask)[0],
        "jump_frequencies": f_s[consensus] if np.any(consensus) else np.array([]),
        "longest_run": longest,
        "n_flagged": int(np.sum(consensus)),
        "n_total": int(np.sum(valid)),
        "detection_strategies": {
            "median_deviation": mask_median,
            "gradient_reversal": mask_grad,
            "segment_discontinuity": mask_seg,
        },
    }
