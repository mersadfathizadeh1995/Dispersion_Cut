"""Analysis operations: averages, near-field, statistics.

Wraps core processing functions with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Iterable

import numpy as np

from dc_cut.api.config import AverageConfig, NearFieldConfig


def compute_averages(
    velocity_arrays: List[np.ndarray],
    domain_arrays: List[np.ndarray],
    config: AverageConfig,
) -> Dict[str, Any]:
    """Compute binned averages across offsets.

    Returns {"success": bool, "errors": [...], "bin_centers": ..., "avg": ..., "std": ...}
    """
    try:
        v_all = np.concatenate(velocity_arrays)
        d_all = np.concatenate(domain_arrays)

        if v_all.size == 0:
            return {"success": False, "errors": ["No data points to average."]}

        if config.domain == "frequency":
            from dc_cut.core.processing.averages import compute_binned_avg_std
            centers, avg, std = compute_binned_avg_std(
                d_all, v_all,
                num_bins=config.num_bins,
                log_bias=config.log_bias,
            )
        else:
            from dc_cut.core.processing.averages import compute_binned_avg_std_wavelength
            centers, avg, std = compute_binned_avg_std_wavelength(
                d_all, v_all,
                num_bins=config.num_bins,
                log_bias=config.log_bias,
            )

        return {
            "success": True,
            "errors": [],
            "bin_centers": centers,
            "avg": avg,
            "std": std,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def compute_nacd(
    velocity: np.ndarray,
    frequency: np.ndarray,
    array_positions: Iterable[float],
    config: NearFieldConfig,
    *,
    source_offset: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute NACD values for a set of picks.

    When *source_offset* is provided, uses x̄-based NACD (paper-correct).
    Otherwise falls back to aperture-based NACD with a note in errors.

    Returns {"success": bool, "errors": [...], "nacd": ..., "nearfield_mask": ...}
    """
    try:
        from dc_cut.core.processing.nearfield import compute_nacd_array
        from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold

        if not hasattr(array_positions, '__len__') or len(list(array_positions)) < 2:
            arr_pos = np.arange(0, config.receiver_dx * config.n_phones, config.receiver_dx)
        else:
            arr_pos = np.asarray(list(array_positions), float)

        # Resolve threshold from source-type criteria
        threshold = resolve_nacd_threshold(
            source_type=config.source_type,
            error_level=config.error_level,
            transform=config.transform,
        )

        nacd = compute_nacd_array(arr_pos, frequency, velocity, source_offset=source_offset)
        mask = nacd < threshold

        warnings: list[str] = []
        if source_offset is None:
            warnings.append("No source_offset — using aperture-based NACD (less accurate).")

        return {
            "success": True,
            "errors": warnings,
            "nacd": nacd,
            "nearfield_mask": mask,
            "nearfield_count": int(np.sum(mask)),
            "threshold_used": threshold,
            "source_type": config.source_type,
            "error_level": config.error_level,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


# ── Phase 6: New API operations ────────────────────────────────────


def compute_nearfield_report_api(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    config: NearFieldConfig,
    receiver_positions: np.ndarray,
    *,
    f_reference: Optional[np.ndarray] = None,
    v_reference: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Compute per-offset NF diagnostic report via the API layer.

    Wraps ``compute_nearfield_report()`` with config-driven defaults.

    Returns {"success": bool, "errors": [...], "report": [...], "reference_index": int}
    """
    try:
        from dc_cut.core.processing.nearfield.report import compute_nearfield_report
        from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold

        recv = np.asarray(receiver_positions, float)
        offsets = config.source_offsets
        if offsets is None or len(offsets) != len(velocity_arrays):
            return {"success": False, "errors": ["source_offsets must match velocity_arrays length."]}

        threshold = resolve_nacd_threshold(
            source_type=config.source_type,
            error_level=config.error_level,
            transform=config.transform,
        )

        report = compute_nearfield_report(
            frequency_arrays=frequency_arrays,
            velocity_arrays=velocity_arrays,
            source_offsets=offsets,
            receiver_positions=recv,
            nacd_threshold=threshold,
            vr_threshold=config.vr_onset_threshold,
            reference_index=config.reference_index,
            f_reference=f_reference,
            v_reference=v_reference,
            clean_threshold=config.vr_clean_threshold,
            marginal_threshold=config.vr_marginal_threshold,
        )

        ref_idx = next((e["index"] for e in report if e.get("is_reference")), None)

        return {
            "success": True,
            "errors": [],
            "report": report,
            "reference_index": ref_idx,
            "threshold_used": threshold,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def compute_nacd_vr_scatter(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    config: NearFieldConfig,
    receiver_positions: np.ndarray,
) -> Dict[str, Any]:
    """Compute NACD-vs-V_R scatter data for all offsets.

    Returns {"success": bool, "errors": [...], "scatter_data": {...}}
    """
    try:
        result = compute_nearfield_report_api(
            velocity_arrays, frequency_arrays, config, receiver_positions,
        )
        if not result["success"]:
            return result

        from dc_cut.core.processing.nearfield.report import prepare_nacd_vr_scatter
        scatter = prepare_nacd_vr_scatter(result["report"])
        return {
            "success": True,
            "errors": [],
            "scatter_data": scatter,
            "threshold_used": result["threshold_used"],
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def build_nf_clean_composite(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    config: NearFieldConfig,
    receiver_positions: np.ndarray,
) -> Dict[str, Any]:
    """Build an NF-clean composite dispersion curve for inversion.

    Returns {"success": bool, "errors": [...], "composite": {...}}
    """
    try:
        from dc_cut.core.processing.nearfield.composite_curve import build_nf_clean_composite_curve
        from dc_cut.core.processing.nearfield.criteria import resolve_nacd_threshold

        recv = np.asarray(receiver_positions, float)
        offsets = config.source_offsets
        if offsets is None or len(offsets) != len(velocity_arrays):
            return {"success": False, "errors": ["source_offsets must match velocity_arrays length."]}

        threshold = resolve_nacd_threshold(
            source_type=config.source_type,
            error_level=config.error_level,
            transform=config.transform,
        )

        composite = build_nf_clean_composite_curve(
            frequency_arrays=frequency_arrays,
            velocity_arrays=velocity_arrays,
            source_offsets=offsets,
            receiver_positions=recv,
            nacd_threshold=threshold,
            source_type=config.source_type,
        )

        return {"success": True, "errors": [], "composite": composite}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def export_nearfield_report(
    report: List[Dict],
    output_path: str,
    *,
    fmt: str = "csv",
) -> Dict[str, Any]:
    """Export NF report to file.

    Parameters
    ----------
    report : list of dict
        Output of ``compute_nearfield_report()``.
    output_path : str
        Destination file path.
    fmt : str
        ``"csv"``, ``"json"``, or ``"ascii"``.

    Returns {"success": bool, "errors": [...], "path": str}
    """
    try:
        from dc_cut.core.processing.nearfield.report_io import (
            save_nearfield_report_csv,
            save_nearfield_report_json,
            format_nearfield_report_table,
        )
        if fmt == "csv":
            path = save_nearfield_report_csv(report, output_path)
        elif fmt == "json":
            path = save_nearfield_report_json(report, output_path)
        elif fmt == "ascii":
            text = format_nearfield_report_table(report)
            from pathlib import Path
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            path = str(p.resolve())
        else:
            return {"success": False, "errors": [f"Unknown format: {fmt}"]}

        return {"success": True, "errors": [], "path": path}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def calibrate_site_nacd(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    config: NearFieldConfig,
    receiver_positions: np.ndarray,
) -> Dict[str, Any]:
    """Calibrate site-specific NACD threshold from scatter data.

    Returns {"success": bool, "errors": [...], "calibration": {...}}
    """
    try:
        result = compute_nearfield_report_api(
            velocity_arrays, frequency_arrays, config, receiver_positions,
        )
        if not result["success"]:
            return result

        from dc_cut.core.processing.nearfield.calibration import recommend_site_nacd_threshold
        cal = recommend_site_nacd_threshold(
            result["report"],
            vr_threshold=config.vr_onset_threshold,
        )
        return {"success": True, "errors": [], "calibration": cal}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}
