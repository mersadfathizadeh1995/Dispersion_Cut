"""Backward-compatibility shim -- real module is dc_cut.core.processing.filters."""
from dc_cut.core.processing.filters import *  # noqa: F401,F403
from dc_cut.core.processing.filters import (
    filter_velocity_range,
    filter_frequency_range,
    filter_wavelength_range,
    apply_filters,
    apply_nacd_filter,
)
