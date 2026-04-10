"""Backward-compatibility shim -- real module is dc_cut.core.processing.averages."""
from dc_cut.core.processing.averages import *  # noqa: F401,F403
from dc_cut.core.processing.averages import (
    biased_edges,
    bin_freqvel,
    compute_avg_by_frequency,
    compute_avg_by_wavelength,
    compute_binned_avg_std,
    compute_binned_avg_std_wavelength,
)
