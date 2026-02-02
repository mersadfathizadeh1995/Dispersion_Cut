"""Edit operations handler.

Handles delete, undo, redo, and filter operations on dispersion curve data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

import numpy as np
import matplotlib

from dc_cut.core.selection import remove_in_freq_box, remove_in_wave_box
from dc_cut.core.inclined_rect_tool import remove_in_polygon_freq, remove_in_polygon_wave
from dc_cut.core.filters import apply_filters
from dc_cut.core.history import push_undo, perform_undo, perform_redo
from dc_cut.core.plot import set_line_xy
from dc_cut.core.model import LayersModel
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.core.base_controller import BaseInteractiveRemoval


class EditHandler:
    """Handles edit operations (delete, undo, redo, filter)."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize edit handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller

    def delete(self, event=None) -> bool:
        """Delete points within current selection boxes (axis-aligned and inclined).

        Returns
        -------
        bool
            True if deletion was performed.
        """
        # Gather all selection boxes
        bxf = list(getattr(self._ctrl, 'bounding_boxes_freq', []))
        bxw = list(getattr(self._ctrl, 'bounding_boxes_wave', []))
        incf = list(getattr(self._ctrl, 'inclined_boxes_freq', []))
        incw = list(getattr(self._ctrl, 'inclined_boxes_wave', []))

        if not bxf and not bxw and not incf and not incw:
            return False

        # Push undo state
        try:
            push_undo(self._ctrl)
        except Exception:
            try:
                self._ctrl._save_state()
            except Exception:
                pass

        # Preserve spectrum state
        spectrum_state = self._preserve_spectrum_state()

        # Apply deletions
        for i in range(len(self._ctrl.velocity_arrays)):
            v = np.asarray(self._ctrl.velocity_arrays[i])
            f = np.asarray(self._ctrl.frequency_arrays[i])
            w = np.asarray(self._ctrl.wavelength_arrays[i])

            if self._ctrl.lines_freq[i].get_visible():
                # Axis-aligned rectangles
                for xmin, xmax, ymin, ymax in bxf:
                    v, f, w = remove_in_freq_box(
                        v, f, w, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax
                    )
                # Inclined rectangles (polygons)
                for corners in incf:
                    v, f, w = remove_in_polygon_freq(v, f, w, corners)

            if self._ctrl.lines_wave[i].get_visible():
                # Axis-aligned rectangles
                for xmin, xmax, ymin, ymax in bxw:
                    v, f, w = remove_in_wave_box(
                        v, f, w, xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax
                    )
                # Inclined rectangles (polygons)
                for corners in incw:
                    v, f, w = remove_in_polygon_wave(v, f, w, corners)

            self._ctrl.velocity_arrays[i] = v
            self._ctrl.frequency_arrays[i] = f
            self._ctrl.wavelength_arrays[i] = w

        # Clear selection patches
        self._clear_selection_patches()

        # Update lines
        self._update_lines()

        # Re-average if enabled
        if self._ctrl.show_average or self._ctrl.show_average_wave:
            self._ctrl._update_average_line()

        # Rebuild model and restore spectrum
        self._rebuild_and_restore(spectrum_state)

        return True

    def undo(self, event=None) -> bool:
        """Undo last operation.

        Returns
        -------
        bool
            True if undo was performed.
        """
        try:
            ok = perform_undo(self._ctrl)
            if not ok:
                return False
        except Exception:
            return False

        # Re-apply view after restore
        try:
            self._ctrl._apply_view_mode(getattr(self._ctrl, 'view_mode', 'both'))
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

        return True

    def redo(self, event=None) -> bool:
        """Redo last undone operation.

        Returns
        -------
        bool
            True if redo was performed.
        """
        try:
            ok = perform_redo(self._ctrl)
            if not ok:
                return False
        except Exception:
            return False

        try:
            self._ctrl._apply_view_mode(getattr(self._ctrl, 'view_mode', 'both'))
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

        return True

    def filter_values(self, event=None) -> bool:
        """Open filter dialog and apply filter to visible layers.

        Returns
        -------
        bool
            True if filter was applied.
        """
        if not matplotlib.get_backend().lower().startswith('qt'):
            return False

        try:
            from matplotlib.backends import qt_compat
            QtWidgets = qt_compat.QtWidgets

            # Build dialog
            dlg = QtWidgets.QDialog(self._ctrl.fig.canvas.manager.window)
            dlg.setWindowTitle("Filter Points")

            field = QtWidgets.QComboBox(dlg)
            field.addItems(["Frequency", "Velocity", "Wavelength"])
            field.setCurrentIndex(0)

            direction = QtWidgets.QComboBox(dlg)
            direction.addItems(["Above", "Below"])
            direction.setCurrentIndex(0)

            thresh = QtWidgets.QLineEdit(dlg)
            unit = QtWidgets.QLabel("Hz", dlg)

            def _on_field_change(txt: str):
                unit.setText(
                    {"Frequency": "Hz", "Velocity": "m/s", "Wavelength": "m"}.get(txt, "")
                )

            field.currentTextChanged.connect(_on_field_change)

            form = QtWidgets.QFormLayout(dlg)
            form.addRow("Field:", field)
            form.addRow("Delete:", direction)
            hl = QtWidgets.QHBoxLayout()
            hl.addWidget(thresh)
            hl.addWidget(unit)
            form.addRow("Threshold:", hl)

            try:
                buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            except AttributeError:
                std = QtWidgets.QDialogButtonBox.StandardButton
                buttons = std.Ok | std.Cancel

            box = QtWidgets.QDialogButtonBox(buttons, parent=dlg)
            form.addRow(box)
            box.accepted.connect(dlg.accept)
            box.rejected.connect(dlg.reject)

            if dlg.exec() != 1:
                return False

            tval = float(thresh.text())
            fkey = {"Frequency": "freq", "Velocity": "vel", "Wavelength": "wave"}[
                field.currentText()
            ]
            delete_above = direction.currentText() == "Above"

            # Push undo state
            try:
                push_undo(self._ctrl)
            except Exception:
                try:
                    self._ctrl._save_state()
                except Exception:
                    pass

            # Apply filter
            for i in range(len(self._ctrl.velocity_arrays)):
                if not self._ctrl.lines_freq[i].get_visible():
                    continue

                v = np.asarray(self._ctrl.velocity_arrays[i])
                f = np.asarray(self._ctrl.frequency_arrays[i])
                w = np.asarray(self._ctrl.wavelength_arrays[i])

                if fkey == 'freq':
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, fmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, fmin=tval)
                elif fkey == 'vel':
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, vmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, vmin=tval)
                else:
                    if delete_above:
                        v, f, w = apply_filters(v, f, w, wmax=tval)
                    else:
                        v, f, w = apply_filters(v, f, w, wmin=tval)

                self._ctrl.velocity_arrays[i] = v
                self._ctrl.frequency_arrays[i] = f
                self._ctrl.wavelength_arrays[i] = w

            # Update lines and UI
            self._update_lines()
            try:
                self._ctrl._update_average_line()
                self._ctrl._update_legend()
                self._ctrl._apply_axis_limits()
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass

            return True
        except Exception as e:
            log.error(f"Filter failed: {e}")
            return False

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

    def _clear_selection_patches(self) -> None:
        """Clear all selection rectangle patches (axis-aligned and inclined)."""
        # Clear axis-aligned rectangle patches
        try:
            for r in list(getattr(self._ctrl, 'freq_patches', [])):
                try:
                    r.remove()
                except Exception:
                    pass
            self._ctrl.freq_patches.clear()
            self._ctrl.bounding_boxes_freq.clear()
        except Exception:
            pass

        try:
            for r in list(getattr(self._ctrl, 'wave_patches', [])):
                try:
                    r.remove()
                except Exception:
                    pass
            self._ctrl.wave_patches.clear()
            self._ctrl.bounding_boxes_wave.clear()
        except Exception:
            pass

        # Clear inclined rectangle patches
        try:
            for p in list(getattr(self._ctrl, 'inclined_patches_freq', [])):
                try:
                    p.remove()
                except Exception:
                    pass
            self._ctrl.inclined_patches_freq.clear()
            self._ctrl.inclined_boxes_freq.clear()
        except Exception:
            pass

        try:
            for p in list(getattr(self._ctrl, 'inclined_patches_wave', [])):
                try:
                    p.remove()
                except Exception:
                    pass
            self._ctrl.inclined_patches_wave.clear()
            self._ctrl.inclined_boxes_wave.clear()
        except Exception:
            pass

    def _update_lines(self) -> None:
        """Update line artists from current arrays."""
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

    def _rebuild_and_restore(self, spectrum_state: dict) -> None:
        """Rebuild model and restore spectrum state."""
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

        # Refresh UI
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
