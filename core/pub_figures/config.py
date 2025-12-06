"""Configuration dataclass and constants for publication figures."""

from __future__ import annotations

from typing import Optional, Tuple, List
from dataclasses import dataclass

# Colorblind-friendly palettes
COLORBLIND_PALETTE = {
    'vibrant': ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161', '#949494', '#ECE133'],
    'muted': ['#332288', '#88CCEE', '#44AA99', '#117733', '#999933', '#DDCC77', '#CC6677', '#882255', '#AA4499'],
    'bright': ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB']
}


@dataclass
class PlotConfig:
    """Configuration for publication-quality plots."""
    # Figure settings
    figsize: Tuple[float, float] = (8, 6)
    dpi: int = 300

    # Styling
    font_family: str = 'serif'
    font_size: int = 11
    font_weight: str = 'normal'  # 'normal' or 'bold'
    line_width: float = 1.5
    marker_size: float = 4.0
    marker_style: str = 'o'  # 'o', 's', '^', 'D', 'x', '+', '.'

    # Title (NEW)
    title: Optional[str] = None
    title_fontsize: Optional[int] = None

    # Legend (NEW)
    legend_position: str = 'best'
    legend_columns: int = 1
    legend_frameon: bool = False

    # Colors
    color_palette: str = 'vibrant'  # 'vibrant', 'muted', 'bright', 'high_contrast'
    uncertainty_alpha: float = 0.3
    near_field_alpha: float = 0.4

    # Near-field marking
    mark_near_field: bool = True
    near_field_style: str = 'faded'  # 'faded', 'crossed', or 'none'
    nacd_threshold: float = 1.0

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
    output_format: str = 'pdf'  # 'pdf', 'png', 'svg', 'eps'
    tight_layout: bool = True

    # Spectrum options (for offset analysis with spectrum background)
    spectrum_colormap: str = 'viridis'
    spectrum_render_mode: str = 'imshow'  # 'imshow' or 'contour'
    spectrum_alpha: float = 0.8
    spectrum_levels: int = 30
    show_spectrum_colorbar: bool = True  # Show/hide colorbar for spectrum plots

    # Peak/curve overlay options (for curves on spectrum background)
    peak_color: str = '#FFFFFF'  # White default for visibility
    peak_outline: bool = True
    peak_outline_color: str = '#000000'
    peak_line_width: float = 2.5
    curve_overlay_style: str = 'line'  # 'line', 'markers', or 'line+markers'

    # Colorbar options (for spectrum plots)
    spectrum_colorbar_orientation: str = 'vertical'  # 'none', 'vertical', 'horizontal'

    # Grid options (for Comparison Grid)
    grid_offset_indices: Optional[List[int]] = None  # None = all offsets
