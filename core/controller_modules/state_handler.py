"""State persistence handler.

Handles saving and restoring controller state including arrays,
preferences, and spectrum settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from dc_cut.core.model import LayersModel
from dc_cut.core.plot import set_line_xy
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.core.base_controller import BaseInteractiveRemoval


class StateHandler:
    """Handles state persistence and restoration."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize state handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller

    def get_current_state(self) -> Dict[str, Any]:
        """Get current controller state as dictionary.

        Returns
        -------
        Dict[str, Any]
            State dictionary containing arrays, preferences, and settings.
        """
        S: Dict[str, Any] = {}

        # Get base state if available
        try:
            if hasattr(super(self._ctrl.__class__, self._ctrl), 'get_current_state'):
                S = super(self._ctrl.__class__, self._ctrl).get_current_state()
        except Exception:
            pass

        # Add k-guides and tick preferences
        S['kmin'] = getattr(self._ctrl, 'kmin', None)
        S['kmax'] = getattr(self._ctrl, 'kmax', None)
        S['show_k_guides'] = bool(getattr(self._ctrl, 'show_k_guides', False))
        S['freq_tick_style'] = getattr(self._ctrl, 'freq_tick_style', 'decades')
        if hasattr(self._ctrl, 'freq_custom_ticks'):
            S['freq_custom_ticks'] = list(getattr(self._ctrl, 'freq_custom_ticks'))

        # Add spectrum settings per layer (NOT the actual data)
        if hasattr(self._ctrl, '_layers_model') and self._ctrl._layers_model is not None:
            S['layer_spectrum_settings'] = []
            for layer in self._ctrl._layers_model.layers:
                S['layer_spectrum_settings'].append({
                    'has_spectrum': layer.spectrum_data is not None,
                    'spectrum_visible': layer.spectrum_visible,
                    'spectrum_alpha': layer.spectrum_alpha,
                })

        # Save spectrum file path for reload
        spectrum_path = None
        if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
            spectrum_path = self._ctrl.spectrum.get_last_spectrum_path()
        elif hasattr(self._ctrl, '_last_spectrum_path'):
            spectrum_path = self._ctrl._last_spectrum_path
        if spectrum_path:
            S['spectrum_path'] = spectrum_path

        return S

    def apply_state(self, state_dict: Dict[str, Any]) -> None:
        """Apply state dictionary to controller.

        Parameters
        ----------
        state_dict : Dict[str, Any]
            State dictionary to apply.
        """
        # Preserve spectrum state before model rebuild
        spectrum_state = self.preserve_spectrum_state()

        # Clear existing spectrum images
        self._clear_spectrum_backgrounds()

        # Apply base state
        try:
            if hasattr(super(self._ctrl.__class__, self._ctrl), 'apply_state'):
                super(self._ctrl.__class__, self._ctrl).apply_state(state_dict)
        except Exception:
            pass

        # Update lines
        self._update_lines_from_arrays()

        # Rebuild LayersModel
        self._rebuild_layers_model()

        # Restore spectrum state
        self.restore_spectrum_state(spectrum_state)

        # Restore spectrum settings from saved state
        if 'layer_spectrum_settings' in state_dict:
            self._apply_spectrum_settings(state_dict['layer_spectrum_settings'])

        log.info("State applied; model rebuilt; ticks/guides/limits applied")

        # Restore tick style and custom ticks
        if 'freq_tick_style' in state_dict:
            self._ctrl.freq_tick_style = state_dict['freq_tick_style']
        if 'freq_custom_ticks' in state_dict:
            self._ctrl.freq_custom_ticks = state_dict['freq_custom_ticks']

        # Restore k-guides
        if 'kmin' in state_dict and state_dict['kmin'] is not None:
            self._ctrl.kmin = float(state_dict['kmin'])
        if 'kmax' in state_dict and state_dict['kmax'] is not None:
            self._ctrl.kmax = float(state_dict['kmax'])
        self._ctrl.show_k_guides = bool(
            state_dict.get('show_k_guides', getattr(self._ctrl, 'show_k_guides', False))
        )

        # Re-apply visual settings
        try:
            self._ctrl._apply_frequency_ticks()
        except Exception:
            pass
        try:
            self._ctrl._draw_k_guides()
        except Exception:
            pass
        try:
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def preserve_spectrum_state(self) -> Dict[int, Dict[str, Any]]:
        """Capture spectrum state from LayersModel before rebuild.

        Returns
        -------
        Dict[int, Dict[str, Any]]
            Dict mapping layer index to spectrum info.
        """
        spectrum_state: Dict[int, Dict[str, Any]] = {}
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

    def restore_spectrum_state(self, spectrum_state: Dict[int, Dict[str, Any]]) -> None:
        """Restore spectrum state to LayersModel after rebuild.

        Parameters
        ----------
        spectrum_state : Dict[int, Dict[str, Any]]
            Dict from preserve_spectrum_state().
        """
        if not spectrum_state:
            return
        if not hasattr(self._ctrl, '_layers_model') or self._ctrl._layers_model is None:
            return

        try:
            for i, data in spectrum_state.items():
                if i < len(self._ctrl._layers_model.layers):
                    layer = self._ctrl._layers_model.layers[i]
                    layer.spectrum_data = data['spectrum_data']
                    layer.spectrum_visible = data['spectrum_visible']
                    layer.spectrum_alpha = data['spectrum_alpha']

            # Re-render spectrum backgrounds
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                self._ctrl.spectrum.render_backgrounds()
        except Exception as e:
            log.error(f"Failed to restore spectrum state: {e}")

    def _clear_spectrum_backgrounds(self) -> None:
        """Clear all spectrum background images."""
        try:
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                self._ctrl.spectrum.clear_all()
            elif hasattr(self._ctrl, '_clear_all_spectrum_backgrounds'):
                self._ctrl._clear_all_spectrum_backgrounds()
        except Exception:
            pass

    def _update_lines_from_arrays(self) -> None:
        """Update line artists from current arrays."""
        try:
            for i in range(min(len(self._ctrl.lines_freq), len(self._ctrl.velocity_arrays))):
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
        except Exception:
            pass

    def _rebuild_layers_model(self) -> None:
        """Rebuild LayersModel from current arrays."""
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

    def _apply_spectrum_settings(self, settings: list) -> None:
        """Apply spectrum settings from saved state."""
        try:
            for i, s in enumerate(settings):
                if i < len(self._ctrl._layers_model.layers):
                    layer = self._ctrl._layers_model.layers[i]
                    layer.spectrum_visible = s.get('spectrum_visible', False)
                    layer.spectrum_alpha = s.get('spectrum_alpha', 0.5)
        except Exception:
            pass
