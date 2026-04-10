"""Add data/layer handler.

Handles adding data to existing layers or creating new layers from files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

import numpy as np
import matplotlib

from dc_cut.gui.controller.add_mode import start_add_to_offset, start_add_new_layer
from dc_cut.visualization.plot_helpers import set_line_xy
from dc_cut.core.models import LayersModel
from dc_cut.core.io.state import load_session
from dc_cut.core.io.csv_io import load_combined_csv
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.gui.controller.base import BaseInteractiveRemoval


class AddHandler:
    """Handles add data/layer operations."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize add handler.

        Parameters
        ----------
        controller : BaseInteractiveRemoval
            Parent controller instance.
        """
        self._ctrl = controller

    def _is_qt_backend(self) -> bool:
        """Check if running on Qt backend."""
        return matplotlib.get_backend().lower().startswith('qt')

    def _get_qt_widgets(self):
        """Get QtWidgets module."""
        from matplotlib.backends import qt_compat
        return qt_compat.QtWidgets

    def add_data(self, event=None) -> bool:
        """Open dialog to add data to existing layer.

        Returns
        -------
        bool
            True if add session started.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()

            # Choose target offset (exclude average entries)
            offsets_no_avg = (
                list(self._ctrl.offset_labels[:-2])
                if len(self._ctrl.offset_labels) >= 2
                else list(self._ctrl.offset_labels)
            )
            if not offsets_no_avg:
                return False

            sel, ok = QtWidgets.QInputDialog.getItem(
                self._ctrl.fig.canvas.manager.window,
                "Add Data – choose offset",
                "Target offset:",
                offsets_no_avg,
                0,
                False,
            )
            if not ok:
                return False

            idx = offsets_no_avg.index(sel)

            # Pick data file
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self._ctrl.fig.canvas.manager.window,
                "Select state (.pkl) or combined CSV",
                "",
                "State (*.pkl);;CSV (*.csv);;All Files (*.*)",
            )
            if not fname:
                return False

            # Load data from file
            v_new, f_new, w_new = self._load_data_from_file(fname)
            if v_new is None:
                QtWidgets.QMessageBox.critical(
                    self._ctrl.fig.canvas.manager.window,
                    "Add Data",
                    "Failed to read file",
                )
                return False

            # Start add session
            try:
                start_add_to_offset(self._ctrl, idx, v_new, f_new, w_new)
            except Exception:
                # Fallback to legacy preview
                self._legacy_start_add(idx, v_new, f_new, w_new)

            # Update limits
            try:
                self._ctrl._apply_axis_limits()
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass

            return True
        except Exception as e:
            log.error(f"Add data failed: {e}")
            return False

    def add_layer(self, event=None) -> bool:
        """Open dialog to add new layer.

        Returns
        -------
        bool
            True if add session started.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()

            # Layer name
            name, ok = QtWidgets.QInputDialog.getText(
                self._ctrl.fig.canvas.manager.window,
                "New Layer",
                "Layer name:",
            )
            if not ok or not str(name).strip():
                return False

            layer_name = str(name).strip()

            # Marker selection
            marker_options = ['o', 'x', '+', 's', '^', 'd']
            marker, okm = QtWidgets.QInputDialog.getItem(
                self._ctrl.fig.canvas.manager.window,
                "Marker",
                "Choose marker:",
                marker_options,
                0,
                False,
            )
            if not okm:
                return False

            marker = str(marker)

            # Color selection
            color = QtWidgets.QColorDialog.getColor(
                parent=self._ctrl.fig.canvas.manager.window
            )
            colour_hex = color.name() if color and color.isValid() else "#1f77b4"

            # Pick data file
            fname, _ = QtWidgets.QFileDialog.getOpenFileName(
                self._ctrl.fig.canvas.manager.window,
                "Select data for new layer",
                "",
                "State (*.pkl);;CSV (*.csv);;All Files (*.*)",
            )
            if not fname:
                return False

            # Load data
            v_new, f_new, w_new = self._load_data_from_file(fname)
            if v_new is None:
                QtWidgets.QMessageBox.critical(
                    self._ctrl.fig.canvas.manager.window,
                    "Add Layer",
                    "Failed to read file",
                )
                return False

            # Start add-layer session
            try:
                start_add_new_layer(
                    self._ctrl, layer_name, marker, colour_hex, v_new, f_new, w_new
                )
            except Exception:
                # Fallback to legacy preview
                self._legacy_start_add_layer(
                    layer_name, marker, colour_hex, v_new, f_new, w_new
                )

            # Update limits
            try:
                self._ctrl._apply_axis_limits()
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass

            return True
        except Exception as e:
            log.error(f"Add layer failed: {e}")
            return False

    def save_added_data(self, event=None) -> bool:
        """Commit current add session.

        Returns
        -------
        bool
            True if data was saved.
        """
        if not bool(getattr(self._ctrl, 'add_mode', False)):
            log.info("Nothing to save – no add session active.")
            return False

        if getattr(self._ctrl, '_add_v', None) is None or len(self._ctrl._add_v) == 0:
            if self._is_qt_backend():
                try:
                    QtWidgets = self._get_qt_widgets()
                    QtWidgets.QMessageBox.information(
                        self._ctrl.fig.canvas.manager.window,
                        "Save Data",
                        "No points in added layer – canceling.",
                    )
                except Exception:
                    pass
            return False

        # Snapshot undo state
        try:
            self._ctrl._save_state()
        except Exception:
            pass

        idx = self._ctrl._added_offset_idx
        is_new_layer = idx >= len(self._ctrl.velocity_arrays)

        try:
            if is_new_layer:
                self._commit_new_layer()
            else:
                self._commit_to_existing(idx)

            # UI refresh
            if self._ctrl.show_average or self._ctrl.show_average_wave:
                self._ctrl._update_average_line()
            self._ctrl._update_legend()

            # Notify layers UI
            cb = getattr(self._ctrl, 'on_layers_changed', None)
            if cb:
                cb()

            # Update limits
            self._ctrl._apply_axis_limits()
            self._ctrl.fig.canvas.draw_idle()
            self._ctrl._apply_axis_limits()

            return True
        except Exception as e:
            log.error(f"Save added data failed: {e}")
            return False
        finally:
            # Clear add-mode state
            self._ctrl.add_mode = False
            self._ctrl._add_v = None
            self._ctrl._add_f = None
            self._ctrl._add_w = None
            self._ctrl._add_line_freq = None
            self._ctrl._add_line_wave = None
            self._ctrl._added_offset_idx = None
            self._ctrl._new_layer_info = None
            self._enable_save_button(False)

            try:
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass

            # Notify layers UI
            try:
                cb = getattr(self._ctrl, 'on_layers_changed', None)
                if cb:
                    cb()
            except Exception:
                pass

    def enable_save_button(self, enable: bool) -> None:
        """Enable or disable the save added data button.

        Parameters
        ----------
        enable : bool
            True to enable, False to disable.
        """
        self._enable_save_button(enable)

    def _enable_save_button(self, enable: bool) -> None:
        """Internal method to toggle save button state."""
        try:
            self._ctrl.add_mode = bool(enable)
        except Exception:
            pass

        btn = getattr(self._ctrl, 'btn_save_added', None)
        if btn is None or not hasattr(btn, 'ax'):
            try:
                self._ctrl.fig.canvas.draw_idle()
            except Exception:
                pass
            return

        ax = btn.ax
        if enable:
            btn.color = "lightyellow"
            btn.hovercolor = "khaki"
            ax.set_alpha(1.0)
        else:
            btn.color = "#dddddd"
            btn.hovercolor = "#dddddd"
            ax.set_alpha(0.4)

        try:
            self._ctrl.fig.canvas.draw_idle()
        except Exception:
            pass

    def _load_data_from_file(
        self, fname: str
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """Load velocity, frequency, wavelength arrays from file."""
        import os

        try:
            ext = os.path.splitext(fname)[1].lower()

            if ext == ".pkl":
                try:
                    D = load_session(fname)
                except Exception:
                    import pickle

                    with open(fname, "rb") as f:
                        D = pickle.load(f)

                v_new = np.concatenate(D["velocity_arrays"])
                f_new = np.concatenate(D["frequency_arrays"])
                w_new = np.concatenate(D["wavelength_arrays"])

            elif ext == ".csv":
                v_list, f_list, w_list, _ = load_combined_csv(fname)
                v_new = np.concatenate(v_list)
                f_new = np.concatenate(f_list)
                w_new = np.concatenate(w_list)

            else:
                raise ValueError("Unsupported file; choose .pkl or .csv")

            return v_new, f_new, w_new
        except Exception as e:
            log.error(f"Failed to load file: {e}")
            return None, None, None

    def _legacy_start_add(
        self, idx: int, v_new: np.ndarray, f_new: np.ndarray, w_new: np.ndarray
    ) -> None:
        """Legacy fallback for starting add-to-offset session."""
        mkr, col = 'x', 'purple'
        lf = self._ctrl.ax_freq.semilogx(
            f_new, v_new, mkr, color=col, markersize=6, label="added"
        )[0]
        lw = self._ctrl.ax_wave.semilogx(
            w_new, v_new, mkr, color=col, markersize=6, label="added"
        )[0]

        self._ctrl._add_v = v_new
        self._ctrl._add_f = f_new
        self._ctrl._add_w = w_new
        self._ctrl._add_line_freq = lf
        self._ctrl._add_line_wave = lw
        self._ctrl._added_offset_idx = idx
        self._ctrl.add_mode = True
        self._enable_save_button(True)

    def _legacy_start_add_layer(
        self,
        layer_name: str,
        marker: str,
        colour_hex: str,
        v_new: np.ndarray,
        f_new: np.ndarray,
        w_new: np.ndarray,
    ) -> None:
        """Legacy fallback for starting add-new-layer session."""
        lf = self._ctrl.ax_freq.semilogx(
            f_new,
            v_new,
            marker=marker,
            linestyle='',
            markerfacecolor='none',
            markeredgecolor=colour_hex,
            markeredgewidth=1.5,
            markersize=6,
        )[0]
        lw = self._ctrl.ax_wave.semilogx(
            w_new,
            v_new,
            marker=marker,
            linestyle='',
            markerfacecolor='none',
            markeredgecolor=colour_hex,
            markeredgewidth=1.5,
            markersize=6,
            label=layer_name,
        )[0]

        self._ctrl._add_v = v_new
        self._ctrl._add_f = f_new
        self._ctrl._add_w = w_new
        self._ctrl._add_line_freq = lf
        self._ctrl._add_line_wave = lw
        self._ctrl._added_offset_idx = len(self._ctrl.velocity_arrays)
        self._ctrl._new_layer_info = (layer_name, marker, colour_hex)
        self._ctrl.add_mode = True
        self._enable_save_button(True)

    def _commit_new_layer(self) -> None:
        """Commit new layer from add session."""
        self._ctrl.velocity_arrays.append(self._ctrl._add_v)
        self._ctrl.frequency_arrays.append(self._ctrl._add_f)
        self._ctrl.wavelength_arrays.append(self._ctrl._add_w)

        self._ctrl.lines_freq.append(self._ctrl._add_line_freq)
        self._ctrl.lines_wave.append(self._ctrl._add_line_wave)

        layer_name, _, _ = self._ctrl._new_layer_info

        try:
            self._ctrl.lines_wave[-1].set_label(layer_name)
        except Exception:
            pass

        # Insert before average labels
        try:
            if len(self._ctrl.offset_labels) >= 2:
                self._ctrl.offset_labels.insert(-2, layer_name)
            else:
                self._ctrl.offset_labels.append(layer_name)
        except Exception:
            self._ctrl.offset_labels = list(self._ctrl.offset_labels) + [layer_name]

        # Update model
        try:
            if self._ctrl._layers_model is not None:
                self._ctrl._layers_model.add_new_layer(
                    layer_name, self._ctrl._add_v, self._ctrl._add_f, self._ctrl._add_w
                )
        except Exception:
            pass

        # Rebuild checkboxes for non-Qt backends
        if not self._is_qt_backend():
            try:
                self._ctrl._rebuild_checkboxes()
            except Exception:
                pass

    def _commit_to_existing(self, idx: int) -> None:
        """Merge add session into existing layer."""
        self._ctrl.velocity_arrays[idx] = np.concatenate(
            [self._ctrl.velocity_arrays[idx], self._ctrl._add_v]
        )
        self._ctrl.frequency_arrays[idx] = np.concatenate(
            [self._ctrl.frequency_arrays[idx], self._ctrl._add_f]
        )
        self._ctrl.wavelength_arrays[idx] = np.concatenate(
            [self._ctrl.wavelength_arrays[idx], self._ctrl._add_w]
        )

        # Update model
        try:
            if self._ctrl._layers_model is not None:
                self._ctrl._layers_model.merge_into(
                    idx, self._ctrl._add_v, self._ctrl._add_f, self._ctrl._add_w
                )
        except Exception:
            pass

        # Update lines
        set_line_xy(
            self._ctrl.lines_freq[idx],
            self._ctrl.frequency_arrays[idx],
            self._ctrl.velocity_arrays[idx],
        )
        set_line_xy(
            self._ctrl.lines_wave[idx],
            self._ctrl.wavelength_arrays[idx],
            self._ctrl.velocity_arrays[idx],
        )

        # Remove temp lines
        try:
            self._ctrl._add_line_freq.remove()
            self._ctrl._add_line_wave.remove()
        except Exception:
            pass
