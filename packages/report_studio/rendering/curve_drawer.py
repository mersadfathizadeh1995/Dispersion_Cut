"""
Curve drawer — render dispersion curves on matplotlib Axes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import OffsetCurve
    from .style import StyleConfig


def draw(
    ax: "Axes",
    curve: "OffsetCurve",
    x_domain: str = "frequency",
    style: "StyleConfig" = None,
    highlight: bool = False,
):
    """
    Draw a single dispersion curve on the given Axes.

    Parameters
    ----------
    ax : Axes
        Target matplotlib axes.
    curve : OffsetCurve
        Curve data and display settings.
    x_domain : str
        "frequency" or "wavelength".
    style : StyleConfig, optional
        Global style config (for label text sizes, etc.).
    highlight : bool
        If True, draw with thicker line for selection emphasis.
    """
    if not curve.has_data or not curve.visible:
        return

    x, y = curve.masked_arrays(x_domain)

    lw = curve.line_width
    ms = curve.marker_size
    ls = getattr(curve, "line_style", "-")
    marker = getattr(curve, "marker_style", "o")
    if marker == "none":
        marker = ""

    # Visibility toggles
    line_vis = getattr(curve, "line_visible", True)
    marker_vis = getattr(curve, "marker_visible", True)
    if not line_vis:
        ls = "none"
    if not marker_vis:
        marker = ""

    if highlight:
        lw *= 2.0
        ms *= 1.5

    # Resolve display color (peak_color overrides curve.color when set)
    display_color = getattr(curve, "peak_color", "") or curve.color

    # Outline layer (drawn behind the main curve for emphasis)
    use_outline = getattr(curve, "peak_outline", False)
    if use_outline:
        outline_color = getattr(curve, "peak_outline_color", "#000000")
        outline_w = getattr(curve, "peak_outline_width", 1.0)
        ax.plot(
            x, y,
            color=outline_color,
            linewidth=lw + outline_w * 2,
            linestyle=ls,
            marker=marker,
            markersize=ms + outline_w * 2,
            markeredgecolor=outline_color,
            markerfacecolor=outline_color,
            alpha=0.9,
            zorder=9,
        )

    ax.plot(
        x, y,
        color=display_color,
        linewidth=lw,
        linestyle=ls,
        marker=marker,
        markersize=ms,
        markeredgecolor=display_color,
        markerfacecolor=display_color,
        alpha=0.9,
        label=(curve.legend_label.strip()
               if getattr(curve, "legend_label", "")
               else curve.display_name),
        zorder=10,
    )
