"""Canvas overlay helpers for the NF evaluation dock.

Extracted from :class:`NearFieldEvalDock`.  All functions operate on
the caller's ``controller`` (which owns ``ax_freq``, ``ax_wave`` and
``fig``); colour palettes are passed in explicitly so the dock can
keep user-configurable severity colours.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from dc_cut.gui.widgets.nf_limit_lines import clear_nf_limit_lines


def draw_nacd_overlay(
    controller,
    offset_idx: int,
    f,
    v,
    w,
    mask,
    colors: Mapping[str, str],
) -> None:
    """Draw red/blue circles on both axes for NACD-only mode."""
    c = controller
    for i in range(len(f)):
        col = colors["contaminated"] if mask[i] else colors["clean"]
        key = (offset_idx, i)
        lf = c.ax_freq.plot(
            [f[i]], [v[i]], 'o', linestyle='None',
            mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
            label='_nf_overlay',
        )[0]
        lw = c.ax_wave.plot(
            [w[i]], [v[i]], 'o', linestyle='None',
            mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
            label='_nf_overlay',
        )[0]
        if not hasattr(c, '_nf_point_overlay'):
            c._nf_point_overlay = {}
        c._nf_point_overlay[key] = (lf, lw)
    try:
        c.fig.canvas.draw_idle()
    except Exception:
        pass


def draw_reference_overlay(
    controller,
    offset_idx: int,
    f,
    v,
    w,
    severity: Sequence[str],
    colors: Mapping[str, str],
) -> None:
    """Draw 4-color severity circles on both axes."""
    c = controller
    for i in range(len(f)):
        sev = severity[i] if severity is not None else "unknown"
        col = colors.get(sev, colors["unknown"])
        key = (offset_idx, i)
        lf = c.ax_freq.plot(
            [f[i]], [v[i]], 'o', linestyle='None',
            mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
            label='_nf_overlay',
        )[0]
        lw = c.ax_wave.plot(
            [w[i]], [v[i]], 'o', linestyle='None',
            mfc='none', mec=col, mew=1.6, ms=6, zorder=10,
            label='_nf_overlay',
        )[0]
        if not hasattr(c, '_nf_point_overlay'):
            c._nf_point_overlay = {}
        c._nf_point_overlay[key] = (lf, lw)
    try:
        c.fig.canvas.draw_idle()
    except Exception:
        pass


def clear_nf_overlays(controller, limit_artists: list) -> None:
    """Clear per-point NF overlays *and* NF limit-line artists."""
    try:
        for key, (lf, lw) in list(
            getattr(controller, '_nf_point_overlay', {}).items()
        ):
            try:
                lf.remove()
                lw.remove()
            except Exception:
                pass
        controller._nf_point_overlay = {}
    except Exception:
        pass
    clear_nf_limit_lines(limit_artists)
    try:
        controller.fig.canvas.draw_idle()
    except Exception:
        pass


__all__ = ["draw_nacd_overlay", "draw_reference_overlay", "clear_nf_overlays"]
