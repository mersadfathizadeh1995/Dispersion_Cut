"""Pure near-field / NACD computation functions.

Implements x-bar-based NACD (Yoon & Rix 2009, Rahimi et al. 2022),
normalised phase velocity V_R, severity classification, and reference-
curve helpers.  No framework imports, no controller references.
"""
from __future__ import annotations

import pathlib
from typing import Iterable, List, Dict, Optional, Tuple, Union
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
    mean source-to-receiver distance (x_bar), consistent with the
    lambda-line criterion.  Otherwise falls back to the array aperture.

    NACD = x_bar / wavelength   (source_offset given)
    NACD = aperture / wavelength (no source_offset)

    Values below 1 typically indicate near-field contamination risk.
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


# ── V_R (Normalised Phase Velocity) functions ──────────────────────


def compute_normalized_vr(
    f_measured: np.ndarray,
    v_measured: np.ndarray,
    f_reference: np.ndarray,
    v_reference: np.ndarray,
) -> np.ndarray:
    """Compute V_R = V_measured / V_true for each measured point.

    The reference curve is linearly interpolated to the measured
    frequencies.  Points outside the reference frequency range are NaN.
    """
    f_m = np.asarray(f_measured, float)
    v_m = np.asarray(v_measured, float)
    f_r = np.asarray(f_reference, float)
    v_r = np.asarray(v_reference, float)

    sort = np.argsort(f_r)
    f_r, v_r = f_r[sort], v_r[sort]

    v_true = np.interp(f_m, f_r, v_r, left=np.nan, right=np.nan)
    v_true_safe = np.where(v_true > 0, v_true, np.nan)
    return v_m / v_true_safe


def compute_normalized_vr_with_validity(
    f_measured: np.ndarray,
    v_measured: np.ndarray,
    f_reference: np.ndarray,
    v_reference: np.ndarray,
    lambda_max_reference: float = np.inf,
) -> np.ndarray:
    """Compute V_R with reference validity masking.

    When the reference is itself an active-source offset, it is only
    reliable for wavelengths up to its own ``lambda_max``.  Points whose
    measured wavelength exceeds *lambda_max_reference* are set to NaN.
    Set ``lambda_max_reference=np.inf`` for passive / theoretical
    references that are valid everywhere.
    """
    vr = compute_normalized_vr(f_measured, v_measured, f_reference, v_reference)
    lam = np.asarray(v_measured, float) / np.maximum(np.asarray(f_measured, float), 1e-12)
    vr[lam > lambda_max_reference] = np.nan
    return vr


SEVERITY_LEVELS = ("clean", "marginal", "contaminated", "unknown")


def classify_nearfield_severity(
    vr: np.ndarray,
    clean_threshold: float = 0.95,
    marginal_threshold: float = 0.85,
    unknown_action: str = "unknown",
) -> np.ndarray:
    """Classify each point into near-field severity levels.

    *clean_threshold*: V_R >= this is clean.
    *marginal_threshold*: V_R >= this but < clean is marginal.
    *unknown_action*: what to label NaN points -- ``"unknown"``,
        ``"contaminated"``, or ``"exclude"``.
    """
    vr = np.asarray(vr, float)
    sev = np.full(vr.shape, "unknown", dtype="U15")
    sev[vr >= clean_threshold] = "clean"
    sev[(vr >= marginal_threshold) & (vr < clean_threshold)] = "marginal"
    sev[vr < marginal_threshold] = "contaminated"
    nan_mask = np.isnan(vr)
    if unknown_action == "contaminated":
        sev[nan_mask] = "contaminated"
    elif unknown_action == "exclude":
        sev[nan_mask] = "exclude"
    else:
        sev[nan_mask] = "unknown"
    return sev


# ── Reference curve helpers ────────────────────────────────────────


def select_reference_by_largest_xbar(
    source_offsets: List[float],
    receiver_positions: np.ndarray,
) -> int:
    """Return the index of the offset with the largest x-bar."""
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
) -> Tuple[np.ndarray, np.ndarray]:
    """Build a reference curve as the median (or mean) across offsets.

    When *source_offsets* and *receiver_positions* are provided, only
    data from offsets that are NF-clean (lambda < lambda_max) at each
    frequency bin are included, preventing contaminated data from
    biasing the reference.
    """
    from dc_cut.core.processing.wavelength_lines import compute_x_bar

    lambda_maxes: Optional[List[float]] = None
    if source_offsets is not None and receiver_positions is not None:
        recv = np.asarray(receiver_positions, float)
        lambda_maxes = [
            compute_x_bar(so, recv) / max(nacd_threshold, 1e-12)
            for so in source_offsets
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
            vals.extend(va[freq_mask].tolist())
        if vals:
            v_ref[k] = float(np.median(vals) if method == "median" else np.mean(vals))

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


# ── NF onset detection ─────────────────────────────────────────────


def detect_nearfield_onset(
    f_measured: np.ndarray,
    v_measured: np.ndarray,
    vr: np.ndarray,
    vr_threshold: float = 0.90,
) -> Dict[str, float]:
    """Find the frequency/wavelength where V_R first drops below threshold.

    Scans from high frequency (short lambda, clean) toward low frequency
    (long lambda, contaminated) and finds the transition point.
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


# ── Per-offset NF report ──────────────────────────────────────────


def compute_nearfield_report(
    frequency_arrays: List[np.ndarray],
    velocity_arrays: List[np.ndarray],
    source_offsets: List[float],
    receiver_positions: np.ndarray,
    nacd_threshold: float = 1.0,
    vr_threshold: float = 0.90,
    reference_index: Optional[int] = None,
    f_reference: Optional[np.ndarray] = None,
    v_reference: Optional[np.ndarray] = None,
    clean_threshold: float = 0.95,
    marginal_threshold: float = 0.85,
    unknown_action: str = "unknown",
) -> List[Dict]:
    """Compute complete NF diagnostic for every offset.

    Uses validity masking when the reference is itself an active offset.
    Returns a list of dicts, one per offset.
    """
    from dc_cut.core.processing.wavelength_lines import compute_x_bar, compute_lambda_max

    recv = np.asarray(receiver_positions, float)

    if f_reference is None or v_reference is None:
        if reference_index is None:
            reference_index = select_reference_by_largest_xbar(source_offsets, recv)
        f_reference = np.asarray(frequency_arrays[reference_index], float)
        v_reference = np.asarray(velocity_arrays[reference_index], float)
        lambda_max_ref = compute_lambda_max(
            source_offsets[reference_index], recv, nacd_threshold,
        )
    else:
        f_reference = np.asarray(f_reference, float)
        v_reference = np.asarray(v_reference, float)
        lambda_max_ref = np.inf

    results: List[Dict] = []
    for idx, (f_arr, v_arr, so) in enumerate(
        zip(frequency_arrays, velocity_arrays, source_offsets)
    ):
        f = np.asarray(f_arr, float)
        v = np.asarray(v_arr, float)
        x_bar = compute_x_bar(so, recv)
        lam_max = compute_lambda_max(so, recv, nacd_threshold)
        nacd = compute_nacd_array(recv, f, v, source_offset=so)
        vr = compute_normalized_vr_with_validity(
            f, v, f_reference, v_reference, lambda_max_ref,
        )
        severity = classify_nearfield_severity(
            vr, clean_threshold, marginal_threshold, unknown_action,
        )
        onset = detect_nearfield_onset(f, v, vr, vr_threshold)

        n_valid = max(int(np.sum(np.isfinite(vr))), 1)
        results.append({
            "index": idx,
            "source_offset": so,
            "x_bar": x_bar,
            "lambda_max": lam_max,
            "nacd": nacd,
            "vr": vr,
            "severity": severity,
            "onset_freq": onset["onset_freq"],
            "onset_wavelength": onset["onset_wavelength"],
            "clean_pct": float(np.sum(severity == "clean") / n_valid * 100),
            "marginal_pct": float(np.sum(severity == "marginal") / n_valid * 100),
            "contaminated_pct": float(np.sum(severity == "contaminated") / n_valid * 100),
            "is_reference": idx == reference_index,
        })

    return results


def prepare_nacd_vr_scatter(
    report: List[Dict],
) -> Dict[str, object]:
    """Flatten per-offset report into arrays for the NACD-vs-V_R scatter.

    Skips the reference offset (V_R = 1 by definition).
    """
    nacd_all, vr_all, ids = [], [], []
    offsets: List[float] = []
    labels: List[str] = []

    group = 0
    for entry in report:
        if entry.get("is_reference"):
            continue
        nacd = np.asarray(entry["nacd"], float)
        vr = np.asarray(entry["vr"], float)
        valid = np.isfinite(nacd) & np.isfinite(vr) & (nacd > 0)
        nacd_all.append(nacd[valid])
        vr_all.append(vr[valid])
        ids.append(np.full(int(np.sum(valid)), group, dtype=int))
        offsets.append(entry["source_offset"])
        labels.append(f"{entry['source_offset']:+g} m")
        group += 1

    return {
        "nacd_all": np.concatenate(nacd_all) if nacd_all else np.array([]),
        "vr_all": np.concatenate(vr_all) if vr_all else np.array([]),
        "offset_ids": np.concatenate(ids) if ids else np.array([], dtype=int),
        "offsets": offsets,
        "labels": labels,
    }
