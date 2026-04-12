"""
Spectrum drawer — render power spectrum pcolormesh backgrounds on Axes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import SpectrumData, OffsetCurve
    from .style import StyleConfig


def _downsample_2d(arr: np.ndarray, max_rows: int, max_cols: int) -> np.ndarray:
    """Stride-based downsampling for large 2D arrays (draft quality)."""
    if arr.ndim != 2:
        return arr
    r, c = arr.shape
    rs = max(1, r // max_rows)
    cs = max(1, c // max_cols)
    return arr[::rs, ::cs]


def _downsample_1d(arr: np.ndarray, step: int) -> np.ndarray:
    """Stride-based downsampling for 1D arrays."""
    if step <= 1:
        return arr
    return arr[::step]


def draw(
    ax: "Axes",
    spectrum: "SpectrumData",
    x_domain: str = "frequency",
    style: "StyleConfig" = None,
    curve: "OffsetCurve" = None,
    quality: str = "draft",
):
    """
    Draw a spectrum background as a pcolormesh on the given Axes.

    Parameters
    ----------
    ax : Axes
        Target matplotlib axes.
    spectrum : SpectrumData
        Spectrum data (frequencies, velocities, power).
    x_domain : str
        "frequency" or "wavelength".
    style : StyleConfig, optional
        Global style config for colormap and alpha.
    curve : OffsetCurve, optional
        If provided, use per-curve spectrum overrides (cmap, alpha).
    quality : str
        "draft" (downsample for canvas) or "high" (full resolution).
    """
    if not spectrum.has_data:
        return

    # Per-curve overrides > global style > defaults
    if curve is not None:
        cmap = curve.spectrum_cmap
        alpha = curve.spectrum_alpha
    elif style is not None:
        cmap = style.spectrum_cmap
        alpha = style.spectrum_alpha
    else:
        cmap = "jet"
        alpha = 0.85

    freq = spectrum.frequencies
    vel = spectrum.velocities
    power = spectrum.power

    if power.ndim != 2:
        return

    # Downsample for draft quality (canvas rendering)
    max_px = 200
    if quality == "draft":
        r, c = power.shape
        rs = max(1, r // max_px)
        cs = max(1, c // max_px)
        power = _downsample_2d(power, max_px, max_px)
        freq = _downsample_1d(freq, cs) if freq.ndim == 1 else freq
        vel = _downsample_1d(vel, rs) if vel.ndim == 1 else vel

    if x_domain == "frequency":
        x = freq
    else:
        x = freq

    try:
        ax.pcolormesh(
            x, vel, power,
            cmap=cmap,
            alpha=alpha,
            shading="auto",
            zorder=1,
            rasterized=True,
        )
    except Exception:
        try:
            ax.pcolormesh(
                x, vel, power.T,
                cmap=cmap,
                alpha=alpha,
                shading="auto",
                zorder=1,
                rasterized=True,
            )
        except Exception:
            pass
