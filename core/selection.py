"""Backward-compatibility shim -- real module is dc_cut.core.processing.selection."""
from dc_cut.core.processing.selection import *  # noqa: F401,F403
from dc_cut.core.processing.selection import (
    box_mask_freq,
    box_mask_wave,
    remove_in_freq_box,
    remove_in_wave_box,
    side_of_line,
    line_mask,
    remove_above_line,
    remove_below_line,
    remove_on_side_of_line,
)
