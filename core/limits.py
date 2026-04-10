"""Backward-compatibility shim -- real module is dc_cut.core.processing.limits.

This shim injects user preferences into the pure function so callers
that relied on the old auto-reading behavior keep working.
"""
from __future__ import annotations

from typing import Dict
import numpy as np

from dc_cut.core.processing.limits import compute_padded_limits as _compute_padded_limits


def compute_padded_limits(v: np.ndarray, f: np.ndarray, w: np.ndarray, *, pad_frac: float = 0.08) -> Dict[str, float]:
    """Wrapper that reads robust percentiles from user preferences."""
    try:
        from dc_cut.services.prefs import get_pref
        p_lo = get_pref('robust_lower_pct', 0.5)
        p_hi = get_pref('robust_upper_pct', 99.5)
    except Exception:
        p_lo, p_hi = 0.5, 99.5
    return _compute_padded_limits(
        v, f, w,
        pad_frac=pad_frac,
        robust_lower_pct=p_lo,
        robust_upper_pct=p_hi,
    )
