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

from dc_cut.core.io.spectrum import (
    load_spectrum_npz,
    load_combined_spectrum_npz,
    match_csv_labels_to_spectrum,
)
from dc_cut.core.rendering.spectrum_render import (
    build_rgba_cache,
    downsample_power,
    resolve_interpolation,
)
from dc_cut.services.prefs import get_pref, set_pref
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.gui.controller.base import BaseInteractiveRemoval


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

        The tolerant core reader is tried first; if that fails, any
        previously-persisted :class:`NpzKeySpec` for this file's
        layout is applied before giving up. GUI callers that still
        need a manual recovery step prompt :class:`MapNpzDialog`
        themselves.

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
        spectrum_data = None
        try:
            spectrum_data = load_spectrum_npz(npz_path)
        except Exception as e:
            log.warning(f"Tolerant spectrum load failed for {npz_path}: {e}")
            spectrum_data = self._load_with_saved_spec(npz_path)

        if spectrum_data is None:
            return False

        try:
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
            log.error(f"Failed to apply spectrum to layer: {e}")
            return False

    def _load_with_saved_spec(self, npz_path: str):
        """Apply a previously-saved NPZ mapping spec if one exists."""
        try:
            from dc_cut.gui.dialogs.map_npz import (
                load_saved_spec,
                read_npz_with_spec,
            )
        except Exception:
            return None
        try:
            spec = load_saved_spec(npz_path)
            if spec is None:
                return None
            records = read_npz_with_spec(npz_path, spec)
            if not records:
                return None
            return records[0].to_dict()
        except Exception as exc:
            log.warning(f"Saved spec load failed for {npz_path}: {exc}")
            return None

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
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return

        # Find which layer's spectrum to show (only one at a time)
        spectrum_to_show = self._find_active_spectrum_layer()

        # Incremental update: if only the active layer should change,
        # the prior render has the same cache key, and incremental
        # updates are enabled, just toggle visibility / alpha instead
        # of tearing the AxesImage down and rebuilding it. This keeps
        # the expensive normalize+colormap path off the draw hot path
        # whenever the user is only changing alpha or toggling display.
        incremental = bool(get_pref('spectrum_perf_incremental_update', True))

        if spectrum_to_show is not None and incremental:
            layer = self._ctrl._layers_model.layers[spectrum_to_show]
            render_key = self._compute_render_key(layer)
            existing_key = getattr(layer, '_spectrum_render_key', None)
            if (
                layer.spectrum_image is not None
                and render_key is not None
                and existing_key == render_key
            ):
                # Hide every other layer, then refresh alpha/visibility on the
                # active one without recreating the artist.
                for i, other in enumerate(self._ctrl._layers_model.layers):
                    if i == spectrum_to_show:
                        continue
                    if other.spectrum_image is not None:
                        try:
                            other.spectrum_image.set_visible(False)
                        except Exception:
                            # Fallback to the legacy teardown if the artist
                            # is in an inconsistent state.
                            self._remove_spectrum_image(other)
                            other.spectrum_image = None
                            other._spectrum_render_key = None
                try:
                    layer.spectrum_image.set_alpha(layer.spectrum_alpha)
                    layer.spectrum_image.set_visible(True)
                except Exception:
                    # Fall through to the full rebuild below.
                    self._remove_spectrum_image(layer)
                    layer.spectrum_image = None
                    layer._spectrum_render_key = None
                else:
                    try:
                        self._ctrl.fig.canvas.draw_idle()
                    except Exception:
                        pass
                    return

        # Full rebuild: tear down every existing spectrum image, then render
        # the newly active one from scratch.
        for layer in self._ctrl._layers_model.layers:
            if layer.spectrum_image is not None:
                self._remove_spectrum_image(layer)
                layer.spectrum_image = None
            if hasattr(layer, '_spectrum_render_key'):
                layer._spectrum_render_key = None

        if spectrum_to_show is not None:
            self._render_single(spectrum_to_show)

        try:
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def _compute_render_key(self, layer) -> Optional[tuple]:
        """Build a lightweight identity key for the layer's current
        spectrum render. Covers every input that actually changes the
        pixel output so the incremental path can safely skip a rebuild
        when the key is unchanged.
        """
        spectrum = layer.spectrum_data
        if spectrum is None:
            return None
        try:
            power = spectrum['power']
            frequencies = spectrum['frequencies']
            velocities = spectrum['velocities']
        except Exception:
            return None
        try:
            power_id = power.ctypes.data
        except Exception:
            power_id = id(power)
        return (
            power_id,
            tuple(power.shape) if hasattr(power, 'shape') else None,
            float(frequencies[0]) if len(frequencies) else 0.0,
            float(frequencies[-1]) if len(frequencies) else 0.0,
            float(velocities[0]) if len(velocities) else 0.0,
            float(velocities[-1]) if len(velocities) else 0.0,
            str(get_pref('spectrum_colormap', 'viridis')),
            str(get_pref('spectrum_render_mode', 'imshow')),
            bool(get_pref('spectrum_perf_downsample', True)),
            int(get_pref('spectrum_perf_max_px', 400)),
            str(get_pref('spectrum_perf_interpolation', 'auto')),
            bool(get_pref('spectrum_perf_rgba_cache', True)),
            bool(get_pref('spectrum_perf_rasterized', True)),
            int(get_pref('spectrum_perf_contour_levels', 12)),
        )

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

        # Performance preferences — each one defaults to the fast path but
        # can be turned off individually from the Preferences dialog.
        use_ds = bool(get_pref('spectrum_perf_downsample', True))
        max_px = int(get_pref('spectrum_perf_max_px', 400))
        use_rgba = bool(get_pref('spectrum_perf_rgba_cache', True))
        interp_pref = str(get_pref('spectrum_perf_interpolation', 'auto'))
        rasterize = bool(get_pref('spectrum_perf_rasterized', True))
        contour_n = int(get_pref('spectrum_perf_contour_levels', 12))

        # Stride-downsample the power array up-front so every render path
        # (imshow / imshow-RGBA / contourf) sees the same smaller grid.
        power_view = downsample_power(power, max_px) if use_ds else power
        if power_view is not power:
            # Downsampling dropped rows/cols; rebuild axis vectors so the
            # extent / meshgrid line up with the reduced array.
            r_stride = max(1, power.shape[0] // power_view.shape[0])
            c_stride = max(1, power.shape[1] // power_view.shape[1])
            frequencies_view = np.asarray(frequencies)[::c_stride]
            velocities_view = np.asarray(velocities)[::r_stride]
            # Guard against rounding mismatches.
            if frequencies_view.size != power_view.shape[1]:
                frequencies_view = np.linspace(
                    float(frequencies[0]), float(frequencies[-1]),
                    power_view.shape[1],
                )
            if velocities_view.size != power_view.shape[0]:
                velocities_view = np.linspace(
                    float(velocities[0]), float(velocities[-1]),
                    power_view.shape[0],
                )
        else:
            frequencies_view = np.asarray(frequencies)
            velocities_view = np.asarray(velocities)

        # Snapshot the current axis limits so the spectrum image does not
        # drive matplotlib's autoscale — axis extents must remain tied to
        # the source-offset (curve) data, not the full frequency/velocity
        # span of the spectrum NPZ.
        ax = self._ctrl.ax_freq
        saved_xlim = ax.get_xlim()
        saved_ylim = ax.get_ylim()
        prev_autoscale_x = ax.get_autoscalex_on()
        prev_autoscale_y = ax.get_autoscaley_on()
        ax.set_autoscale_on(False)

        try:
            if render_mode == 'contour':
                F, V = np.meshgrid(frequencies_view, velocities_view)
                layer.spectrum_image = ax.contourf(
                    F, V, power_view,
                    levels=contour_n,
                    cmap=cmap,
                    alpha=layer.spectrum_alpha,
                    zorder=0,
                )
                # contourf returns a QuadContourSet — matplotlib does not
                # support `rasterized=True` on the set as a whole, only
                # on its child collections.
                if rasterize:
                    try:
                        for coll in layer.spectrum_image.collections:
                            coll.set_rasterized(True)
                    except Exception:
                        pass
            else:
                extent = [
                    float(frequencies_view[0]), float(frequencies_view[-1]),
                    float(velocities_view[0]), float(velocities_view[-1]),
                ]

                # Resolve "auto" interpolation against the axes pixel size so
                # tall, narrow axes don't pay the bilinear cost when the
                # input is already at display resolution.
                try:
                    bbox_px = ax.get_window_extent()
                    output_shape = (int(bbox_px.height), int(bbox_px.width))
                except Exception:
                    output_shape = power_view.shape
                interp = resolve_interpolation(
                    interp_pref, power_view.shape, output_shape,
                )

                if use_rgba:
                    vmin = float(np.nanmin(power_view)) if power_view.size else 0.0
                    vmax = float(np.nanmax(power_view)) if power_view.size else 1.0
                    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmin == vmax:
                        vmax = vmin + 1.0
                    try:
                        rgba = build_rgba_cache(power_view, cmap, vmin, vmax)
                    except Exception:
                        rgba = None
                    if rgba is not None:
                        layer.spectrum_image = ax.imshow(
                            rgba,
                            aspect='auto',
                            origin='lower',
                            extent=extent,
                            alpha=layer.spectrum_alpha,
                            zorder=0,
                            interpolation=interp,
                        )
                        try:
                            layer.spectrum_image.set_rasterized(bool(rasterize))
                        except Exception:
                            pass
                    else:
                        use_rgba = False  # Fall through to the float path.

                if not use_rgba:
                    layer.spectrum_image = ax.imshow(
                        power_view,
                        aspect='auto',
                        origin='lower',
                        extent=extent,
                        cmap=cmap,
                        alpha=layer.spectrum_alpha,
                        zorder=0,
                        interpolation=interp,
                    )
                    try:
                        layer.spectrum_image.set_rasterized(bool(rasterize))
                    except Exception:
                        pass

            # Stash the render key so render_backgrounds can detect a
            # no-op rebuild on the next pass.
            try:
                layer._spectrum_render_key = self._compute_render_key(layer)
            except Exception:
                layer._spectrum_render_key = None
        finally:
            # Restore the user-facing viewport and the previous autoscale
            # state. Using set_xlim/set_ylim here is safe even when the
            # saved limits are the matplotlib default (0, 1) — the next
            # apply_axis_limits() call will overwrite them with values
            # derived from the curves.
            try:
                ax.set_xlim(saved_xlim)
                ax.set_ylim(saved_ylim)
            except Exception:
                pass
            try:
                ax.set_autoscalex_on(prev_autoscale_x)
                ax.set_autoscaley_on(prev_autoscale_y)
            except Exception:
                pass

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
            if hasattr(layer, '_spectrum_render_key'):
                layer._spectrum_render_key = None
        
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
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return
        for layer in self._ctrl._layers_model.layers:
            if layer.spectrum_data is not None:
                layer.spectrum_visible = enabled
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
