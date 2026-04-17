"""Normalised phase-velocity ratio (V_R) computation and severity classification.

V_R = V_measured / V_true  (Rahimi et al. 2021, 2022).
Clean ≥ 0.95, Marginal ≥ 0.85, Contaminated < 0.85.

No framework imports, no controller references.
"""
from __future__ import annotations

import numpy as np

from dc_cut.core.processing.nearfield.constants import SEVERITY_LEVELS


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
    user_lambda_max: float | None = None,
) -> np.ndarray:
    """Compute V_R with reference validity masking.

    When the reference is itself an active-source offset, it is only
    reliable for wavelengths up to its own ``lambda_max``.  Points whose
    measured wavelength exceeds *lambda_max_reference* are set to NaN.
    Set ``lambda_max_reference=np.inf`` for passive / theoretical
    references that are valid everywhere.

    If *user_lambda_max* is provided it overrides *lambda_max_reference*
    for the validity mask entirely:

    * ``user_lambda_max > 0`` and finite -- apply that value as the cut;
    * ``user_lambda_max == inf`` -- disable the wavelength cap (useful
      when an :class:`~dc_cut.core.processing.nearfield.ranges.EvaluationRange`
      is already applied outside, making a duplicate ref-cap harmful);
    * ``user_lambda_max is None`` -- fall back to *lambda_max_reference*
      (legacy behaviour).

    Points that lie outside the reference's frequency support remain
    NaN because ``compute_normalized_vr`` already returns NaN there.
    """
    vr = compute_normalized_vr(f_measured, v_measured, f_reference, v_reference)
    lam = np.asarray(v_measured, float) / np.maximum(np.asarray(f_measured, float), 1e-12)
    if user_lambda_max is not None:
        lam_cut = float(user_lambda_max) if user_lambda_max > 0 else np.inf
    else:
        lam_cut = float(lambda_max_reference)
    if np.isfinite(lam_cut):
        vr[lam > lam_cut] = np.nan
    return vr


def classify_nearfield_severity(
    vr: np.ndarray,
    clean_threshold: float = 0.95,
    marginal_threshold: float = 0.85,
    unknown_action: str = "unknown",
) -> np.ndarray:
    """Classify each point into near-field severity levels.

    *clean_threshold*: V_R ≥ this is clean.
    *marginal_threshold*: V_R ≥ this but < clean is marginal.
    *unknown_action*: what to label NaN points — ``"unknown"``,
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
