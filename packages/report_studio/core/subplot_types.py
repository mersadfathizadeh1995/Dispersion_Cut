"""
Subplot type system — validates which data can go in which subplot.

Adapted from GeoFigure's core/subplot_types.py for DC Cut's data types.
"""

# Subplot types
UNSET = "unset"
DISPERSION = "dispersion"   # Curve-only (freq or wavelength vs velocity)
SPECTRUM = "spectrum"        # Spectrum background only
COMBINED = "combined"        # Curve + spectrum background (default)

ALL_TYPES = (UNSET, DISPERSION, SPECTRUM, COMBINED)

# Data kinds that can be added to subplots
KIND_CURVE = "curve"
KIND_SPECTRUM = "spectrum"

# What each subplot type accepts
ACCEPTANCE_RULES = {
    UNSET:      {KIND_CURVE, KIND_SPECTRUM},
    DISPERSION: {KIND_CURVE},
    SPECTRUM:   {KIND_SPECTRUM},
    COMBINED:   {KIND_CURVE, KIND_SPECTRUM},
}


def can_accept(subplot_type: str, data_kind: str) -> bool:
    """Check if *subplot_type* can accept *data_kind*."""
    return data_kind in ACCEPTANCE_RULES.get(subplot_type, set())


def auto_assign_type(current_type: str, data_kind: str) -> str:
    """When an UNSET subplot receives data, determine its new type."""
    if current_type != UNSET:
        return current_type
    if data_kind == KIND_CURVE:
        return COMBINED
    if data_kind == KIND_SPECTRUM:
        return SPECTRUM
    return COMBINED
