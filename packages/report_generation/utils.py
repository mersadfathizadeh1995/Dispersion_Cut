"""Helper utilities for publication figure generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from typing import List, Optional, Tuple, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from .config import PlotConfig, COLORBLIND_PALETTE

logger = logging.getLogger(__name__)


def ensure_parent_dir_for_file(filepath: str) -> None:
    """Create parent directories for filepath if missing (matplotlib does not)."""
    p = Path(filepath).expanduser()
    parent = p.parent
    if parent and str(parent) not in ('.', ''):
        parent.mkdir(parents=True, exist_ok=True)


def apply_style(config: 'PlotConfig'):
    """Apply publication styling to matplotlib."""
    from .config import COLORBLIND_PALETTE
    
    # Determine if we're using a raster format (needs white background)
    is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']

    # Handle font family with fallback for specific fonts
    font_family = config.font_family
    if font_family in ('Times New Roman', 'Arial', 'Helvetica'):
        # Try to use specific font, fallback to generic if not available
        try:
            import matplotlib.font_manager as fm
            available_fonts = [f.name for f in fm.fontManager.ttflist]
            if font_family not in available_fonts:
                logger.warning(f"Font '{font_family}' not found, falling back to 'serif'")
                font_family = 'serif'
        except Exception:
            font_family = 'serif'

    plt.rcParams.update({
        'font.family': font_family,
        'font.size': config.font_size,
        'font.weight': config.font_weight,
        'axes.linewidth': 1.0,
        'axes.labelsize': config.font_size,
        'axes.labelweight': config.font_weight,
        'axes.titleweight': config.font_weight,
        'xtick.labelsize': config.font_size - 1,
        'ytick.labelsize': config.font_size - 1,
        'legend.fontsize': config.font_size - 1,
        'lines.linewidth': config.line_width,
        'lines.markersize': config.marker_size,
        'figure.dpi': config.dpi,
        # Set backgrounds: white for raster, transparent for vector
        'figure.facecolor': 'white' if is_raster else 'none',
        'axes.facecolor': 'white',
        'savefig.facecolor': 'white' if is_raster else 'none',
        'savefig.edgecolor': 'none',
    })


def get_colors(config: 'PlotConfig', n: int) -> List[str]:
    """Get n colors from the configured palette with robust fallback."""
    from .config import COLORBLIND_PALETTE
    
    try:
        # Get palette with fallback to vibrant
        palette_name = config.color_palette if config.color_palette in COLORBLIND_PALETTE else 'vibrant'
        palette = COLORBLIND_PALETTE.get(palette_name, COLORBLIND_PALETTE['vibrant'])

        # Ensure palette is a list
        if not isinstance(palette, (list, tuple)) or len(palette) == 0:
            palette = COLORBLIND_PALETTE['vibrant']

        # Repeat palette if needed
        colors = []
        while len(colors) < n:
            colors.extend(palette)
        return colors[:n]
    except Exception:
        # Ultimate fallback: return matplotlib default colors
        import matplotlib.pyplot as plt
        prop_cycle = plt.rcParams['axes.prop_cycle']
        default_colors = prop_cycle.by_key()['color']
        colors = []
        while len(colors) < n:
            colors.extend(default_colors)
        return colors[:n]


def compute_smart_axis_limits(
    freq_data: np.ndarray,
    vel_data: np.ndarray,
    config: 'PlotConfig',
    x_margin_left: float = 1.0,
    x_margin_right: float = 5.0,
    y_margin: float = 100.0,
    y_floor: float = 0.0,
) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Compute smart axis limits based on dispersion curve data.

    Args:
        freq_data: Frequency data array
        vel_data: Velocity data array
        config: PlotConfig with xlim/ylim overrides
        x_margin_left: Left margin for frequency axis (Hz)
        x_margin_right: Right margin for frequency axis (Hz)
        y_margin: Margin for velocity axis (m/s)
        y_floor: Minimum Y value (0 to hide negatives, or -50 for some margin)

    Returns:
        Tuple of (xlim, ylim) tuples or None if using config values
    """
    # Use explicit config limits if set
    xlim = config.xlim
    ylim = config.ylim

    # Compute auto limits if not specified
    if xlim is None and len(freq_data) > 0:
        freq_min = float(np.nanmin(freq_data))
        freq_max = float(np.nanmax(freq_data))
        xlim = (max(0.0, freq_min - x_margin_left), freq_max + x_margin_right)

    if ylim is None and len(vel_data) > 0:
        vel_min = float(np.nanmin(vel_data))
        vel_max = float(np.nanmax(vel_data))
        # Apply floor (don't show negative values unless curve goes there)
        ylim_low = max(y_floor, vel_min - y_margin)
        ylim = (ylim_low, vel_max + y_margin)

    return xlim, ylim


def apply_legend(
    ax: plt.Axes,
    fig: Figure,
    config: 'PlotConfig',
) -> None:
    """Apply legend with support for outside positions.

    Handles 'outside right', 'outside top', 'outside bottom' positions
    by using bbox_to_anchor for proper placement.

    Args:
        ax: Matplotlib Axes
        fig: Matplotlib Figure
        config: PlotConfig with legend settings
    """
    pos = config.legend_position.lower()  # Normalize to lowercase
    
    if pos == 'outside right':
        ax.legend(
            loc='center left',
            bbox_to_anchor=(1.02, 0.5),
            ncol=config.legend_columns,
            frameon=config.legend_frameon,
            borderaxespad=0,
        )
        # Adjust figure to make room for legend
        fig.tight_layout()
        fig.subplots_adjust(right=0.75)
    elif pos == 'outside top':
        ax.legend(
            loc='lower center',
            bbox_to_anchor=(0.5, 1.02),
            ncol=config.legend_columns,
            frameon=config.legend_frameon,
            borderaxespad=0,
        )
        fig.tight_layout()
        fig.subplots_adjust(top=0.85)
    elif pos == 'outside bottom':
        ax.legend(
            loc='upper center',
            bbox_to_anchor=(0.5, -0.15),
            ncol=config.legend_columns,
            frameon=config.legend_frameon,
            borderaxespad=0,
        )
        fig.tight_layout()
        fig.subplots_adjust(bottom=0.22)
    else:
        # Standard position (inside figure)
        ax.legend(
            loc=config.legend_position,  # Use original case for matplotlib
            ncol=config.legend_columns,
            frameon=config.legend_frameon,
        )


def add_colorbar(
    fig: Figure,
    ax: plt.Axes,
    mappable,
    config: 'PlotConfig',
    label: str = 'Power',
) -> None:
    """Add colorbar by appending axes (maintains plot size).

    Uses make_axes_locatable to add colorbar without shrinking the main plot.
    The colorbar is placed adjacent to the plot.

    Args:
        fig: Matplotlib Figure
        ax: Matplotlib Axes
        mappable: The plot object (contourf, imshow result)
        config: PlotConfig with colorbar settings
        label: Label for the colorbar
    """
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    
    orientation = config.spectrum_colorbar_orientation
    divider = make_axes_locatable(ax)
    
    if orientation == 'horizontal':
        # Add colorbar below the plot
        cax = divider.append_axes("bottom", size="5%", pad=0.5)
        cbar = fig.colorbar(mappable, cax=cax, orientation='horizontal')
        cbar.set_label(label, fontsize=config.font_size - 1)
    else:  # vertical (default)
        # Add colorbar to the right of the plot
        cax = divider.append_axes("right", size="5%", pad=0.1)
        cbar = fig.colorbar(mappable, cax=cax, orientation='vertical')
        cbar.set_label(label, fontsize=config.font_size - 1)


def save_figure(fig: Figure, output_path: str, config: 'PlotConfig'):
    """Helper method to save figure with proper settings."""
    ensure_parent_dir_for_file(output_path)
    is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
    transparent = not is_raster
    fig.savefig(
        output_path,
        dpi=config.dpi,
        bbox_inches='tight',
        facecolor='white' if is_raster else 'none',
        transparent=transparent
    )
