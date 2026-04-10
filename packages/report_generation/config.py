"""Configuration dataclass and constants for report generation.

PlotConfig is the flat dataclass used by all existing plot code and the dialog.
ReportConfig is an alias for PlotConfig (future: composed sub-configs).
"""
from __future__ import annotations

from typing import Optional, Tuple, List
from dataclasses import dataclass

COLORBLIND_PALETTE = {
    'vibrant': ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161', '#949494', '#ECE133'],
    'muted': ['#332288', '#88CCEE', '#44AA99', '#117733', '#999933', '#DDCC77', '#CC6677', '#882255', '#AA4499'],
    'bright': ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB'],
}


@dataclass
class PlotConfig:
    """Configuration for publication-quality plots (flat layout).

    All existing plot mixins, the dialog, and the generator consume this
    class directly.  A future ``ReportConfig`` with composed sub-dataclasses
    can inherit from here and map the flat fields to sub-objects.
    """
    # Figure settings
    figsize: Tuple[float, float] = (8, 6)
    dpi: int = 300

    # Styling
    font_family: str = 'serif'
    font_size: int = 11
    font_weight: str = 'normal'
    line_width: float = 1.5
    marker_size: float = 4.0
    marker_style: str = 'o'

    # Title
    title: Optional[str] = None
    title_fontsize: Optional[int] = None

    # Legend
    legend_position: str = 'best'
    legend_columns: int = 1
    legend_frameon: bool = False

    # Colors
    color_palette: str = 'vibrant'
    uncertainty_alpha: float = 0.3
    near_field_alpha: float = 0.4

    # Near-field marking
    mark_near_field: bool = True
    near_field_style: str = 'faded'
    nacd_threshold: float = 1.0
    nf_farfield_color: str = 'blue'
    nf_nearfield_color: str = 'red'
    nf_show_spectrum: bool = False
    nf_grid_display_mode: str = 'curves'
    nf_grid_offset_indices: Optional[List[int]] = None

    # Axes
    show_grid: bool = True
    grid_alpha: float = 0.3

    # Labels
    xlabel: str = 'Frequency (Hz)'
    ylabel: str = 'Phase Velocity (m/s)'

    # Limits (None = auto)
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None

    # Output
    output_format: str = 'pdf'
    tight_layout: bool = True

    # Spectrum options
    spectrum_colormap: str = 'viridis'
    spectrum_render_mode: str = 'imshow'
    spectrum_alpha: float = 0.8
    spectrum_levels: int = 30
    show_spectrum_colorbar: bool = True

    # Peak/curve overlay
    peak_color: str = '#FFFFFF'
    peak_outline: bool = True
    peak_outline_color: str = '#000000'
    peak_line_width: float = 2.5
    curve_overlay_style: str = 'line'

    # Colorbar
    spectrum_colorbar_orientation: str = 'vertical'

    # Grid (comparison grid)
    grid_offset_indices: Optional[List[int]] = None
    grid_shared_colorbar: str = 'vertical'


# Forward-looking alias -- today they're the same class
ReportConfig = PlotConfig
