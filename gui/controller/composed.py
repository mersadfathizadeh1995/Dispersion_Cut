"""Refactored controller using composition architecture.

This module provides `InteractiveRemovalWithLayers`, a controller that uses
composition with handler delegates instead of a monolithic class.

Each handler encapsulates specific functionality:
- SpectrumHandler: Spectrum background loading/rendering
- ToolsHandler: Line delete and selection tools
- DialogsHandler: Qt dialogs for settings
- FileIOHandler: File save/load operations
- StateHandler: State persistence
- EditHandler: Delete/undo/redo/filter
- AddHandler: Add data/layer operations
- VisualizationHandler: Legend, average, k-guides
"""

from __future__ import annotations

from typing import Dict, List, Optional

from dc_cut.gui.controller.base import BaseInteractiveRemoval
from dc_cut.gui.controller.handlers import (
    SpectrumHandler,
    ToolsHandler,
    DialogsHandler,
    FileIOHandler,
    StateHandler,
    EditHandler,
    AddHandler,
    VisualizationHandler,
)
from dc_cut.core.models import LayersModel
from dc_cut.gui.controller.nf_inspector import NearFieldInspector
from dc_cut.gui.controller.line_tool import LineSelector
from dc_cut.gui.controller.inclined_rect_tool import InclinedRectTool
from dc_cut.services.actions import ActionRegistry
from dc_cut.services.mpl_compat import patch_toolbar_home
from dc_cut.services import log


class InteractiveRemovalWithLayers(BaseInteractiveRemoval):
    """Controller with composition-based modular architecture.

    Uses handler delegates for specific functionality, making the code
    more testable, maintainable, and easier to extend.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize callback for shell integration
        self.on_layers_changed = None
        self.on_spectrum_loaded = None

        # Initialize handlers (composition pattern)
        self.spectrum = SpectrumHandler(self)
        self.tools = ToolsHandler(self)
        self.dialogs = DialogsHandler(self)
        self.file_io = FileIOHandler(self)
        self.state = StateHandler(self)
        self.edit = EditHandler(self)
        self.add = AddHandler(self)
        self.viz = VisualizationHandler(self)

        # Setup toolbar and event hooks
        self._setup_toolbar_home()
        self._setup_event_hooks()

        # Initialize LayersModel
        self._init_layers_model()

        # Initialize NearFieldInspector
        self._init_nf_evaluator()

        # Register actions
        self._register_actions()

        # Initialize line selector tools
        self._init_line_selectors()

        # Initialize inclined rectangle tools
        self._init_inclined_rect_tools()

        # Render default averages at startup so checked-by-default
        # items match what is shown on canvas.
        try:
            if bool(getattr(self, 'show_average', False)) or bool(getattr(self, 'show_average_wave', False)):
                self._update_average_line()
        except Exception:
            log.debug("Initial average line render skipped", exc_info=True)

        log.info("Controller initialized with composition handlers")

    def _setup_toolbar_home(self) -> None:
        """Patch toolbar Home button to respect view mode."""
        try:
            patch_toolbar_home(self.fig, on_after=self._on_home_after)
        except Exception:
            pass

    def _on_home_after(self) -> None:
        """Handler called after Home button pressed."""
        try:
            self._apply_view_mode(getattr(self, 'view_mode', 'both'))
            self._apply_axis_limits()
        except Exception:
            pass

    def _setup_event_hooks(self) -> None:
        """Setup matplotlib event connections."""
        self._selection_active = False
        self._enforcing_limits = False

        # Resize event for configure-subplots
        try:
            def _on_configure_closed(evt):
                try:
                    self._apply_view_mode(getattr(self, 'view_mode', 'both'))
                    self._apply_axis_limits()
                    self.fig.canvas.draw_idle()
                except Exception:
                    pass

            self.fig.canvas.mpl_connect('resize_event', _on_configure_closed)
        except Exception:
            pass

        # Draw event for enforcing limits
        try:
            def _on_draw(evt):
                if not bool(getattr(self, 'auto_limits', True)):
                    return
                if bool(getattr(self, '_selection_active', False)):
                    return
                if self._enforcing_limits:
                    return
                self._enforcing_limits = True
                try:
                    self._apply_axis_limits()
                finally:
                    self._enforcing_limits = False

            self.fig.canvas.mpl_connect('draw_event', _on_draw)
        except Exception:
            pass

        # Mouse events for selection tracking
        try:
            def _on_press(evt):
                if evt is None or getattr(evt, 'button', None) != 1:
                    return
                if evt.inaxes not in (self.ax_freq, self.ax_wave):
                    return
                self._selection_active = True

            def _on_release(evt):
                if evt is None or getattr(evt, 'button', None) != 1:
                    return
                self._selection_active = False
                if bool(getattr(self, 'auto_limits', True)):
                    self._apply_axis_limits()
                    try:
                        self.fig.canvas.draw_idle()
                    except Exception:
                        pass

            self.fig.canvas.mpl_connect('button_press_event', _on_press)
            self.fig.canvas.mpl_connect('button_release_event', _on_release)
        except Exception:
            pass

    def _init_layers_model(self) -> None:
        """Initialize LayersModel from current arrays."""
        try:
            labels = (
                list(self.offset_labels[:len(self.velocity_arrays)])
                if hasattr(self, 'offset_labels')
                else [f"Offset {i+1}" for i in range(len(self.velocity_arrays))]
            )
            self._layers_model = LayersModel.from_arrays(
                self.velocity_arrays,
                self.frequency_arrays,
                self.wavelength_arrays,
                labels,
            )
        except Exception:
            self._layers_model = None

    @property
    def model(self):
        """Property alias for _layers_model for external access."""
        return getattr(self, '_layers_model', None)

    def _init_nf_evaluator(self) -> None:
        """Initialize NearFieldInspector facade."""
        try:
            self.nf_evaluator = NearFieldInspector(self)
        except Exception:
            # Minimal stub
            class _Stub:
                def start_with(self, label, thr, open_checklist=False):
                    pass

                def cancel(self):
                    pass

                def apply_deletions(self, indices):
                    pass

                def update_threshold(self, thr):
                    pass

                def get_current_arrays(self):
                    return None

            self.nf_evaluator = _Stub()

    def _register_actions(self) -> None:
        """Register actions with ActionRegistry."""
        try:
            if not hasattr(self, 'actions') or self.actions is None:
                self.actions = ActionRegistry()

            # File actions
            self.actions.add(
                id="file.save_passive_stats",
                text="Save Passive Stats…",
                shortcut=None,
                callback=lambda: self.file_io.save_passive_stats(),
            )
            if self.actions.try_get('file.load_spectrum') is None:
                self.actions.add(
                    id="file.load_spectrum",
                    text="Load Spectrum…",
                    shortcut=None,
                    callback=lambda: self.file_io.load_spectrum_dialog(),
                )
            if self.actions.try_get('file.save_state') is None:
                self.actions.add(
                    id="file.save_state",
                    text="Save State…",
                    shortcut="Ctrl+S",
                    callback=lambda: self.file_io.save_session(),
                )
            if self.actions.try_get('file.save_dc') is None:
                self.actions.add(
                    id="file.save_dc",
                    text="Save Dispersion TXT…",
                    shortcut=None,
                    callback=lambda: self.file_io.save_dispersion_txt(),
                )

            # Edit actions
            if self.actions.try_get('edit.delete') is None:
                self.actions.add(
                    id="edit.delete",
                    text="Delete",
                    callback=lambda: self.edit.delete(),
                    shortcut=None,
                )
            if self.actions.try_get('edit.cancel') is None:
                self.actions.add(
                    id="edit.cancel",
                    text="Cancel Selection",
                    callback=lambda: self._on_cancel(None),
                    shortcut=None,
                )
            if self.actions.try_get('edit.undo') is None:
                self.actions.add(
                    id="edit.undo",
                    text="Undo",
                    callback=lambda: self.edit.undo(),
                    shortcut=None,
                )
            if self.actions.try_get('edit.redo') is None:
                self.actions.add(
                    id="edit.redo",
                    text="Redo",
                    callback=lambda: self.edit.redo(),
                    shortcut=None,
                )

            # View actions
            if self.actions.try_get('view.both') is None:
                self.actions.add(
                    id="view.both",
                    text="Both plots",
                    callback=lambda: self._apply_view_mode('both'),
                    shortcut=None,
                )
            if self.actions.try_get('view.freq') is None:
                self.actions.add(
                    id="view.freq",
                    text="Phase-vel vs Freq",
                    callback=lambda: self._apply_view_mode('freq_only'),
                    shortcut=None,
                )
            if self.actions.try_get('view.wave') is None:
                self.actions.add(
                    id="view.wave",
                    text="Wave vs Vel",
                    callback=lambda: self._apply_view_mode('wave_only'),
                    shortcut=None,
                )

            # Tool actions
            if self.actions.try_get('edit.line_delete') is None:
                self.actions.add(
                    id="edit.line_delete",
                    text="Line Delete Tool",
                    callback=lambda: self.tools.activate_line_tool(),
                    shortcut=None,
                )
            if self.actions.try_get('edit.box_select') is None:
                self.actions.add(
                    id="edit.box_select",
                    text="Box Select Tool",
                    callback=lambda: self.tools.activate_box_tool(),
                    shortcut=None,
                )
            if self.actions.try_get('edit.inclined_rect') is None:
                self.actions.add(
                    id="edit.inclined_rect",
                    text="Inclined Rectangle Tool",
                    callback=lambda: self.tools.activate_inclined_rect_tool(),
                    shortcut=None,
                )
        except Exception:
            pass

    def _init_line_selectors(self) -> None:
        """Initialize line selector tools for both axes."""
        self._current_tool = 'box'
        self._line_selector_freq = None
        self._line_selector_wave = None

        try:
            self._line_selector_freq = LineSelector(
                self.ax_freq,
                on_select=lambda x1, y1, x2, y2, side: self.tools.on_line_delete_freq(
                    x1, y1, x2, y2, side
                ),
            )
            self._line_selector_wave = LineSelector(
                self.ax_wave,
                on_select=lambda x1, y1, x2, y2, side: self.tools.on_line_delete_wave(
                    x1, y1, x2, y2, side
                ),
            )
        except Exception:
            pass

    def _init_inclined_rect_tools(self) -> None:
        """Initialize inclined rectangle tools for both axes."""
        self._inclined_rect_tool_freq = None
        self._inclined_rect_tool_wave = None

        try:
            self._inclined_rect_tool_freq = InclinedRectTool(
                self.ax_freq,
                on_confirm=lambda corners, patch: self._on_inclined_rect_confirm_freq(
                    corners, patch
                ),
            )
            self._inclined_rect_tool_wave = InclinedRectTool(
                self.ax_wave,
                on_confirm=lambda corners, patch: self._on_inclined_rect_confirm_wave(
                    corners, patch
                ),
            )
        except Exception:
            pass

    def _on_inclined_rect_confirm_freq(self, corners, patch) -> None:
        """Handle confirmed inclined rectangle on frequency plot."""
        self.inclined_boxes_freq.append(corners)
        self.inclined_patches_freq.append(patch)

    def _on_inclined_rect_confirm_wave(self, corners, patch) -> None:
        """Handle confirmed inclined rectangle on wavelength plot."""
        self.inclined_boxes_wave.append(corners)
        self.inclined_patches_wave.append(patch)

    # ==================== DELEGATING METHODS ====================
    # These methods delegate to handlers while maintaining backward compatibility

    def _update_legend(self) -> None:
        """Update legend (delegates to viz handler)."""
        self.viz.update_legend()

    def _update_average_line(self) -> None:
        """Update average lines (delegates to viz handler)."""
        self.viz.update_average_line()

    def _apply_axis_limits(self) -> None:
        """Apply axis limits (delegates to viz handler)."""
        self.viz.apply_axis_limits()

    def _draw_k_guides(self) -> None:
        """Draw k-guides (delegates to viz handler)."""
        self.viz.draw_k_guides()

    def _clear_k_guides(self) -> None:
        """Clear k-guides (delegates to viz handler)."""
        self.viz.clear_k_guides()

    def _apply_axis_scales(self) -> None:
        """Apply axis scales (delegates to base)."""
        super()._apply_axis_scales()

    def _draw_wavelength_lines(self) -> None:
        """Draw wavelength (lambda) reference lines (delegates to viz handler)."""
        self.viz.draw_wavelength_lines()

    def _clear_wavelength_lines(self) -> None:
        """Clear wavelength (lambda) reference lines (delegates to viz handler)."""
        self.viz.clear_wavelength_lines()

    def _enable_save_added(self, enable: bool) -> None:
        """Enable/disable save button (delegates to add handler)."""
        self.add.enable_save_button(enable)

    def get_current_state(self) -> dict:
        """Get current state (delegates to state handler)."""
        return self.state.get_current_state()

    def apply_state(self, state_dict: dict) -> None:
        """Apply state (delegates to state handler)."""
        self.state.apply_state(state_dict)

    def get_current_tool(self) -> str:
        """Get current tool (delegates to tools handler)."""
        return self.tools.get_current_tool()

    # ==================== SPECTRUM METHODS ====================

    def load_spectrum_for_layer(self, layer_idx: int, npz_path: str) -> bool:
        """Load spectrum for layer (delegates to spectrum handler)."""
        return self.spectrum.load_for_layer(layer_idx, npz_path)

    def load_combined_spectrum_for_layers(self, npz_path: str) -> Dict[int, bool]:
        """Load combined spectrum (delegates to spectrum handler)."""
        return self.spectrum.load_combined_for_layers(npz_path)

    def _render_spectrum_backgrounds(self) -> None:
        """Render spectrum backgrounds (delegates to spectrum handler)."""
        self.spectrum.render_backgrounds()

    def _clear_all_spectrum_backgrounds(self) -> None:
        """Clear all spectrum backgrounds (delegates to spectrum handler)."""
        self.spectrum.clear_all()

    def set_layer_spectrum_visibility(self, layer_idx: int, visible: bool) -> None:
        """Set layer spectrum visibility (delegates to spectrum handler)."""
        self.spectrum.set_visibility(layer_idx, visible)

    def set_layer_spectrum_alpha(self, layer_idx: int, alpha: float) -> None:
        """Set layer spectrum alpha (delegates to spectrum handler)."""
        self.spectrum.set_alpha(layer_idx, alpha)

    def toggle_all_spectra(self, enabled: bool) -> None:
        """Toggle all spectra (delegates to spectrum handler)."""
        self.spectrum.toggle_all(enabled)

    def _on_layer_visibility_changed(self) -> None:
        """Handle layer visibility change (delegates to spectrum handler)."""
        self.spectrum.on_layer_visibility_changed()

    # ==================== STATE METHODS ====================

    def _preserve_spectrum_state(self) -> dict:
        """Preserve spectrum state (delegates to state handler)."""
        return self.state.preserve_spectrum_state()

    def _restore_spectrum_state(self, spectrum_state: dict) -> None:
        """Restore spectrum state (delegates to state handler)."""
        self.state.restore_spectrum_state(spectrum_state)

    # ==================== EVENT HANDLERS ====================
    # Override base class event handlers to use composition

    def _on_delete(self, event) -> None:
        """Handle delete (delegates to edit handler)."""
        self.edit.delete(event)

    def _on_undo(self, event) -> None:
        """Handle undo (delegates to edit handler)."""
        if not self.edit.undo(event):
            try:
                super()._on_undo(event)
            except Exception:
                pass

    def _on_redo(self, event) -> None:
        """Handle redo (delegates to edit handler)."""
        if not self.edit.redo(event):
            try:
                super()._on_redo(event)
            except Exception:
                pass

    def _on_filter_values(self, event) -> None:
        """Handle filter (delegates to edit handler)."""
        if not self.edit.filter_values(event):
            try:
                super()._on_filter_values(event)
            except Exception:
                pass

    def _on_add_data(self, event) -> None:
        """Handle add data (delegates to add handler)."""
        if not self.add.add_data(event):
            try:
                super()._on_add_data(event)
            except Exception:
                pass

    def _on_add_layer(self, event) -> None:
        """Handle add layer (delegates to add handler)."""
        if not self.add.add_layer(event):
            try:
                super()._on_add_layer(event)
            except Exception:
                pass

    def _on_save_added_data(self, event) -> None:
        """Handle save added data (delegates to add handler)."""
        if not self.add.save_added_data(event):
            try:
                super()._on_save_added_data(event)
            except Exception:
                pass

    def _on_save_session(self, event) -> None:
        """Handle save session (delegates to file_io handler)."""
        if not self.file_io.save_session(event):
            try:
                super()._on_save_session(event)
            except Exception:
                pass

    def _on_quit(self, event) -> None:
        """Handle quit/save TXT (delegates to file_io handler)."""
        if not self.file_io.save_dispersion_txt(event):
            try:
                super()._on_quit(event)
            except Exception:
                pass

    def _on_save_passive_stats(self, event) -> None:
        """Handle save passive stats (delegates to file_io handler)."""
        self.file_io.save_passive_stats(event)

    def _on_load_spectrum(self, event) -> None:
        """Handle load spectrum (delegates to file_io handler)."""
        self.file_io.load_spectrum_dialog(event)

    def _prompt_load_spectrum(self, saved_path: str) -> None:
        """Prompt to load spectrum (delegates to file_io handler)."""
        self.file_io.prompt_load_spectrum(saved_path)

    def _on_set_xlim(self, event) -> None:
        """Handle set xlim (delegates to dialogs handler)."""
        if not self.dialogs.set_xlim(event):
            try:
                super()._on_set_xlim(event)
            except Exception:
                pass

    def _on_set_ylim(self, event) -> None:
        """Handle set ylim (delegates to dialogs handler)."""
        if not self.dialogs.set_ylim(event):
            try:
                super()._on_set_ylim(event)
            except Exception:
                pass

    def _on_set_average_resolution(self, event) -> None:
        """Handle set average resolution (delegates to dialogs handler)."""
        if not self.dialogs.set_average_resolution(event):
            try:
                super()._on_set_average_resolution(event)
            except Exception:
                pass

    def _activate_line_tool(self) -> None:
        """Activate line tool (delegates to tools handler)."""
        self.tools.activate_line_tool()

    def _activate_box_tool(self) -> None:
        """Activate box tool (delegates to tools handler)."""
        self.tools.activate_box_tool()

    def _activate_inclined_rect_tool(self) -> None:
        """Activate inclined rectangle tool (delegates to tools handler)."""
        self.tools.activate_inclined_rect_tool()

    def _on_line_delete_freq(
        self, x1: float, y1: float, x2: float, y2: float, side: str
    ) -> None:
        """Handle line delete on freq plot (delegates to tools handler)."""
        self.tools.on_line_delete_freq(x1, y1, x2, y2, side)

    def _on_line_delete_wave(
        self, x1: float, y1: float, x2: float, y2: float, side: str
    ) -> None:
        """Handle line delete on wave plot (delegates to tools handler)."""
        self.tools.on_line_delete_wave(x1, y1, x2, y2, side)

    def _perform_line_delete(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        side: str,
        use_freq: bool = True,
    ) -> None:
        """Perform line delete (delegates to tools handler)."""
        self.tools._perform_line_delete(x1, y1, x2, y2, side, use_freq)

    # ==================== UTILITY METHODS ====================

    def _smoke_autoscale(self) -> None:
        """Developer smoke check for autoscale behavior."""
        try:
            # Home equivalent
            try:
                mgr = self.fig.canvas.manager
                tb = getattr(mgr, 'toolbar', None)
                if tb is not None and hasattr(tb, 'home'):
                    tb.home()
            except Exception:
                pass
            self._apply_axis_limits()

            # Simulate resize
            try:
                sz = self.fig.get_size_inches()
                self.fig.set_size_inches(sz[0] + 0.01, sz[1] + 0.01, forward=True)
                self.fig.set_size_inches(*sz, forward=True)
            except Exception:
                pass
            self._apply_axis_limits()

            # Check add-mode
            if bool(getattr(self, 'add_mode', False)):
                if getattr(self, '_add_v', None) is not None:
                    self._apply_axis_limits()

            try:
                self.fig.canvas.draw_idle()
            except Exception:
                pass
        except Exception:
            pass
