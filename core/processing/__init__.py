"""Pure stateless computation functions for DC Cut.

Modules in this package perform domain computations (filtering,
averaging, selection masks, near-field analysis, etc.) with no
framework imports and no side effects.
"""
from __future__ import annotations

from dc_cut.core.processing.selection import (
    box_mask_freq,
    box_mask_wave,
    remove_in_freq_box,
    remove_in_wave_box,
    line_mask,
    remove_on_side_of_line,
)
from dc_cut.core.processing.averages import (
    compute_avg_by_frequency,
    compute_avg_by_wavelength,
    compute_binned_avg_std,
    compute_binned_avg_std_wavelength,
)
from dc_cut.core.processing.filters import apply_filters, apply_nacd_filter
from dc_cut.core.processing.nearfield import compute_nacd, compute_nacd_array
from dc_cut.core.processing.limits import compute_padded_limits
from dc_cut.core.processing.guides import compute_k_guides
from dc_cut.core.processing.ticks import make_freq_ticks
from dc_cut.core.processing.wavelength_lines import (
    compute_x_bar,
    compute_lambda_max,
    compute_wavelength_line,
    compute_wavelength_lines_batch,
    compute_lambda_max_manual,
    parse_source_offset_from_label,
)

__all__ = [
    "box_mask_freq",
    "box_mask_wave",
    "remove_in_freq_box",
    "remove_in_wave_box",
    "line_mask",
    "remove_on_side_of_line",
    "compute_avg_by_frequency",
    "compute_avg_by_wavelength",
    "compute_binned_avg_std",
    "compute_binned_avg_std_wavelength",
    "apply_filters",
    "apply_nacd_filter",
    "compute_nacd",
    "compute_nacd_array",
    "compute_padded_limits",
    "compute_k_guides",
    "make_freq_ticks",
    "compute_x_bar",
    "compute_lambda_max",
    "compute_wavelength_line",
    "compute_wavelength_lines_batch",
    "compute_lambda_max_manual",
    "parse_source_offset_from_label",
]
