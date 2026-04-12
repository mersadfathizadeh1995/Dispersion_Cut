"""
Unified renderer — SheetState → matplotlib Figure.

One function, no dual-renderer split. The entire rendering pipeline
in a single, testable module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from . import layout_builder, curve_drawer, spectrum_drawer
from .style import StyleConfig

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import SheetState


def render_sheet(
    fig: Figure,
    state: "SheetState",
    style: Optional[StyleConfig] = None,
    selected_uid: str = "",
) -> Dict[str, "Axes"]:
    """
    Render a complete sheet onto *fig*.

    Parameters
    ----------
    fig : Figure
        Target matplotlib figure (will be cleared).
    state : SheetState
        Complete state: curves, spectra, subplots, layout.
    style : StyleConfig, optional
        Rendering style. Uses defaults if not given.
    selected_uid : str
        UID of the currently selected curve (drawn highlighted).

    Returns
    -------
    dict
        Mapping subplot_key → Axes for post-render access.
    """
    if style is None:
        style = StyleConfig()

    fig.clear()
    fig.set_facecolor(style.figure_facecolor)
    fig.set_size_inches(state.figure_width, state.figure_height)

    # Create subplot grid
    axes = layout_builder.create_grid(fig, state)

    # Render each subplot
    for key, ax in axes.items():
        _render_subplot(ax, key, state, style, selected_uid)

    # Apply layout
    try:
        if state.grid_rows == 1 and state.grid_cols == 1:
            fig.tight_layout(pad=1.5)
        else:
            fig.subplots_adjust(
                hspace=state.hspace, wspace=state.wspace,
                left=0.08, right=0.96, top=0.94, bottom=0.08,
            )
    except Exception:
        pass

    return axes


def _render_subplot(
    ax: "Axes",
    subplot_key: str,
    state: "SheetState",
    style: StyleConfig,
    selected_uid: str,
):
    """Render one subplot: spectrum backgrounds + dispersion curves + axes."""
    sp = state.subplots.get(subplot_key)
    if sp is None:
        ax.set_visible(False)
        return

    x_domain = sp.x_domain
    curves = state.get_curves_for_subplot(subplot_key)

    # 1. Draw spectrum backgrounds (behind curves)
    for curve in curves:
        if curve.spectrum_uid and curve.spectrum_visible:
            spec = state.spectra.get(curve.spectrum_uid)
            if spec and spec.has_data:
                spectrum_drawer.draw(ax, spec, x_domain, style)

    # 2. Draw dispersion curves
    for curve in curves:
        if curve.visible:
            curve_drawer.draw(
                ax, curve, x_domain, style,
                highlight=(curve.uid == selected_uid),
            )

    # 3. Configure axes
    _configure_axes(ax, sp, style, x_domain, curves=curves)

    # 4. Legend
    if style.legend_visible and curves:
        visible_curves = [c for c in curves if c.visible]
        if visible_curves:
            ax.legend(
                fontsize=style.legend_font_size,
                loc=style.legend_position,
                frameon=style.legend_frame_on,
                framealpha=style.legend_alpha,
            )

    # 5. Title
    if sp.display_name:
        ax.set_title(sp.display_name, fontsize=style.title_size)


def _configure_axes(ax, sp, style: StyleConfig, x_domain: str, curves=None):
    """Set axis labels, limits, and styling."""
    ax.set_xlabel(style.get_x_label(x_domain), fontsize=style.axis_label_size)
    ax.set_ylabel(style.get_y_label(), fontsize=style.axis_label_size)
    style.apply_to_axes(ax)

    # Auto-range based on curve data extents (not spectra)
    if curves and (sp.auto_x or sp.auto_y):
        import numpy as np
        all_x, all_y = [], []
        for c in curves:
            if not c.visible or c.frequency.size == 0:
                continue
            if x_domain == "wavelength" and c.wavelength.size > 0:
                all_x.append(c.wavelength)
            else:
                all_x.append(c.frequency)
            all_y.append(c.velocity)
        if all_x and all_y:
            x_all = np.concatenate(all_x)
            y_all = np.concatenate(all_y)
            pad = 0.05
            if sp.auto_x and x_all.size > 0:
                x_min, x_max = float(np.nanmin(x_all)), float(np.nanmax(x_all))
                dx = max((x_max - x_min) * pad, 0.1)
                ax.set_xlim(x_min - dx, x_max + dx)
            if sp.auto_y and y_all.size > 0:
                y_min, y_max = float(np.nanmin(y_all)), float(np.nanmax(y_all))
                dy = max((y_max - y_min) * pad, 0.1)
                ax.set_ylim(y_min - dy, y_max + dy)

    # Apply manual limits if set
    if not sp.auto_x and sp.x_range:
        ax.set_xlim(sp.x_range)
    if not sp.auto_y and sp.y_range:
        ax.set_ylim(sp.y_range)
