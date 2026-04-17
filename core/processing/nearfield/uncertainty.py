"""V_R uncertainty propagation.

Computes V_R with error bars via first-order error propagation:
    σ(V_R) = V_R × √((σ_m/V_m)² + (σ_r/V_r)²)

Conservative severity classification uses V_R − σ(V_R) for
boundary decisions (marginal-to-contaminated).

Rahimi et al. (2022) discussion on variability (σ ≈ 0.28–0.45).

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Tuple, Union
import numpy as np


def compute_vr_with_uncertainty(
    f_measured: np.ndarray,
    v_measured: np.ndarray,
    sigma_v_measured: Union[np.ndarray, float],
    f_ref: np.ndarray,
    v_ref: np.ndarray,
    sigma_v_ref: Union[np.ndarray, float] = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute V_R and its uncertainty via first-order error propagation.

    Parameters
    ----------
    f_measured : array
        Measured frequencies.
    v_measured : array
        Measured velocities.
    sigma_v_measured : array or float
        Uncertainty in measured velocities.
    f_ref : array
        Reference curve frequencies.
    v_ref : array
        Reference curve velocities.
    sigma_v_ref : array or float
        Uncertainty in reference velocities (0 for theoretical refs).

    Returns
    -------
    vr : array
        V_R = V_measured / V_reference.
    sigma_vr : array
        σ(V_R) via error propagation.
    """
    f_m = np.asarray(f_measured, float)
    v_m = np.asarray(v_measured, float)
    sigma_m = np.broadcast_to(np.asarray(sigma_v_measured, float), v_m.shape).copy()

    # Interpolate reference
    f_r = np.asarray(f_ref, float)
    v_r = np.asarray(v_ref, float)
    sort = np.argsort(f_r)
    v_true = np.interp(f_m, f_r[sort], v_r[sort], left=np.nan, right=np.nan)

    # Interpolate reference uncertainty
    sigma_r = np.broadcast_to(np.asarray(sigma_v_ref, float), v_r.shape).copy()
    sigma_true = np.interp(f_m, f_r[sort], sigma_r[sort], left=0.0, right=0.0)

    v_true_safe = np.where(v_true > 0, v_true, np.nan)
    vr = v_m / v_true_safe

    # Error propagation: σ(V_R) = V_R × √((σ_m/V_m)² + (σ_r/V_r)²)
    rel_m = np.where(v_m > 0, sigma_m / v_m, 0.0)
    rel_r = np.where(v_true_safe > 0, sigma_true / v_true_safe, 0.0)
    sigma_vr = np.abs(vr) * np.sqrt(rel_m**2 + rel_r**2)

    return vr, sigma_vr


def classify_nearfield_severity_with_uncertainty(
    vr: np.ndarray,
    sigma_vr: np.ndarray,
    clean_threshold: float = 0.95,
    marginal_threshold: float = 0.85,
    conservative: bool = True,
) -> np.ndarray:
    """Classify severity using uncertainty-aware boundaries.

    When *conservative* is True, uses ``V_R − σ(V_R)`` for threshold
    comparisons.  This means a point must be confidently clean to be
    labelled clean — uncertainty pushes classification toward
    contaminated.

    Parameters
    ----------
    vr : array
        V_R values.
    sigma_vr : array
        σ(V_R) values.
    clean_threshold, marginal_threshold : float
        Standard severity thresholds.
    conservative : bool
        If True, use lower confidence bound for classification.

    Returns
    -------
    array of str
        Severity labels.
    """
    vr = np.asarray(vr, float)
    sigma_vr = np.asarray(sigma_vr, float)

    if conservative:
        vr_eff = vr - sigma_vr
    else:
        vr_eff = vr

    sev = np.full(vr.shape, "unknown", dtype="U15")
    sev[vr_eff >= clean_threshold] = "clean"
    sev[(vr_eff >= marginal_threshold) & (vr_eff < clean_threshold)] = "marginal"
    sev[vr_eff < marginal_threshold] = "contaminated"
    sev[np.isnan(vr)] = "unknown"
    return sev
