"""
Spectrum drawer — render power spectrum backgrounds on Axes using imshow.
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


def draw(
    ax: "Axes",
    spectrum: "SpectrumData",
    x_domain: str = "frequency",
    style: "StyleConfig" = None,
    curve: "OffsetCurve" = None,
    quality: str = "draft",
):
    """
    Draw a spectrum background as an imshow heatmap on the given Axes.

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
    if quality == "draft":
        max_px = 200
        power = _downsample_2d(power, max_px, max_px)

    # Determine x-axis values based on domain
    if x_domain == "wavelength" and freq is not None and vel is not None:
        # wavelength = velocity / frequency (guard division by zero)
        safe_freq = np.where(freq > 0, freq, np.nan)
        x = vel.mean() / safe_freq if freq.ndim == 1 else freq
    else:
        x = freq

    if x is None or vel is None or len(x) == 0 or len(vel) == 0:
        return

    # Use imshow with explicit extent for fast, aligned rendering
    extent = [float(x.min()), float(x.max()),
              float(vel.min()), float(vel.max())]

    try:
        im = ax.imshow(
            power, extent=extent, aspect="auto", origin="lower",
            cmap=cmap, alpha=alpha, interpolation="bilinear",
            zorder=1, rasterized=True,
        )
        return im
    except Exception:
        return None
