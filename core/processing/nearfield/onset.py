"""Near-field onset detection and roll-off analysis.

Detects the frequency / wavelength where near-field effects begin,
either via V_R threshold crossing or curve geometry analysis.
Provides multiple roll-off detection methods (running-max, derivative,
curvature, V_R drop) plus a multi-method consensus wrapper.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np


def detect_nearfield_onset(
    f_measured: np.ndarray,
    v_measured: np.ndarray,
    vr: np.ndarray,
    vr_threshold: float = 0.90,
) -> Dict[str, float]:
    """Find the frequency/wavelength where V_R first drops below threshold.

    Scans from high frequency (short λ, clean) toward low frequency
    (long λ, contaminated) and finds the transition point.
    """
    f = np.asarray(f_measured, float)
    v = np.asarray(v_measured, float)
    vr_arr = np.asarray(vr, float)

    order = np.argsort(-f)
    f_s, v_s, vr_s = f[order], v[order], vr_arr[order]
    valid = np.isfinite(vr_s)

    onset_idx = None
    for i in range(len(vr_s)):
        if valid[i] and vr_s[i] < vr_threshold:
            onset_idx = i
            break

    if onset_idx is None:
        n_clean = int(np.sum(valid & (vr_s >= vr_threshold)))
        return {
            "onset_freq": np.nan,
            "onset_wavelength": np.nan,
            "onset_vr": np.nan,
            "clean_fraction": n_clean / max(int(np.sum(valid)), 1),
        }

    onset_f = float(f_s[onset_idx])
    onset_v = float(v_s[onset_idx])
    n_valid = int(np.sum(valid))
    n_clean = int(np.sum(valid & (vr_s >= vr_threshold)))

    return {
        "onset_freq": onset_f,
        "onset_wavelength": onset_v / max(onset_f, 1e-12),
        "onset_vr": float(vr_s[onset_idx]),
        "clean_fraction": n_clean / max(n_valid, 1),
    }


def detect_rolloff_point(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 5,
    min_drop: float = 0.05,
    domain: str = "frequency",
) -> Dict[str, float]:
    """Detect velocity roll-off using curve geometry only (no reference needed).

    Uses derivative analysis: finds where d(V)/d(f) changes sign and
    velocity systematically drops relative to its local maximum,
    indicating the onset of near-field effects.

    This is useful when no reference curve is available.

    Parameters
    ----------
    f : array
        Frequency values.
    v : array
        Phase velocity values.
    smoothing_window : int
        Moving average window for smoothing before derivative computation.
    min_drop : float
        Minimum fractional velocity drop (relative to local max) to
        trigger roll-off detection.
    domain : str
        ``"frequency"`` — scan from high to low frequency.
        ``"wavelength"`` — scan from short to long wavelength.

    Returns
    -------
    dict
        ``rolloff_freq`` — frequency where roll-off begins.
        ``rolloff_wavelength`` — corresponding wavelength.
        ``rolloff_velocity`` — velocity at roll-off point.
        ``confidence`` — 0–1 measure of detection reliability.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    valid = np.isfinite(f) & np.isfinite(v) & (f > 0) & (v > 0)
    f, v = f[valid], v[valid]

    if len(f) < smoothing_window + 2:
        return {
            "rolloff_freq": np.nan,
            "rolloff_wavelength": np.nan,
            "rolloff_velocity": np.nan,
            "confidence": 0.0,
        }

    # Sort by decreasing frequency (high freq = short λ = clean)
    order = np.argsort(-f)
    f_s = f[order]
    v_s = v[order]

    # Smooth
    if smoothing_window > 1:
        kernel = np.ones(smoothing_window) / smoothing_window
        v_smooth = np.convolve(v_s, kernel, mode="same")
    else:
        v_smooth = v_s.copy()

    # Track running maximum from the high-freq (clean) end
    v_max = np.maximum.accumulate(v_smooth)

    # Find where velocity drops below (1 - min_drop) × running max
    drop_frac = 1.0 - v_smooth / np.maximum(v_max, 1e-12)
    rolloff_candidates = np.where(drop_frac >= min_drop)[0]

    if len(rolloff_candidates) == 0:
        return {
            "rolloff_freq": np.nan,
            "rolloff_wavelength": np.nan,
            "rolloff_velocity": np.nan,
            "confidence": 0.0,
        }

    # Take the first sustained drop (require consecutive points)
    idx = rolloff_candidates[0]
    rolloff_f = float(f_s[idx])
    rolloff_v = float(v_s[idx])
    rolloff_lam = rolloff_v / max(rolloff_f, 1e-12)

    # Confidence: based on how many consecutive points are in drop zone
    consec = 0
    for i in range(idx, len(drop_frac)):
        if drop_frac[i] >= min_drop:
            consec += 1
        else:
            break
    confidence = min(1.0, consec / max(3, smoothing_window))

    return {
        "rolloff_freq": rolloff_f,
        "rolloff_wavelength": rolloff_lam,
        "rolloff_velocity": rolloff_v,
        "confidence": confidence,
    }


# ──────────────────────────────────────────────────────────────────
#  Standardised roll-off result helpers
# ──────────────────────────────────────────────────────────────────

_EMPTY_RESULT: Dict[str, Any] = {
    "method": "",
    "rolloff_freq": np.nan,
    "rolloff_wavelength": np.nan,
    "confidence": 0.0,
    "valid_freq_range": (np.nan, np.nan),
    "details": {},
}


def _make_result(
    method: str,
    rolloff_freq: float,
    rolloff_wavelength: float,
    confidence: float,
    f_sorted: np.ndarray,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a standardised roll-off result dict."""
    f_min = float(np.nanmin(f_sorted)) if len(f_sorted) > 0 else np.nan
    valid_hi = float(np.nanmax(f_sorted)) if len(f_sorted) > 0 else np.nan
    valid_lo = rolloff_freq if np.isfinite(rolloff_freq) else f_min
    return {
        "method": method,
        "rolloff_freq": float(rolloff_freq),
        "rolloff_wavelength": float(rolloff_wavelength),
        "confidence": float(confidence),
        "valid_freq_range": (valid_lo, valid_hi),
        "details": details or {},
    }


def _prepare_curve(
    f: np.ndarray,
    v: np.ndarray,
    smoothing_window: int = 1,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate, sort (descending f), and optionally smooth a curve.

    Returns
    -------
    f_sorted, v_sorted, v_smooth : arrays sorted by descending frequency.
    """
    f = np.asarray(f, float)
    v = np.asarray(v, float)
    valid = np.isfinite(f) & np.isfinite(v) & (f > 0) & (v > 0)
    f, v = f[valid], v[valid]
    order = np.argsort(-f)
    f_s, v_s = f[order], v[order]
    if smoothing_window > 1 and len(v_s) >= smoothing_window:
        kernel = np.ones(smoothing_window) / smoothing_window
        v_sm = np.convolve(v_s, kernel, mode="same")
    else:
        v_sm = v_s.copy()
    return f_s, v_s, v_sm


# ──────────────────────────────────────────────────────────────────
#  Individual roll-off detectors
# ──────────────────────────────────────────────────────────────────

def detect_rolloff_running_max(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 5,
    min_drop: float = 0.05,
) -> Dict[str, Any]:
    """Running-max roll-off detector (wrapper around ``detect_rolloff_point``).

    Scans from high to low frequency; flags where velocity drops below
    ``(1 - min_drop) × running_max``.  This is the original method.

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays.
    smoothing_window : int
        Moving-average window applied before analysis.
    min_drop : float
        Fractional drop threshold relative to the running maximum.

    Returns
    -------
    dict
        Standardised roll-off result.
    """
    raw = detect_rolloff_point(
        f, v, smoothing_window=smoothing_window, min_drop=min_drop,
    )
    rolloff_f = raw["rolloff_freq"]
    rolloff_lam = raw["rolloff_wavelength"]
    conf = raw["confidence"]
    f_s, _, _ = _prepare_curve(f, v)
    return _make_result(
        "running_max", rolloff_f, rolloff_lam, conf, f_s,
        details={"rolloff_velocity": raw["rolloff_velocity"]},
    )


def detect_rolloff_derivative(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 7,
    sign_run_threshold: int = 3,
) -> Dict[str, Any]:
    """Derivative-based roll-off detector.

    In a normal dispersion curve velocity *decreases* with increasing
    frequency (dV/df < 0).  Near-field contamination at low frequencies
    causes velocity to *increase* toward low f (dV/df becomes positive
    when scanning high→low).

    The detector scans from high frequency toward low frequency and
    looks for a sustained run of positive dV/df values (sign flip).

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays.
    smoothing_window : int
        Smoothing window before gradient computation.
    sign_run_threshold : int
        Minimum consecutive positive-gradient points to confirm roll-off.

    Returns
    -------
    dict
        Standardised roll-off result.
    """
    f_s, v_s, v_sm = _prepare_curve(f, v, smoothing_window)
    if len(f_s) < sign_run_threshold + 2:
        return _make_result("derivative", np.nan, np.nan, 0.0, f_s)

    # Gradient along the high→low-f direction (index increases → f decreases)
    dv = np.diff(v_sm)
    df = np.diff(f_s)
    grad = np.where(np.abs(df) > 1e-12, dv / df, 0.0)

    # In high→low-f order, normal dispersion has dV/df < 0.
    # NF roll-off makes velocity DROP → dV/df > 0 in this scan direction.
    # Actually when scanning high→low: f decreases, v normally increases,
    # so dV (= v[i+1]-v[i]) > 0 and df (= f[i+1]-f[i]) < 0 → dV/df < 0.
    # NF roll-off at low f: velocity drops → dV < 0 → dV/df > 0.
    positive_run = 0
    rolloff_idx = None
    for i in range(len(grad)):
        if grad[i] > 0:
            positive_run += 1
            if positive_run >= sign_run_threshold and rolloff_idx is None:
                rolloff_idx = i - sign_run_threshold + 1
        else:
            positive_run = 0

    if rolloff_idx is None:
        return _make_result("derivative", np.nan, np.nan, 0.0, f_s)

    rolloff_f = float(f_s[rolloff_idx])
    rolloff_v = float(v_s[rolloff_idx])
    rolloff_lam = rolloff_v / max(rolloff_f, 1e-12)
    conf = min(1.0, positive_run / max(5, sign_run_threshold))
    return _make_result(
        "derivative", rolloff_f, rolloff_lam, conf, f_s,
        details={"sign_run_length": positive_run},
    )


def detect_rolloff_curvature(
    f: np.ndarray,
    v: np.ndarray,
    *,
    smoothing_window: int = 7,
    curvature_percentile: float = 95.0,
) -> Dict[str, Any]:
    """Curvature-based roll-off detector.

    Finds the inflection point where |d²V/df²| is largest, indicating
    the sharpest transition in the dispersion curve.  Best for data
    with a distinct "knee" at the NF boundary.

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays.
    smoothing_window : int
        Smoothing window before curvature computation.
    curvature_percentile : float
        Percentile threshold for flagging high-curvature points.

    Returns
    -------
    dict
        Standardised roll-off result.
    """
    f_s, v_s, v_sm = _prepare_curve(f, v, smoothing_window)
    if len(f_s) < 5:
        return _make_result("curvature", np.nan, np.nan, 0.0, f_s)

    d2v = np.gradient(np.gradient(v_sm, f_s), f_s)
    abs_d2v = np.abs(d2v)

    threshold = np.percentile(abs_d2v, curvature_percentile)
    candidates = np.where(abs_d2v >= threshold)[0]

    if len(candidates) == 0:
        return _make_result("curvature", np.nan, np.nan, 0.0, f_s)

    # Pick the candidate at the lowest frequency (deepest into NF region)
    # among those in the lower half of the frequency range
    mid_idx = len(f_s) // 2
    low_f_candidates = candidates[candidates >= mid_idx]
    if len(low_f_candidates) > 0:
        best = low_f_candidates[np.argmax(abs_d2v[low_f_candidates])]
    else:
        best = candidates[np.argmax(abs_d2v[candidates])]

    rolloff_f = float(f_s[best])
    rolloff_v = float(v_s[best])
    rolloff_lam = rolloff_v / max(rolloff_f, 1e-12)

    peak_curvature = float(abs_d2v[best])
    median_curvature = float(np.median(abs_d2v))
    conf = min(1.0, peak_curvature / max(median_curvature * 5, 1e-12))

    return _make_result(
        "curvature", rolloff_f, rolloff_lam, conf, f_s,
        details={
            "peak_curvature": peak_curvature,
            "median_curvature": median_curvature,
        },
    )


def detect_rolloff_vr_drop(
    f: np.ndarray,
    v: np.ndarray,
    f_ref: np.ndarray,
    v_ref: np.ndarray,
    *,
    vr_threshold: float = 0.95,
    min_consecutive: int = 2,
) -> Dict[str, Any]:
    """V_R-drop roll-off detector.  Requires a reference curve.

    Computes V_R = V_measured / V_reference and scans from high to low
    frequency, flagging where V_R first drops below *vr_threshold*.

    Parameters
    ----------
    f, v : array
        Measured frequency and phase-velocity.
    f_ref, v_ref : array
        Reference curve.
    vr_threshold : float
        V_R value below which roll-off is declared.
    min_consecutive : int
        Minimum consecutive sub-threshold points to confirm.

    Returns
    -------
    dict
        Standardised roll-off result.
    """
    f_m = np.asarray(f, float)
    v_m = np.asarray(v, float)
    f_r = np.asarray(f_ref, float)
    v_r = np.asarray(v_ref, float)

    valid = np.isfinite(f_m) & np.isfinite(v_m) & (f_m > 0) & (v_m > 0)
    f_m, v_m = f_m[valid], v_m[valid]
    order = np.argsort(-f_m)
    f_s, v_s = f_m[order], v_m[order]

    if len(f_s) < min_consecutive + 1:
        return _make_result("vr_drop", np.nan, np.nan, 0.0, f_s)

    sort_r = np.argsort(f_r)
    v_interp = np.interp(f_s, f_r[sort_r], v_r[sort_r], left=np.nan, right=np.nan)
    vr = np.where(
        np.isfinite(v_interp) & (v_interp > 0), v_s / v_interp, np.nan,
    )

    run = 0
    rolloff_idx = None
    for i in range(len(vr)):
        if np.isfinite(vr[i]) and vr[i] < vr_threshold:
            run += 1
            if run >= min_consecutive and rolloff_idx is None:
                rolloff_idx = i - min_consecutive + 1
        else:
            run = 0

    if rolloff_idx is None:
        return _make_result("vr_drop", np.nan, np.nan, 0.0, f_s)

    rolloff_f = float(f_s[rolloff_idx])
    rolloff_v = float(v_s[rolloff_idx])
    rolloff_lam = rolloff_v / max(rolloff_f, 1e-12)
    vr_at_rolloff = float(vr[rolloff_idx]) if np.isfinite(vr[rolloff_idx]) else 0.0
    conf = min(1.0, run / max(4, min_consecutive))

    return _make_result(
        "vr_drop", rolloff_f, rolloff_lam, conf, f_s,
        details={"vr_at_rolloff": vr_at_rolloff, "run_length": run},
    )


# ──────────────────────────────────────────────────────────────────
#  Multi-method and general wrapper
# ──────────────────────────────────────────────────────────────────

ROLLOFF_METHODS = ("running_max", "derivative", "curvature", "vr_drop")


def detect_rolloff_multi_method(
    f: np.ndarray,
    v: np.ndarray,
    *,
    f_ref: Optional[np.ndarray] = None,
    v_ref: Optional[np.ndarray] = None,
    methods: Optional[List[str]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Run multiple roll-off detectors and return per-method + consensus.

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays.
    f_ref, v_ref : array, optional
        Reference curve (needed for ``"vr_drop"`` method).
    methods : list of str, optional
        Which methods to run.  ``None`` → all applicable methods.
    **kwargs
        Forwarded to individual detectors (e.g. ``smoothing_window``).

    Returns
    -------
    dict
        ``per_method`` — dict mapping method name → result dict.
        ``consensus_rolloff_freq`` — median frequency across successful detections.
        ``consensus_rolloff_wavelength`` — median wavelength.
        ``consensus_confidence`` — mean confidence of successful detections.
        ``n_methods_detected`` — how many methods found a roll-off.
    """
    if methods is None:
        methods = list(ROLLOFF_METHODS)

    has_ref = (
        f_ref is not None
        and v_ref is not None
        and len(np.asarray(f_ref)) > 0
    )
    if not has_ref and "vr_drop" in methods:
        methods = [m for m in methods if m != "vr_drop"]

    per_method: Dict[str, Dict[str, Any]] = {}
    for m in methods:
        if m == "running_max":
            per_method[m] = detect_rolloff_running_max(f, v, **{
                kk: vv for kk, vv in kwargs.items()
                if kk in ("smoothing_window", "min_drop")
            })
        elif m == "derivative":
            per_method[m] = detect_rolloff_derivative(f, v, **{
                kk: vv for kk, vv in kwargs.items()
                if kk in ("smoothing_window", "sign_run_threshold")
            })
        elif m == "curvature":
            per_method[m] = detect_rolloff_curvature(f, v, **{
                kk: vv for kk, vv in kwargs.items()
                if kk in ("smoothing_window", "curvature_percentile")
            })
        elif m == "vr_drop" and has_ref:
            per_method[m] = detect_rolloff_vr_drop(f, v, f_ref, v_ref, **{
                kk: vv for kk, vv in kwargs.items()
                if kk in ("vr_threshold", "min_consecutive")
            })

    freqs = [
        r["rolloff_freq"] for r in per_method.values()
        if np.isfinite(r["rolloff_freq"])
    ]
    lams = [
        r["rolloff_wavelength"] for r in per_method.values()
        if np.isfinite(r["rolloff_wavelength"])
    ]
    confs = [
        r["confidence"] for r in per_method.values()
        if r["confidence"] > 0
    ]

    return {
        "per_method": per_method,
        "consensus_rolloff_freq": float(np.median(freqs)) if freqs else np.nan,
        "consensus_rolloff_wavelength": float(np.median(lams)) if lams else np.nan,
        "consensus_confidence": float(np.mean(confs)) if confs else 0.0,
        "n_methods_detected": len(freqs),
    }


def compute_valid_range(
    f: np.ndarray,
    v: np.ndarray,
    *,
    method: str = "running_max",
    f_ref: Optional[np.ndarray] = None,
    v_ref: Optional[np.ndarray] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """General-purpose wrapper: compute the reliable frequency range for any curve.

    Parameters
    ----------
    f, v : array
        Frequency and phase-velocity arrays (any curve — reference, offset, composite).
    method : str
        One of ``"running_max"``, ``"derivative"``, ``"curvature"``,
        ``"vr_drop"``, or ``"multi"`` (consensus of all applicable).
    f_ref, v_ref : array, optional
        Reference curve, required only for ``"vr_drop"`` or ``"multi"``.
    **kwargs
        Forwarded to the chosen detector.

    Returns
    -------
    dict
        Standardised result (single method) or multi-method result.
    """
    if method == "multi":
        return detect_rolloff_multi_method(
            f, v, f_ref=f_ref, v_ref=v_ref, **kwargs,
        )
    if method == "running_max":
        return detect_rolloff_running_max(f, v, **kwargs)
    if method == "derivative":
        return detect_rolloff_derivative(f, v, **kwargs)
    if method == "curvature":
        return detect_rolloff_curvature(f, v, **kwargs)
    if method == "vr_drop":
        if f_ref is None or v_ref is None:
            raise ValueError("vr_drop method requires f_ref and v_ref")
        return detect_rolloff_vr_drop(f, v, f_ref, v_ref, **kwargs)
    raise ValueError(f"Unknown roll-off method: {method!r}")
