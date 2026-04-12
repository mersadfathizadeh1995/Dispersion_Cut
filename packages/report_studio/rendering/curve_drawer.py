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
    if highlight:
        lw *= 2.0
        ms *= 1.5

    ax.plot(
        x, y,
        color=curve.color,
        linewidth=lw,
        marker="o",
        markersize=ms,
        markeredgecolor=curve.color,
        markerfacecolor=curve.color,
        alpha=0.9,
        label=curve.display_name,
        zorder=10,
    )
