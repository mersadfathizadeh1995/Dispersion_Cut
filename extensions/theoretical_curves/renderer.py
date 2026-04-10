"""Renderer for theoretical dispersion curves on matplotlib axes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional
import numpy as np

if TYPE_CHECKING:
    from dc_cut.extensions.theoretical_curves.config import TheoreticalCurve


class TheoreticalCurveRenderer:
    """Renders theoretical dispersion curves on the frequency and wavelength plots.
    
    Handles:
    - Median line rendering (semilogx)
    - Uncertainty band rendering (fill_between)
    - Visibility toggling
    - Style updates
    """
    
    def __init__(self, controller) -> None:
        """Initialize renderer.
        
        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller with ax_freq and ax_wave axes.
        """
        self._ctrl = controller
        self._curves: Dict[str, "TheoreticalCurve"] = {}
    
    @property
    def curves(self) -> List["TheoreticalCurve"]:
        """Get list of all loaded curves."""
        return list(self._curves.values())
    
    def add_curve(self, curve: "TheoreticalCurve") -> None:
        """Add a theoretical curve and render it.
        
        Parameters
        ----------
        curve : TheoreticalCurve
            Curve to add
        """
        self._curves[curve.curve_id] = curve
        self._render_curve(curve)
        self._redraw()
    
    def remove_curve(self, curve_id: str) -> None:
        """Remove a theoretical curve.
        
        Parameters
        ----------
        curve_id : str
            Unique identifier of the curve to remove
        """
        if curve_id not in self._curves:
            return
        
        curve = self._curves[curve_id]
        self._clear_curve_artists(curve)
        del self._curves[curve_id]
        self._redraw()
    
    def get_curve(self, curve_id: str) -> Optional["TheoreticalCurve"]:
        """Get a curve by its ID."""
        return self._curves.get(curve_id)
    
    def set_visibility(self, curve_id: str, visible: bool) -> None:
        """Set overall visibility of a curve.
        
        Parameters
        ----------
        curve_id : str
            Curve identifier
        visible : bool
            True to show, False to hide
        """
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.visible = visible
        self._update_visibility(curve)
        self._redraw()
    
    def set_median_visibility(self, curve_id: str, visible: bool) -> None:
        """Set visibility of the median line."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.median_visible = visible
        self._update_visibility(curve)
        self._redraw()
    
    def set_band_visibility(self, curve_id: str, visible: bool) -> None:
        """Set visibility of the uncertainty band."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.band_visible = visible
        self._update_visibility(curve)
        self._redraw()
    
    def set_band_alpha(self, curve_id: str, alpha: float) -> None:
        """Set opacity of the uncertainty band."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.style.band_alpha = max(0.0, min(1.0, alpha))
        
        if curve._band_fill_freq is not None:
            curve._band_fill_freq.set_alpha(curve.style.band_alpha)
        if curve._band_fill_wave is not None:
            curve._band_fill_wave.set_alpha(curve.style.band_alpha)
        
        self._redraw()
    
    def set_median_color(self, curve_id: str, color: str) -> None:
        """Set color of the median line."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.style.median_color = color
        
        if curve._median_line_freq is not None:
            curve._median_line_freq.set_color(color)
        if curve._median_line_wave is not None:
            curve._median_line_wave.set_color(color)
        
        self._redraw()
    
    def set_median_alpha(self, curve_id: str, alpha: float) -> None:
        """Set opacity of the median line."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.style.median_alpha = max(0.0, min(1.0, alpha))
        
        if curve._median_line_freq is not None:
            curve._median_line_freq.set_alpha(curve.style.median_alpha)
        if curve._median_line_wave is not None:
            curve._median_line_wave.set_alpha(curve.style.median_alpha)
        
        self._redraw()
    
    def set_band_color(self, curve_id: str, color: str) -> None:
        """Set color of the uncertainty band."""
        curve = self._curves.get(curve_id)
        if curve is None:
            return
        
        curve.style.band_color = color
        self._clear_curve_artists(curve)
        self._render_curve(curve)
        self._redraw()
    
    def render_all(self) -> None:
        """Re-render all curves."""
        for curve in self._curves.values():
            self._clear_curve_artists(curve)
            self._render_curve(curve)
        self._redraw()
    
    def clear_all(self) -> None:
        """Remove all theoretical curves."""
        for curve in list(self._curves.values()):
            self._clear_curve_artists(curve)
        self._curves.clear()
        self._redraw()
    
    def _render_curve(self, curve: "TheoreticalCurve") -> None:
        """Render a single curve on both axes."""
        if not curve.visible:
            return
        
        ax_freq = self._ctrl.ax_freq
        ax_wave = self._ctrl.ax_wave
        style = curve.style
        
        freq = curve.frequencies
        vel_median = curve.median
        vel_lower = curve.lower
        vel_upper = curve.upper
        wavelengths = curve.wavelengths
        
        valid_freq = np.isfinite(freq) & np.isfinite(vel_median)
        valid_wave = np.isfinite(wavelengths) & np.isfinite(vel_median)
        
        if curve.band_visible and np.any(valid_freq):
            curve._band_fill_freq = ax_freq.fill_between(
                freq[valid_freq],
                vel_lower[valid_freq],
                vel_upper[valid_freq],
                color=style.band_color,
                alpha=style.band_alpha,
                zorder=1,
                label='_nolegend_',
            )
        
        if curve.band_visible and np.any(valid_wave):
            curve._band_fill_wave = ax_wave.fill_between(
                wavelengths[valid_wave],
                vel_lower[valid_wave],
                vel_upper[valid_wave],
                color=style.band_color,
                alpha=style.band_alpha,
                zorder=1,
                label='_nolegend_',
            )
        
        if curve.median_visible and np.any(valid_freq):
            line, = ax_freq.semilogx(
                freq[valid_freq],
                vel_median[valid_freq],
                color=style.median_color,
                linewidth=style.median_linewidth,
                linestyle=style.median_linestyle,
                alpha=style.median_alpha,
                zorder=2,
                label=f"Theoretical: {curve.name}",
            )
            curve._median_line_freq = line
        
        if curve.median_visible and np.any(valid_wave):
            line, = ax_wave.semilogx(
                wavelengths[valid_wave],
                vel_median[valid_wave],
                color=style.median_color,
                linewidth=style.median_linewidth,
                linestyle=style.median_linestyle,
                alpha=style.median_alpha,
                zorder=2,
                label='_nolegend_',
            )
            curve._median_line_wave = line
    
    def _clear_curve_artists(self, curve: "TheoreticalCurve") -> None:
        """Remove matplotlib artists for a curve."""
        ax_freq = self._ctrl.ax_freq
        ax_wave = self._ctrl.ax_wave
        
        for attr in ['_median_line_freq', '_median_line_wave', '_band_fill_freq', '_band_fill_wave']:
            artist = getattr(curve, attr, None)
            if artist is not None:
                try:
                    artist.remove()
                except (ValueError, AttributeError):
                    # Artist may already be removed, try removing from axes directly
                    try:
                        if attr.endswith('_freq') and artist in ax_freq.lines:
                            ax_freq.lines.remove(artist)
                        elif attr.endswith('_freq') and artist in ax_freq.collections:
                            ax_freq.collections.remove(artist)
                        elif attr.endswith('_wave') and artist in ax_wave.lines:
                            ax_wave.lines.remove(artist)
                        elif attr.endswith('_wave') and artist in ax_wave.collections:
                            ax_wave.collections.remove(artist)
                    except (ValueError, AttributeError):
                        pass
                finally:
                    setattr(curve, attr, None)
    
    def _update_visibility(self, curve: "TheoreticalCurve") -> None:
        """Update visibility of curve artists based on current state."""
        show_median = curve.visible and curve.median_visible
        show_band = curve.visible and curve.band_visible
        
        if curve._median_line_freq is not None:
            curve._median_line_freq.set_visible(show_median)
        if curve._median_line_wave is not None:
            curve._median_line_wave.set_visible(show_median)
        if curve._band_fill_freq is not None:
            curve._band_fill_freq.set_visible(show_band)
        if curve._band_fill_wave is not None:
            curve._band_fill_wave.set_visible(show_band)
    
    def _redraw(self) -> None:
        """Redraw the canvas."""
        try:
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass
