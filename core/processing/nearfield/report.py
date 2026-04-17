"""Per-offset near-field diagnostic report and scatter data preparation.

Combines NACD, V_R, onset detection, and severity classification
into a single per-offset summary suitable for display or export.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np

from dc_cut.core.processing.nearfield.nacd import compute_nacd_array
from dc_cut.core.processing.nearfield.normalized_vr import (
    compute_normalized_vr_with_validity,
    classify_nearfield_severity,
)
from dc_cut.core.processing.nearfield.reference import select_reference_by_largest_xbar
from dc_cut.core.processing.nearfield.onset import detect_nearfield_onset


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
