"""Backward-compatibility shim -- real module is dc_cut.visualization.plot_helpers."""
from dc_cut.visualization.plot_helpers import *  # noqa: F401,F403
from dc_cut.visualization.plot_helpers import (
    visible_wave_handles_labels,
    assemble_legend,
    create_offset_lines,
    set_line_xy,
)
