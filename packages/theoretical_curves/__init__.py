"""Theoretical Dispersion Curves package for DC Cut.

This subpackage provides functionality for displaying and generating
theoretical dispersion curves with uncertainty bands.

Features:
- Load theoretical curves from CSV files (statistics format)
- Generate curves from Geopsy .report files using gpdcreport/gpdc
- Display median line and uncertainty band on frequency/wavelength plots
- Adjustable visibility, opacity, and colors per curve
"""
from __future__ import annotations

from dc_cut.packages.theoretical_curves.config import (
    TheoreticalCurve,
    TheoreticalCurveStyle,
    GenerationConfig,
)

from dc_cut.packages.theoretical_curves.io import (
    load_theoretical_csv,
    load_multiple_csv,
)

from dc_cut.packages.theoretical_curves.renderer import TheoreticalCurveRenderer
from dc_cut.packages.theoretical_curves.dock import TheoreticalCurvesDock
from dc_cut.packages.theoretical_curves.generator import (
    TheoreticalCurveGenerator,
    validate_geopsy_installation,
)

__all__ = [
    "TheoreticalCurve",
    "TheoreticalCurveStyle",
    "GenerationConfig",
    "load_theoretical_csv",
    "load_multiple_csv",
    "TheoreticalCurveRenderer",
    "TheoreticalCurvesDock",
    "TheoreticalCurveGenerator",
    "validate_geopsy_installation",
]
