"""Spectrum background loading and rendering handler.

Handles all spectrum-related functionality including:
- Loading spectrum NPZ files for individual or combined layers
- Rendering spectrum backgrounds on the frequency plot
- Managing spectrum visibility and alpha per layer
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import numpy as np
import matplotlib.cm as cm

from dc_cut.core.spectrum_loader import (
    load_spectrum_npz,
    load_combined_spectrum_npz,
    match_csv_labels_to_spectrum,
)
from dc_cut.services.prefs import get_pref, set_pref
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.core.base_controller import BaseInteractiveRemoval


class SpectrumHandler:
    """Handles spectrum background loading and rendering."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize spectrum handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller
        self._last_spectrum_path: Optional[str] = None

    def load_for_layer(self, layer_idx: int, npz_path: str) -> bool:
        """Load power spectrum background for a specific layer.

        Parameters
        ----------
        layer_idx : int
            Index of the layer to load spectrum for.
        npz_path : str
            Path to spectrum .npz file.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        try:
            spectrum_data = load_spectrum_npz(npz_path)
            
            if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
                return False
            
            if not (0 <= layer_idx < len(self._ctrl._layers_model.layers)):
                return False
            
            layer = self._ctrl._layers_model.layers[layer_idx]
            layer.spectrum_data = spectrum_data
            layer.spectrum_alpha = get_pref('default_spectrum_alpha', 0.5)
            layer.spectrum_visible = get_pref('show_spectra', True)
            
            self.render_backgrounds()
            return True
        except Exception as e:
            log.error(f"Failed to load spectrum: {e}")
            return False

    def load_combined_for_layers(self, npz_path: str) -> Dict[int, bool]:
        """Load combined power spectrum NPZ and assign to matching layers.

        For combined CSV files, the NPZ contains spectra for multiple offsets.
        This method matches each layer's label to the appropriate spectrum.

        Parameters
        ----------
        npz_path : str
            Path to combined spectrum .npz file.

        Returns
        -------
        Dict[int, bool]
            Dictionary mapping layer index to success (True/False).
        """
        results: Dict[int, bool] = {}
        
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return results
        
        try:
            spectra_by_offset = load_combined_spectrum_npz(npz_path)
            if not spectra_by_offset:
                log.warning(f"No spectra found in combined NPZ: {npz_path}")
                return results
            
            csv_labels = [layer.label for layer in self._ctrl._layers_model.layers]
            matches = match_csv_labels_to_spectrum(csv_labels, spectra_by_offset)
            
            default_alpha = get_pref('default_spectrum_alpha', 0.5)
            show_spectra = get_pref('show_spectra', True)
            
            for layer_idx, offset_key in matches.items():
                try:
                    layer = self._ctrl._layers_model.layers[layer_idx]
                    layer.spectrum_data = spectra_by_offset[offset_key]
                    layer.spectrum_alpha = default_alpha
                    layer.spectrum_visible = show_spectra
                    results[layer_idx] = True
                except Exception as e:
                    results[layer_idx] = False
                    log.warning(f"Failed to assign spectrum to layer {layer_idx}: {e}")
            
            matched = sum(1 for v in results.values() if v)
            total = len(self._ctrl._layers_model.layers)
            log.info(f"Combined spectrum: matched {matched}/{total} layers from {npz_path}")
            
            if any(results.values()):
                self._last_spectrum_path = npz_path
                self.render_backgrounds()
                
                # Notify spectrum dock if callback exists
                if hasattr(self._ctrl, 'on_spectrum_loaded') and self._ctrl.on_spectrum_loaded:
                    self._ctrl.on_spectrum_loaded()
        except Exception as e:
            log.error(f"Failed to load combined spectrum: {e}")
        
        return results

    def render_backgrounds(self) -> None:
        """Render spectrum background for the currently active spectrum layer.

        Only ONE spectrum is shown at a time to avoid overlapping.
        The shown spectrum is determined by:
        1. The first layer with spectrum_visible=True and visible line, OR
        2. If no match, the first layer with spectrum_visible=True
        """
        if not get_pref('show_spectra', True):
            self.clear_all()
            return
        
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        
        # Clear all existing spectrum images first
        for layer in self._ctrl._layers_model.layers:
            if layer.spectrum_image is not None:
                self._remove_spectrum_image(layer)
                layer.spectrum_image = None
        
        # Find which layer's spectrum to show (only one at a time)
        spectrum_to_show = self._find_active_spectrum_layer()
        
        if spectrum_to_show is not None:
            self._render_single(spectrum_to_show)
        
        try:
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def _find_active_spectrum_layer(self) -> Optional[int]:
        """Find which layer should show its spectrum.

        Returns
        -------
        Optional[int]
            Layer index to show spectrum for, or None.
        """
        # Priority: layer with spectrum_visible AND visible line
        for i, layer in enumerate(self._ctrl._layers_model.layers):
            if layer.spectrum_visible and layer.spectrum_data is not None:
                try:
                    if i < len(self._ctrl.lines_freq) and self._ctrl.lines_freq[i].get_visible():
                        return i
                except Exception:
                    pass
        
        # Fallback: first with spectrum_visible
        for i, layer in enumerate(self._ctrl._layers_model.layers):
            if layer.spectrum_visible and layer.spectrum_data is not None:
                return i
        
        return None

    def _render_single(self, layer_idx: int) -> None:
        """Render spectrum background for a single layer.

        Parameters
        ----------
        layer_idx : int
            Index of the layer to render spectrum for.
        """
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        
        if not (0 <= layer_idx < len(self._ctrl._layers_model.layers)):
            return
        
        layer = self._ctrl._layers_model.layers[layer_idx]
        
        if layer.spectrum_data is None or not layer.spectrum_visible:
            return
        
        spectrum = layer.spectrum_data
        power = spectrum['power']
        frequencies = spectrum['frequencies']
        velocities = spectrum['velocities']
        
        colormap_name = get_pref('spectrum_colormap', 'viridis')
        try:
            cmap = cm.get_cmap(colormap_name)
        except Exception:
            cmap = cm.get_cmap('viridis')
        
        render_mode = get_pref('spectrum_render_mode', 'imshow')
        
        if render_mode == 'contour':
            F, V = np.meshgrid(frequencies, velocities)
            layer.spectrum_image = self._ctrl.ax_freq.contourf(
                F, V, power,
                levels=30,
                cmap=cmap,
                alpha=layer.spectrum_alpha,
                zorder=0,
            )
        else:
            extent = [frequencies[0], frequencies[-1], velocities[0], velocities[-1]]
            layer.spectrum_image = self._ctrl.ax_freq.imshow(
                power,
                aspect='auto',
                origin='lower',
                extent=extent,
                cmap=cmap,
                alpha=layer.spectrum_alpha,
                zorder=0,
                interpolation='bilinear',
            )

    def _remove_spectrum_image(self, layer) -> None:
        """Remove spectrum image from layer (handles both imshow and contourf)."""
        if layer.spectrum_image is None:
            return
        
        try:
            if hasattr(layer.spectrum_image, 'collections'):
                # QuadContourSet from contourf
                for coll in layer.spectrum_image.collections:
                    try:
                        coll.remove()
                    except Exception:
                        pass
            else:
                # AxesImage from imshow
                layer.spectrum_image.remove()
        except Exception:
            pass

    def clear_all(self) -> None:
        """Remove all spectrum background images."""
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        
        for layer in self._ctrl._layers_model.layers:
            if layer.spectrum_image is not None:
                self._remove_spectrum_image(layer)
                layer.spectrum_image = None
        
        try:
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def set_visibility(self, layer_idx: int, visible: bool) -> None:
        """Toggle visibility of a layer's spectrum background.

        Parameters
        ----------
        layer_idx : int
            Index of the layer.
        visible : bool
            True to show, False to hide.
        """
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        
        if 0 <= layer_idx < len(self._ctrl._layers_model.layers):
            layer = self._ctrl._layers_model.layers[layer_idx]
            layer.spectrum_visible = visible
            self.render_backgrounds()

    def set_alpha(self, layer_idx: int, alpha: float) -> None:
        """Set opacity of a layer's spectrum background.

        Parameters
        ----------
        layer_idx : int
            Index of the layer.
        alpha : float
            Opacity value (0.0 = transparent, 1.0 = opaque).
        """
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        
        if 0 <= layer_idx < len(self._ctrl._layers_model.layers):
            layer = self._ctrl._layers_model.layers[layer_idx]
            layer.spectrum_alpha = max(0.0, min(1.0, alpha))
            
            if layer.spectrum_image is not None:
                layer.spectrum_image.set_alpha(layer.spectrum_alpha)
                try:
                    self._ctrl.fig.canvas.draw_idle()
                except Exception:
                    pass

    def toggle_all(self, enabled: bool) -> None:
        """Toggle all spectrum backgrounds on/off.

        Parameters
        ----------
        enabled : bool
            True to show all, False to hide all.
        """
        set_pref('show_spectra', enabled)
        self.render_backgrounds()

    def on_layer_visibility_changed(self) -> None:
        """Hook called when layer visibility changes."""
        self.render_backgrounds()

    def get_last_spectrum_path(self) -> Optional[str]:
        """Get the last loaded spectrum file path."""
        return self._last_spectrum_path

    def set_last_spectrum_path(self, path: str) -> None:
        """Set the last loaded spectrum file path."""
        self._last_spectrum_path = path
