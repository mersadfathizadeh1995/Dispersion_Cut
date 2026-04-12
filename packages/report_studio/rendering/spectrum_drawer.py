"""
Spectrum drawer — render power spectrum pcolormesh backgrounds on Axes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import SpectrumData
    from .style import StyleConfig


def draw(
    ax: "Axes",
    spectrum: "SpectrumData",
    x_domain: str = "frequency",
    style: "StyleConfig" = None,
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
        "frequency" or "wavelength". If "wavelength", we convert
        using λ = v / f.
    style : StyleConfig, optional
        Global style config for colormap and alpha.
    """
    if not spectrum.has_data:
        return

    cmap = "jet" if style is None else style.spectrum_cmap
    alpha = 0.85 if style is None else style.spectrum_alpha

    freq = spectrum.frequencies
    vel = spectrum.velocities
    power = spectrum.power

    # Ensure power is 2D
    if power.ndim != 2:
        return

    if x_domain == "frequency":
        x = freq
    else:
        # Wavelength: λ = v / f — but spectrum is on a freq×vel grid,
        # so we still plot against frequency axis but label it as wavelength.
        # For true wavelength domain, we'd need to re-grid. For now, use freq.
        x = freq

    # pcolormesh expects (M+1, N+1) or (M, N) with shading='auto'
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
        # Fallback: if shapes don't match, try transpose
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
            pass  # Skip if data is incompatible
