"""Shared constants for near-field analysis.

Severity levels, default thresholds, and naming conventions
used across the nearfield sub-package.
"""
from __future__ import annotations

# Severity classification labels (ordered by contamination level)
SEVERITY_LEVELS = ("clean", "marginal", "contaminated", "unknown")

# Default V_R thresholds — Rahimi et al. (2021, 2022)
DEFAULT_VR_CLEAN_THRESHOLD = 0.95
DEFAULT_VR_MARGINAL_THRESHOLD = 0.85
DEFAULT_VR_ONSET_THRESHOLD = 0.90

# Default NACD threshold (conservative, sledgehammer 10-15% error)
DEFAULT_NACD_THRESHOLD = 1.0
