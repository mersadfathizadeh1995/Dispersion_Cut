"""Line delete and selection tools handler.

Handles tool activation/deactivation and line-based deletion operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from dc_cut.core.processing.selection import remove_on_side_of_line, line_mask
from dc_cut.visualization.plot_helpers import set_line_xy
from dc_cut.core.history import push_undo
from dc_cut.core.models import LayersModel
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.gui.controller.base import BaseInteractiveRemoval


class ToolsHandler:
    """Handles line delete tool and selection tools."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize tools handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller
        self._current_tool = 'box'

    def get_current_tool(self) -> str:
        """Return the currently active tool name.

        Returns
        -------
        str
            'box', 'line', or 'inclined_rect'.
        """
        return self._current_tool

    def activate_line_tool(self) -> None:
        """Switch to line delete tool mode."""
        self._current_tool = 'line'
        
        # Disable box selectors
        try:
            self._ctrl.rect_selector_freq.set_active(False)
            self._ctrl.rect_selector_wave.set_active(False)
        except Exception:
            pass
        
        # Deactivate inclined rect tools
        try:
            if getattr(self._ctrl, '_inclined_rect_tool_freq', None) is not None:
                self._ctrl._inclined_rect_tool_freq.deactivate()
            if getattr(self._ctrl, '_inclined_rect_tool_wave', None) is not None:
                self._ctrl._inclined_rect_tool_wave.deactivate()
        except Exception:
            pass
        
        # Activate line selectors
        try:
            if self._ctrl._line_selector_freq is not None:
                self._ctrl._line_selector_freq.activate()
            if self._ctrl._line_selector_wave is not None:
                self._ctrl._line_selector_wave.activate()
        except Exception:
            pass
        
        log.info("Line delete tool activated")

    def activate_box_tool(self) -> None:
        """Switch back to box select tool mode."""
        self._current_tool = 'box'
        
        # Deactivate line selectors
        try:
            if self._ctrl._line_selector_freq is not None:
                self._ctrl._line_selector_freq.deactivate()
            if self._ctrl._line_selector_wave is not None:
                self._ctrl._line_selector_wave.deactivate()
        except Exception:
            pass
        
        # Deactivate inclined rect tools
        try:
            if getattr(self._ctrl, '_inclined_rect_tool_freq', None) is not None:
                self._ctrl._inclined_rect_tool_freq.deactivate()
            if getattr(self._ctrl, '_inclined_rect_tool_wave', None) is not None:
                self._ctrl._inclined_rect_tool_wave.deactivate()
        except Exception:
            pass
        
        # Re-enable box selectors
        try:
            self._ctrl.rect_selector_freq.set_active(True)
            self._ctrl.rect_selector_wave.set_active(True)
        except Exception:
            pass
        
        log.info("Box select tool activated")

    def activate_inclined_rect_tool(self) -> None:
        """Switch to inclined rectangle tool mode."""
        self._current_tool = 'inclined_rect'
        
        # Disable box selectors
        try:
            self._ctrl.rect_selector_freq.set_active(False)
            self._ctrl.rect_selector_wave.set_active(False)
        except Exception:
            pass
        
        # Deactivate line selectors
        try:
            if self._ctrl._line_selector_freq is not None:
                self._ctrl._line_selector_freq.deactivate()
            if self._ctrl._line_selector_wave is not None:
                self._ctrl._line_selector_wave.deactivate()
        except Exception:
            pass
        
        # Activate inclined rect tools
        try:
            if getattr(self._ctrl, '_inclined_rect_tool_freq', None) is not None:
                self._ctrl._inclined_rect_tool_freq.activate()
            if getattr(self._ctrl, '_inclined_rect_tool_wave', None) is not None:
                self._ctrl._inclined_rect_tool_wave.activate()
        except Exception:
            pass
        
        log.info("Inclined rectangle tool activated")

    def on_line_delete_freq(
        self, x1: float, y1: float, x2: float, y2: float, side: str
    ) -> None:
        """Handle line delete on frequency plot.

        Parameters
        ----------
        x1, y1, x2, y2 : float
            Two points defining the line.
        side : str
            'above' or 'below' - which side to delete.
        """
        self._perform_line_delete(x1, y1, x2, y2, side, use_freq=True)

    def on_line_delete_wave(
        self, x1: float, y1: float, x2: float, y2: float, side: str
    ) -> None:
        """Handle line delete on wavelength plot.

        Parameters
        ----------
        x1, y1, x2, y2 : float
            Two points defining the line.
        side : str
            'above' or 'below' - which side to delete.
        """
        self._perform_line_delete(x1, y1, x2, y2, side, use_freq=False)

    def _perform_line_delete(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        side: str,
        use_freq: bool = True,
    ) -> None:
        """Perform line-based deletion on all visible layers.

        Parameters
        ----------
        x1, y1, x2, y2 : float
            Two points defining the line.
        side : str
            'above' or 'below' - which side to delete.
        use_freq : bool
            If True, line is in (frequency, velocity) space.
            If False, line is in (wavelength, velocity) space.
        """
        # Push undo state
        try:
            push_undo(self._ctrl)
        except Exception:
            try:
                self._ctrl._save_state()
            except Exception:
                pass
        
        # Preserve spectrum state before model rebuild
        spectrum_state = self._preserve_spectrum_state()
        
        try:
            for i in range(len(self._ctrl.velocity_arrays)):
                v = np.asarray(self._ctrl.velocity_arrays[i])
                f = np.asarray(self._ctrl.frequency_arrays[i])
                w = np.asarray(self._ctrl.wavelength_arrays[i])
                
                # Check visibility on appropriate plot
                visible = self._is_layer_visible(i, use_freq)
                if not visible:
                    continue
                
                # Apply line deletion
                if use_freq:
                    v, f, w = remove_on_side_of_line(v, f, w, x1, y1, x2, y2, side=side)
                else:
                    mask = line_mask(w, v, x1, y1, x2, y2, side=side)
                    keep = ~mask
                    v, f, w = v[keep], f[keep], w[keep]
                
                self._ctrl.velocity_arrays[i] = v
                self._ctrl.frequency_arrays[i] = f
                self._ctrl.wavelength_arrays[i] = w
            
            # Update plot lines
            for i in range(len(self._ctrl.velocity_arrays)):
                set_line_xy(
                    self._ctrl.lines_freq[i],
                    self._ctrl.frequency_arrays[i],
                    self._ctrl.velocity_arrays[i],
                )
                set_line_xy(
                    self._ctrl.lines_wave[i],
                    self._ctrl.wavelength_arrays[i],
                    self._ctrl.velocity_arrays[i],
                )
            
            # Re-average if enabled
            if self._ctrl.show_average or self._ctrl.show_average_wave:
                self._ctrl._update_average_line()
        except Exception as e:
            log.error(f"Line delete failed: {e}")
        
        # Rebuild model and restore spectrum state
        self._rebuild_model_and_restore_spectrum(spectrum_state)
        
        # Refresh UI
        self._refresh_after_edit()

    def _is_layer_visible(self, idx: int, use_freq: bool) -> bool:
        """Check if layer is visible on the specified plot."""
        try:
            if use_freq:
                return self._ctrl.lines_freq[idx].get_visible()
            else:
                return self._ctrl.lines_wave[idx].get_visible()
        except Exception:
            return True

    def _preserve_spectrum_state(self) -> dict:
        """Capture spectrum state from LayersModel before rebuild."""
        spectrum_state = {}
        try:
            if hasattr(self._ctrl, '_layers_model') and self._ctrl._layers_model is not None:
                for i, layer in enumerate(self._ctrl._layers_model.layers):
                    if layer.spectrum_data is not None:
                        spectrum_state[i] = {
                            'spectrum_data': layer.spectrum_data,
                            'spectrum_visible': layer.spectrum_visible,
                            'spectrum_alpha': layer.spectrum_alpha,
                        }
        except Exception:
            pass
        return spectrum_state

    def _rebuild_model_and_restore_spectrum(self, spectrum_state: dict) -> None:
        """Rebuild LayersModel and restore spectrum state."""
        # Clear spectrum images
        try:
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                self._ctrl.spectrum.clear_all()
        except Exception:
            pass
        
        # Rebuild model
        try:
            labels = list(self._ctrl.offset_labels[:len(self._ctrl.velocity_arrays)])
            self._ctrl._layers_model = LayersModel.from_arrays(
                self._ctrl.velocity_arrays,
                self._ctrl.frequency_arrays,
                self._ctrl.wavelength_arrays,
                labels,
            )
        except Exception:
            pass
        
        # Restore spectrum state
        try:
            if spectrum_state and self._ctrl._layers_model is not None:
                for i, data in spectrum_state.items():
                    if i < len(self._ctrl._layers_model.layers):
                        layer = self._ctrl._layers_model.layers[i]
                        layer.spectrum_data = data['spectrum_data']
                        layer.spectrum_visible = data['spectrum_visible']
                        layer.spectrum_alpha = data['spectrum_alpha']
                
                if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                    self._ctrl.spectrum.render_backgrounds()
        except Exception as e:
            log.error(f"Failed to restore spectrum state: {e}")

    def _refresh_after_edit(self) -> None:
        """Refresh UI after edit operation."""
        try:
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass
        
        # Notify layer UI
        try:
            cb = getattr(self._ctrl, 'on_layers_changed', None)
            if cb:
                cb()
        except Exception:
            pass
