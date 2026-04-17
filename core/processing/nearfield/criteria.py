"""Source-type-aware NACD criteria and transformation-method multipliers.

Thresholds are drawn from Rahimi et al. (2022) Table 2 and the
transformation-method comparison in Rahimi et al. (2021) Section 5.

No framework imports, no controller references.
"""
from __future__ import annotations

from typing import Dict, Optional


# ── Source-type NACD thresholds ─────────────────────────────────────
#
# Rahimi et al. (2022) Table 2:
#   Sledgehammer — σ ≈ 0.28–0.33
#     NACD ≥ 1.0 → ≤ 10–15% error  |  NACD ≥ 1.5 → ≤ 5% error
#   Vibroseis — σ ≈ 0.05–0.45
#     NACD ≥ 0.5 → ≤ 10–15% error  |  NACD ≥ 0.6 → ≤ 5% error
#
# These are INDEPENDENT of surface wave type (Rayleigh/Love) and
# impedance contrast depth.

NACD_CRITERIA: Dict[str, Dict[str, float]] = {
    "sledgehammer": {
        "5pct": 1.5,
        "10_15pct": 1.0,
        "sigma_5": 0.30,
        "sigma_10_15": 0.30,
    },
    "vibroseis": {
        "5pct": 0.6,
        "10_15pct": 0.5,
        "sigma_5": 0.45,
        "sigma_10_15": 0.05,
    },
    # Aliases
    "hammer": {
        "5pct": 1.5,
        "10_15pct": 1.0,
        "sigma_5": 0.30,
        "sigma_10_15": 0.30,
    },
    # Conservative fallback for unknown source
    "unknown": {
        "5pct": 1.5,
        "10_15pct": 1.0,
        "sigma_5": 0.33,
        "sigma_10_15": 0.33,
    },
}

# Human-readable descriptions for UI dropdowns
SOURCE_TYPE_LABELS: Dict[str, str] = {
    "sledgehammer": "Sledgehammer (impulsive)",
    "vibroseis": "Vibroseis (swept)",
    "hammer": "Hammer (impulsive, alias)",
    "unknown": "Unknown (conservative)",
}

ERROR_LEVEL_LABELS: Dict[str, str] = {
    "5pct": "≤ 5% phase velocity error",
    "10_15pct": "≤ 10–15% phase velocity error",
}


# ── Transformation-method NF multipliers ────────────────────────────
#
# Rahimi et al. (2021) Section 5, Figs. 14–15:
#   FDBF-cylindrical resolves ≈ 2× longer wavelengths than FK/τp
#   because it accounts for wavefront curvature.
#
# The multiplier adjusts the effective NACD threshold:
#   effective_threshold = base_threshold × multiplier
#
# Lower multiplier ⟹ method is more robust to near-field effects.

TRANSFORM_NF_MULTIPLIER: Dict[str, float] = {
    "fdbf_cylindrical": 0.5,   # handles NF best — 2× improvement
    "fdbf_plane": 1.0,         # plane-wave assumption, no improvement
    "fk": 1.0,                 # standard FK, plane-wave based
    "tau_p": 1.0,              # slant-stack, plane-wave based
    "phase_shift": 0.8,        # intermediate (Paper 1 Fig. 15)
    "ps": 0.8,                 # alias for phase_shift
}

TRANSFORM_LABELS: Dict[str, str] = {
    "fdbf_cylindrical": "FDBF Cylindrical",
    "fdbf_plane": "FDBF Plane-wave",
    "fk": "FK (Frequency-Wavenumber)",
    "tau_p": "τ-p (Slant Stack)",
    "phase_shift": "Phase Shift",
    "ps": "Phase Shift (alias)",
}


def resolve_nacd_threshold(
    source_type: str = "sledgehammer",
    error_level: str = "10_15pct",
    transform: Optional[str] = None,
) -> float:
    """Resolve the NACD threshold for a given source type, error level, and transform.

    Parameters
    ----------
    source_type : str
        Source type key: ``"sledgehammer"``, ``"vibroseis"``, ``"hammer"``,
        or ``"unknown"``.
    error_level : str
        Acceptable error level: ``"5pct"`` or ``"10_15pct"``.
    transform : str, optional
        Transformation method key (e.g. ``"fdbf_cylindrical"``).
        If given, the threshold is adjusted by the method's NF multiplier.

    Returns
    -------
    float
        The NACD threshold below which data is considered near-field contaminated.

    Examples
    --------
    >>> resolve_nacd_threshold("sledgehammer", "10_15pct")
    1.0
    >>> resolve_nacd_threshold("vibroseis", "5pct")
    0.6
    >>> resolve_nacd_threshold("sledgehammer", "10_15pct", "fdbf_cylindrical")
    0.5
    """
    st = source_type.lower().strip()
    if st not in NACD_CRITERIA:
        st = "unknown"

    el = error_level.lower().strip()
    criteria = NACD_CRITERIA[st]
    if el not in criteria:
        el = "10_15pct"

    base = criteria[el]

    if transform is not None:
        tr = transform.lower().strip().replace("-", "_").replace(" ", "_")
        multiplier = TRANSFORM_NF_MULTIPLIER.get(tr, 1.0)
        base *= multiplier

    return float(base)


def get_nacd_sigma(
    source_type: str = "sledgehammer",
    error_level: str = "10_15pct",
) -> float:
    """Return the standard deviation (σ) for the given source type and error level.

    Useful for confidence band plotting and site calibration comparison.

    Rahimi et al. (2022) Table 2.
    """
    st = source_type.lower().strip()
    if st not in NACD_CRITERIA:
        st = "unknown"

    key = f"sigma_{error_level.lower().strip()}"
    criteria = NACD_CRITERIA[st]
    return float(criteria.get(key, 0.30))


def parse_transform_from_label(label: str) -> Optional[str]:
    """Try to detect transformation method from a dataset label.

    Looks for common substrings like ``"FDBF"``, ``"FK"``, ``"tau"``, etc.
    Returns the normalised key or ``None`` if unrecognised.
    """
    lbl = label.lower().strip()

    if "fdbf" in lbl and ("cyl" in lbl or "cylindr" in lbl):
        return "fdbf_cylindrical"
    if "fdbf" in lbl and "plane" in lbl:
        return "fdbf_plane"
    if "fdbf" in lbl:
        return "fdbf_plane"  # default FDBF variant
    if "fk" in lbl or "f-k" in lbl:
        return "fk"
    if "tau" in lbl or "slant" in lbl:
        return "tau_p"
    if "phase" in lbl and "shift" in lbl:
        return "phase_shift"
    if lbl.startswith("ps") or lbl.endswith("ps"):
        return "phase_shift"

    return None
