"""Shared styling engine for report generation.

Every plot type imports from this module rather than calling
plt.rcParams or duplicating style logic. Change font size, axis
scale, or grid appearance here and all figures pick it up.

All functions accept a PlotConfig (flat dataclass) instance.
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes

if TYPE_CHECKING:
    from .config import PlotConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# matplotlib defaults
# ---------------------------------------------------------------------------

def apply_matplotlib_defaults(config: 'PlotConfig'):
    """Set rcParams: font family, sizes, weights, line widths, backgrounds."""
    is_raster = config.output_format.lower() in ('png', 'jpg', 'jpeg')

    font_family = config.font_family
    if font_family in ('Times New Roman', 'Arial', 'Helvetica'):
        try:
            import matplotlib.font_manager as fm
            available = [f.name for f in fm.fontManager.ttflist]
            if font_family not in available:
                logger.warning("Font '%s' not found, falling back to 'serif'", font_family)
                font_family = 'serif'
        except Exception:
            font_family = 'serif'

    fs = config.font_size
    plt.rcParams.update({
        'font.family': font_family,
        'font.size': fs,
        'font.weight': config.font_weight,
        'axes.linewidth': 1.0,
        'axes.labelsize': fs,
        'axes.labelweight': config.font_weight,
        'axes.titleweight': config.font_weight,
        'xtick.labelsize': fs - 1,
        'ytick.labelsize': fs - 1,
        'legend.fontsize': fs - 1,
        'lines.linewidth': config.line_width,
        'lines.markersize': config.marker_size,
        'figure.dpi': config.dpi,
        'figure.facecolor': 'white' if is_raster else 'none',
        'axes.facecolor': 'white',
        'savefig.facecolor': 'white' if is_raster else 'none',
        'savefig.edgecolor': 'none',
    })

# ---------------------------------------------------------------------------
# figure creation
# ---------------------------------------------------------------------------

def create_figure(config: 'PlotConfig', **subplots_kw) -> Tuple[Figure, Axes]:
    """Create a figure with correct size, DPI, and style applied."""
    apply_matplotlib_defaults(config)
    fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi, **subplots_kw)
    return fig, ax

# ---------------------------------------------------------------------------
# axes configuration
# ---------------------------------------------------------------------------

def configure_axes(ax: Axes, config: 'PlotConfig', *, domain: str = 'frequency'):
    """Apply axis labels, log/linear scale, tick formatting, grid."""
    ax.set_xlabel(config.xlabel)
    ax.set_ylabel(config.ylabel)

    if config.show_grid:
        ax.grid(True, alpha=config.grid_alpha, linestyle='--', linewidth=0.5)

    if config.xlim is not None:
        ax.set_xlim(config.xlim)
    if config.ylim is not None:
        ax.set_ylim(config.ylim)

    if config.title:
        title_fs = config.title_fontsize or config.font_size + 2
        ax.set_title(config.title, fontsize=title_fs)

# ---------------------------------------------------------------------------
# colors
# ---------------------------------------------------------------------------

def get_color_palette(config: 'PlotConfig', n: int) -> List[str]:
    """Return *n* colors from the chosen colorblind-friendly palette."""
    from .config import COLORBLIND_PALETTE

    try:
        name = config.color_palette if config.color_palette in COLORBLIND_PALETTE else 'vibrant'
        palette = list(COLORBLIND_PALETTE.get(name, COLORBLIND_PALETTE['vibrant']))
        if not palette:
            palette = list(COLORBLIND_PALETTE['vibrant'])
        colors: List[str] = []
        while len(colors) < n:
            colors.extend(palette)
        return colors[:n]
    except Exception:
        prop_cycle = plt.rcParams['axes.prop_cycle']
        default = prop_cycle.by_key()['color']
        colors = []
        while len(colors) < n:
            colors.extend(default)
        return colors[:n]

# ---------------------------------------------------------------------------
# legend
# ---------------------------------------------------------------------------

def apply_legend(ax: Axes, fig: Figure, config: 'PlotConfig'):
    """Place legend with support for outside positions."""
    pos = config.legend_position.lower()

    kw = dict(ncol=config.legend_columns, frameon=config.legend_frameon)

    if pos == 'outside right':
        ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), borderaxespad=0, **kw)
        fig.tight_layout(); fig.subplots_adjust(right=0.75)
    elif pos == 'outside top':
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02), borderaxespad=0, **kw)
        fig.tight_layout(); fig.subplots_adjust(top=0.85)
    elif pos == 'outside bottom':
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), borderaxespad=0, **kw)
        fig.tight_layout(); fig.subplots_adjust(bottom=0.22)
    else:
        ax.legend(loc=config.legend_position, **kw)

# ---------------------------------------------------------------------------
# colorbar
# ---------------------------------------------------------------------------

def add_colorbar(fig: Figure, ax: Axes, mappable, config: 'PlotConfig', label: str = 'Power'):
    """Attach colorbar without shrinking the plot."""
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    orientation = config.spectrum_colorbar_orientation
    divider = make_axes_locatable(ax)

    if orientation == 'horizontal':
        cax = divider.append_axes('bottom', size='5%', pad=0.5)
        cbar = fig.colorbar(mappable, cax=cax, orientation='horizontal')
    else:
        cax = divider.append_axes('right', size='5%', pad=0.1)
        cbar = fig.colorbar(mappable, cax=cax, orientation='vertical')
    cbar.set_label(label, fontsize=config.font_size - 1)

# ---------------------------------------------------------------------------
# axis limits
# ---------------------------------------------------------------------------

def compute_smart_axis_limits(
    freq_data: np.ndarray,
    vel_data: np.ndarray,
    config: 'PlotConfig',
    x_margin_left: float = 1.0,
    x_margin_right: float = 5.0,
    y_margin: float = 100.0,
    y_floor: float = 0.0,
) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Compute smart axis limits based on dispersion-curve data."""
    xlim = config.xlim
    ylim = config.ylim

    if xlim is None and len(freq_data) > 0:
        fmin = float(np.nanmin(freq_data))
        fmax = float(np.nanmax(freq_data))
        xlim = (max(0.0, fmin - x_margin_left), fmax + x_margin_right)

    if ylim is None and len(vel_data) > 0:
        vmin = float(np.nanmin(vel_data))
        vmax = float(np.nanmax(vel_data))
        ylim = (max(y_floor, vmin - y_margin), vmax + y_margin)

    return xlim, ylim

# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

def save_figure(fig: Figure, output_path: str, config: 'PlotConfig'):
    """Save with proper DPI, transparency, tight layout."""
    is_raster = config.output_format.lower() in ('png', 'jpg', 'jpeg')
    fig.savefig(
        output_path,
        dpi=config.dpi,
        bbox_inches='tight',
        facecolor='white' if is_raster else 'none',
        transparent=not is_raster,
    )
