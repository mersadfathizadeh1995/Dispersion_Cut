"""Site-specific NACD calibration from NACD-vs-V_R scatter data.

The standard NACD thresholds (1.0 for sledgehammer, 0.5 for vibroseis)
have σ ≈ 0.3, meaning they can vary ±30% across sites.  This module
provides empirical fitting of site-specific thresholds from the
scatter plot data.

Rahimi et al. (2022) Section 4.3.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np


def fit_nacd_cutoff_from_scatter(
    nacd: np.ndarray,
    vr: np.ndarray,
    vr_threshold: float = 0.90,
    method: str = "percentile",
) -> Dict[str, float]:
    """Fit site-specific NACD cutoff from NACD-vs-V_R scatter data.

    Parameters
    ----------
    nacd : array
        NACD values (all offsets concatenated).
    vr : array
        Corresponding V_R values.
    vr_threshold : float
        V_R below this is considered contaminated.
    method : str
        ``"percentile"`` — find NACD value where P(V_R < threshold)
        drops below 10%.
        ``"logistic"`` — fit a logistic transition curve.

    Returns
    -------
    dict
        ``nacd_cutoff``  — the empirical NACD threshold for this site.
        ``confidence_lower``, ``confidence_upper`` — ±1σ bounds.
        ``n_points`` — total data points used.
        ``contaminated_fraction`` — fraction below V_R threshold.
    """
    nacd = np.asarray(nacd, float)
    vr = np.asarray(vr, float)
    valid = np.isfinite(nacd) & np.isfinite(vr) & (nacd > 0)
    nacd, vr = nacd[valid], vr[valid]

    if nacd.size < 5:
        return {
            "nacd_cutoff": np.nan,
            "confidence_lower": np.nan,
            "confidence_upper": np.nan,
            "n_points": int(nacd.size),
            "contaminated_fraction": np.nan,
            "method": method,
        }

    contaminated = vr < vr_threshold
    contam_frac = float(np.sum(contaminated) / nacd.size)

    if method == "logistic":
        cutoff = _fit_logistic_cutoff(nacd, vr, vr_threshold)
    else:
        cutoff = _fit_percentile_cutoff(nacd, contaminated)

    # Estimate uncertainty via bootstrap
    rng = np.random.default_rng(42)
    n_boot = 200
    cutoffs = np.full(n_boot, np.nan)
    for b in range(n_boot):
        idx = rng.integers(0, nacd.size, nacd.size)
        n_b, v_b = nacd[idx], vr[idx]
        c_b = v_b < vr_threshold
        try:
            cutoffs[b] = _fit_percentile_cutoff(n_b, c_b)
        except Exception:
            pass

    valid_boots = cutoffs[np.isfinite(cutoffs)]
    if valid_boots.size >= 10:
        ci_lo = float(np.percentile(valid_boots, 16))
        ci_hi = float(np.percentile(valid_boots, 84))
    else:
        ci_lo = ci_hi = cutoff

    return {
        "nacd_cutoff": float(cutoff),
        "confidence_lower": ci_lo,
        "confidence_upper": ci_hi,
        "n_points": int(nacd.size),
        "contaminated_fraction": contam_frac,
        "method": method,
    }


def _fit_percentile_cutoff(
    nacd: np.ndarray,
    contaminated: np.ndarray,
    contamination_rate: float = 0.10,
) -> float:
    """Find NACD where contamination rate drops below threshold.

    Scans NACD from low to high, computing the fraction of points
    with V_R < threshold at each NACD level.  Returns the NACD
    value where the contamination rate first drops below the target.
    """
    order = np.argsort(nacd)
    nacd_s = nacd[order]
    contam_s = contaminated[order]

    n = len(nacd_s)
    # Sliding window: for each cutoff, what fraction above it is contaminated?
    n_candidates = min(50, n)
    test_cutoffs = np.linspace(float(nacd_s[0]), float(nacd_s[-1]), n_candidates)

    for cutoff in test_cutoffs:
        above = nacd_s >= cutoff
        if np.sum(above) < 3:
            continue
        rate = float(np.sum(contam_s[above]) / np.sum(above))
        if rate <= contamination_rate:
            return float(cutoff)

    # Fallback: median NACD of contaminated points
    if np.any(contaminated):
        return float(np.median(nacd[contaminated]))
    return float(np.median(nacd))


def _fit_logistic_cutoff(
    nacd: np.ndarray,
    vr: np.ndarray,
    vr_threshold: float,
) -> float:
    """Fit logistic curve to P(clean | NACD) and find 50% crossing."""
    try:
        # Binary labels: 1 = clean, 0 = contaminated
        y = (vr >= vr_threshold).astype(float)
        log_nacd = np.log10(np.maximum(nacd, 1e-6))

        # Simple logistic regression via least-squares on log-odds
        clean_frac_by_bin = []
        bins = np.linspace(log_nacd.min(), log_nacd.max(), 20)
        centers = []
        for i in range(len(bins) - 1):
            mask = (log_nacd >= bins[i]) & (log_nacd < bins[i + 1])
            if np.sum(mask) >= 3:
                clean_frac_by_bin.append(float(np.mean(y[mask])))
                centers.append(float((bins[i] + bins[i + 1]) / 2))

        if len(centers) < 3:
            return _fit_percentile_cutoff(nacd, vr < vr_threshold)

        # Find where clean fraction crosses 0.5
        fracs = np.array(clean_frac_by_bin)
        ctrs = np.array(centers)
        for i in range(len(fracs) - 1):
            if fracs[i] <= 0.5 <= fracs[i + 1]:
                # Linear interpolation
                t = (0.5 - fracs[i]) / max(fracs[i + 1] - fracs[i], 1e-12)
                return float(10 ** (ctrs[i] + t * (ctrs[i + 1] - ctrs[i])))

        # Fallback
        return _fit_percentile_cutoff(nacd, vr < vr_threshold)
    except Exception:
        return _fit_percentile_cutoff(nacd, vr < vr_threshold)


def recommend_site_nacd_threshold(
    report: List[Dict],
    vr_threshold: float = 0.90,
    method: str = "percentile",
) -> Dict[str, float]:
    """Recommend NACD threshold for THIS site from a full NF report.

    Aggregates NACD and V_R across all non-reference offsets,
    fits the empirical cutoff, and returns the recommendation.
    """
    from dc_cut.core.processing.nearfield.report import prepare_nacd_vr_scatter

    scatter = prepare_nacd_vr_scatter(report)
    nacd_all = scatter["nacd_all"]
    vr_all = scatter["vr_all"]

    if len(nacd_all) == 0:
        return {
            "nacd_cutoff": np.nan,
            "confidence_lower": np.nan,
            "confidence_upper": np.nan,
            "n_points": 0,
            "contaminated_fraction": np.nan,
            "method": method,
            "recommendation": "Insufficient data for site-specific calibration.",
        }

    result = fit_nacd_cutoff_from_scatter(nacd_all, vr_all, vr_threshold, method)

    # Add human-readable recommendation
    cutoff = result["nacd_cutoff"]
    if np.isfinite(cutoff):
        result["recommendation"] = (
            f"Use NACD ≥ {cutoff:.2f} for this site "
            f"(CI: [{result['confidence_lower']:.2f}, {result['confidence_upper']:.2f}])."
        )
    else:
        result["recommendation"] = "Could not determine site-specific threshold."

    return result
