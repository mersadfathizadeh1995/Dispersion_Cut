"""Near-field analysis sub-package for DC Cut.

Re-exports all public symbols from the sub-modules so that existing
``from dc_cut.core.processing.nearfield import ...`` statements keep
working unchanged.

Sub-modules
-----------
nacd            NACD computation (x̄/λ)
normalized_vr   V_R = V_measured / V_true and severity classification
reference       Reference curve selection, composite, file loading
onset           Near-field onset detection
report          Per-offset diagnostic report and scatter data
constants       Shared constants and severity levels
criteria        Source-type-aware NACD thresholds (Phase 1)
calibration     Site-specific NACD calibration (Phase 2)
composite_curve NF-clean composite dispersion curve (Phase 2)
far_field       Far-field attenuation sanity check (Phase 2)
mode_detection  Higher-mode / mode-kissing flagging (Phase 3)
uncertainty     V_R uncertainty propagation (Phase 4)
report_io       Report export helpers (Phase 5)
"""
from __future__ import annotations

# ── nacd.py ────────────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.nacd import (
    compute_nacd,
    compute_nacd_array,
    compute_nacd_for_all_data,
    detect_nearfield_picks,
)

# ── normalized_vr.py ───────────────────────────────────────────────
from dc_cut.core.processing.nearfield.normalized_vr import (
    compute_normalized_vr,
    compute_normalized_vr_with_validity,
    classify_nearfield_severity,
)

# ── ranges.py ──────────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.ranges import (
    EvaluationRange,
    compute_range_mask,
    reference_coverage_warnings,
)

# ── range_derivation.py ────────────────────────────────────────────
from dc_cut.core.processing.nearfield.range_derivation import (
    DerivedLine,
    DerivedLimitSet,
    derive_limits,
)

# ── reference.py ───────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.reference import (
    select_reference_by_largest_xbar,
    compute_composite_reference,
    load_reference_curve,
)

# ── onset.py ───────────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.onset import (
    detect_nearfield_onset,
    detect_rolloff_point,
    detect_rolloff_running_max,
    detect_rolloff_derivative,
    detect_rolloff_curvature,
    detect_rolloff_vr_drop,
    detect_rolloff_multi_method,
    compute_valid_range,
    ROLLOFF_METHODS,
)

# ── report.py ──────────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.report import (
    compute_nearfield_report,
    prepare_nacd_vr_scatter,
)

# ── calibration.py ─────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.calibration import (
    fit_nacd_cutoff_from_scatter,
    recommend_site_nacd_threshold,
)

# ── composite_curve.py ─────────────────────────────────────────────
from dc_cut.core.processing.nearfield.composite_curve import (
    build_nf_clean_composite_curve,
)

# ── far_field.py ───────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.far_field import (
    assess_far_field_risk,
    assess_far_field_risk_batch,
)

# ── mode_detection.py ──────────────────────────────────────────────
from dc_cut.core.processing.nearfield.mode_detection import (
    detect_mode_jump,
    detect_mode_jump_standalone,
    detect_mode_kissing,
)

# ── uncertainty.py ─────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.uncertainty import (
    compute_vr_with_uncertainty,
    classify_nearfield_severity_with_uncertainty,
)

# ── report_io.py ───────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.report_io import (
    format_nearfield_report_table,
    save_nearfield_report_csv,
    save_nearfield_report_json,
    save_nacd_vr_scatter_npz,
)

# ── constants.py ───────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.constants import (
    SEVERITY_LEVELS,
    DEFAULT_VR_CLEAN_THRESHOLD,
    DEFAULT_VR_MARGINAL_THRESHOLD,
    DEFAULT_VR_ONSET_THRESHOLD,
    DEFAULT_NACD_THRESHOLD,
)

# ── criteria.py ────────────────────────────────────────────────────
from dc_cut.core.processing.nearfield.criteria import (
    NACD_CRITERIA,
    SOURCE_TYPE_LABELS,
    ERROR_LEVEL_LABELS,
    TRANSFORM_NF_MULTIPLIER,
    TRANSFORM_LABELS,
    resolve_nacd_threshold,
    get_nacd_sigma,
    parse_transform_from_label,
)

__all__ = [
    # nacd
    "compute_nacd",
    "compute_nacd_array",
    "compute_nacd_for_all_data",
    "detect_nearfield_picks",
    # normalized_vr
    "compute_normalized_vr",
    "compute_normalized_vr_with_validity",
    "classify_nearfield_severity",
    # ranges
    "EvaluationRange",
    "compute_range_mask",
    "reference_coverage_warnings",
    # range_derivation
    "DerivedLine",
    "DerivedLimitSet",
    "derive_limits",
    # reference
    "select_reference_by_largest_xbar",
    "compute_composite_reference",
    "load_reference_curve",
    # onset
    "detect_nearfield_onset",
    "detect_rolloff_point",
    "detect_rolloff_running_max",
    "detect_rolloff_derivative",
    "detect_rolloff_curvature",
    "detect_rolloff_vr_drop",
    "detect_rolloff_multi_method",
    "compute_valid_range",
    "ROLLOFF_METHODS",
    # report
    "compute_nearfield_report",
    "prepare_nacd_vr_scatter",
    # calibration
    "fit_nacd_cutoff_from_scatter",
    "recommend_site_nacd_threshold",
    # composite_curve
    "build_nf_clean_composite_curve",
    # far_field
    "assess_far_field_risk",
    "assess_far_field_risk_batch",
    # constants
    "SEVERITY_LEVELS",
    "DEFAULT_VR_CLEAN_THRESHOLD",
    "DEFAULT_VR_MARGINAL_THRESHOLD",
    "DEFAULT_VR_ONSET_THRESHOLD",
    "DEFAULT_NACD_THRESHOLD",
    # criteria
    "NACD_CRITERIA",
    "SOURCE_TYPE_LABELS",
    "ERROR_LEVEL_LABELS",
    "TRANSFORM_NF_MULTIPLIER",
    "TRANSFORM_LABELS",
    "resolve_nacd_threshold",
    "get_nacd_sigma",
    "parse_transform_from_label",
    # mode_detection
    "detect_mode_jump",
    "detect_mode_jump_standalone",
    "detect_mode_kissing",
    # uncertainty
    "compute_vr_with_uncertainty",
    "classify_nearfield_severity_with_uncertainty",
    # report_io
    "format_nearfield_report_table",
    "save_nearfield_report_csv",
    "save_nearfield_report_json",
    "save_nacd_vr_scatter_npz",
]
