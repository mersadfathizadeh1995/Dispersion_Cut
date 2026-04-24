"""
Aggregated curve drawer — render average line + uncertainty on Axes.

Draws three visual layers:
  zorder 5: Shadow curves (faded individual offsets)
  zorder 7: Uncertainty band (fill_between) or errorbars
  zorder 8: Average line with markers
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import AggregatedCurve, OffsetCurve
    from .style import StyleConfig


def draw(
    ax: "Axes",
    agg: "AggregatedCurve",
    shadow_curves: List["OffsetCurve"],
    x_domain: str = "frequency",
    style: "StyleConfig" = None,
):
    """
    Draw aggregated average + uncertainty + optional shadow curves.

    Parameters
    ----------
    ax : Axes
        Target matplotlib axes.
    agg : AggregatedCurve
        Aggregated data and display settings.
    shadow_curves : list[OffsetCurve]
        Individual offset curves for shadow layer.
    x_domain : str
        "frequency" or "wavelength".
    style : StyleConfig, optional
        Global style config.
    """
    if not agg.has_data:
        return

    x = agg.bin_centers
    y = agg.avg_vals
    std = agg.std_vals

    # ── Layer 1: Shadow curves ──────────────────────────────────────────
    if agg.shadow_visible and shadow_curves:
        _draw_shadows(ax, shadow_curves, x_domain, agg.shadow_alpha)

    # ── Layer 2: Uncertainty ────────────────────────────────────────────
    if agg.uncertainty_visible and std is not None and len(std) > 0:
        unc_color = agg.effective_uncertainty_color
        if agg.uncertainty_mode == "band":
            ax.fill_between(
                x,
                y - std,
                y + std,
                alpha=agg.uncertainty_alpha,
                color=unc_color,
                label="±1σ envelope",
                zorder=7,
            )
        elif agg.uncertainty_mode == "errorbar":
            ax.errorbar(
                x, y,
                yerr=std,
                fmt="none",
                ecolor=unc_color,
                elinewidth=1.2,
                capsize=3,
                capthick=1.0,
                alpha=min(agg.uncertainty_alpha + 0.3, 1.0),
                label="±1σ errorbars",
                zorder=7,
            )
        elif agg.uncertainty_mode == "sticks":
            # Vertical lines at each bin (no caps)
            unc_alpha = min(agg.uncertainty_alpha + 0.3, 1.0)
            ax.vlines(
                x, y - std, y + std,
                colors=unc_color,
                linewidths=1.2,
                alpha=unc_alpha,
                label="±1σ sticks",
                zorder=7,
            )

    # ── Layer 3: Average line ───────────────────────────────────────────
    if agg.avg_visible:
        ls = agg.avg_line_style
        marker = agg.avg_marker_style
        if marker == "none":
            marker = ""

        ax.plot(
            x, y,
            color=agg.avg_color,
            linewidth=agg.avg_line_width,
            linestyle=ls,
            marker=marker,
            markersize=agg.avg_marker_size,
            markeredgecolor=agg.avg_color,
            markerfacecolor=agg.avg_color,
            alpha=0.95,
            label=(agg.legend_label.strip()
                   if getattr(agg, "legend_label", "")
                   else agg.display_name),
            zorder=8,
        )


def _draw_shadows(
    ax: "Axes",
    curves: List["OffsetCurve"],
    x_domain: str,
    alpha: float,
):
    """Draw individual offset curves as faded shadows."""
    for curve in curves:
        if not curve.has_data:
            continue
        x, y = curve.masked_arrays(x_domain)
        ax.plot(
            x, y,
            color=curve.color,
            linewidth=0.8,
            linestyle="-",
            alpha=alpha,
            zorder=5,
        )
