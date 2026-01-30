"""Edit module - re-exports selection functions for backward compatibility.

All editing functions are now consolidated in core/selection.py.
This module re-exports them for any code that imports from edit.py.
"""
from __future__ import annotations

from dc_cut.core.selection import (
    remove_in_freq_box,
    remove_in_wave_box,
    remove_above_line,
    remove_below_line,
    remove_on_side_of_line,
    line_mask,
    side_of_line,
    box_mask_freq,
    box_mask_wave,
)

__all__ = [
    "remove_in_freq_box",
    "remove_in_wave_box",
    "remove_above_line",
    "remove_below_line",
    "remove_on_side_of_line",
    "line_mask",
    "side_of_line",
    "box_mask_freq",
    "box_mask_wave",
]










