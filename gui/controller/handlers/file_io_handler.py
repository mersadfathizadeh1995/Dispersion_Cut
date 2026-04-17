"""File I/O handler for save/load operations.

Handles all file-based operations including session save/load,
dispersion curve export, and passive stats export.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import numpy as np
import matplotlib

from dc_cut.core.processing.averages import compute_avg_by_frequency
from dc_cut.core.io.state import save_session, load_session
from dc_cut.core.io.export import write_geopsy_txt, write_passive_stats_csv
from dc_cut.services import log

if TYPE_CHECKING:
    from dc_cut.gui.controller.base import BaseInteractiveRemoval


class FileIOHandler:
    """Handles file save/load operations."""

    def __init__(self, controller: "BaseInteractiveRemoval") -> None:
        """Initialize file I/O handler.

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

    def save_session(self, event=None) -> bool:
        """Save current session state to file.

        Returns
        -------
        bool
            True if saved successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self._ctrl.fig.canvas.manager.window,
                "Save Interactive Session",
                "",
                "Session State (*.pkl);;All Files (*.*)",
            )
            if not path:
                return False

            state_dict = self._ctrl.get_current_state()
            save_session(state_dict, path)

            QtWidgets.QMessageBox.information(
                self._ctrl.fig.canvas.manager.window,
                "Save State",
                f"Saved → {path}",
            )
            return True
        except Exception as e:
            log.error(f"Failed to save session: {e}")
            return False

    def save_dispersion_txt(self, event=None) -> bool:
        """Export dispersion curve to Geopsy TXT format.

        Returns
        -------
        bool
            True if saved successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self._ctrl.fig.canvas.manager.window,
                "Save Dispersion Curve",
                "",
                "Text file (*.txt);;All Files (*.*)",
            )
            if not path:
                return False

            # Gather visible picks
            vis_freq, vis_vel = self._gather_visible_data()
            if not vis_freq:
                QtWidgets.QMessageBox.information(
                    self._ctrl.fig.canvas.manager.window,
                    "Save Dispersion Curve",
                    "No visible data – nothing to save.",
                )
                return False

            freq_arr = np.asarray(vis_freq, float)
            vel_arr = np.asarray(vis_vel, float)
            stats = self._build_export_curve(freq_arr, vel_arr)

            write_geopsy_txt(stats, path)
            
            # Store last saved file path for export wizard
            self._ctrl._last_saved_file = path
            
            QtWidgets.QMessageBox.information(
                self._ctrl.fig.canvas.manager.window,
                "Save Dispersion Curve",
                f"Saved → {path}",
            )
            return True
        except Exception as e:
            log.error(f"Failed to save dispersion TXT: {e}")
            if self._is_qt_backend():
                try:
                    QtWidgets = self._get_qt_widgets()
                    QtWidgets.QMessageBox.critical(
                        self._ctrl.fig.canvas.manager.window,
                        "Save Dispersion Curve",
                        f"Export failed:\n{e}",
                    )
                except Exception:
                    pass
            return False

    def save_passive_stats(self, event=None) -> bool:
        """Export passive stats (Meandisp-compatible CSV).

        Returns
        -------
        bool
            True if saved successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()

            vis_freq, vis_vel = self._gather_visible_data()
            if not vis_freq:
                QtWidgets.QMessageBox.information(
                    self._ctrl.fig.canvas.manager.window,
                    "Save Passive Stats",
                    "No visible data to export.",
                )
                return False

            freq_arr = np.asarray(vis_freq, float)
            vel_arr = np.asarray(vis_vel, float)

            # Compute binned stats
            bins = int(getattr(self._ctrl, 'bins_for_average', 50))
            stats = compute_avg_by_frequency(
                vel_arr,
                freq_arr,
                min_freq=float(
                    getattr(self._ctrl, 'min_freq', max(0.1, float(np.nanmin(freq_arr))))
                ),
                max_freq=float(getattr(self._ctrl, 'max_freq', float(np.nanmax(freq_arr)))),
                bins=bins,
                bias=float(getattr(self._ctrl, 'low_bias', 1.0)),
            )

            f = stats['FreqMean']
            v = stats['VelMean']
            s = stats['VelStd']
            m = np.isfinite(f) & np.isfinite(v)
            f, v, s = f[m], v[m], s[m]
            slow = np.where(v != 0, 1.0 / v, np.nan)
            dinv = np.where(v != 0, (s + v) / v, np.nan)
            nump = np.full_like(f, 0, dtype=int)

            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self._ctrl.fig.canvas.manager.window,
                "Save Passive Stats",
                "",
                "CSV (*.csv);;All Files (*.*)",
            )
            if not path:
                return False

            write_passive_stats_csv(f, slow, dinv, nump, path)
            QtWidgets.QMessageBox.information(
                self._ctrl.fig.canvas.manager.window,
                "Save Passive Stats",
                f"Saved → {path}",
            )
            return True
        except Exception as e:
            log.error(f"Failed to save passive stats: {e}")
            return False

    def load_spectrum_dialog(self, event=None) -> bool:
        """Open dialog to load spectrum NPZ file.

        Returns
        -------
        bool
            True if loaded successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self._ctrl.fig.canvas.manager.window,
                "Load Combined Spectrum",
                "",
                "NPZ files (*.npz);;All Files (*.*)",
            )
            if not path:
                return False

            # Use spectrum handler if available
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                results = self._ctrl.spectrum.load_combined_for_layers(path)
            else:
                results = self._ctrl.load_combined_spectrum_for_layers(path)

            if results:
                matched = sum(1 for v in results.values() if v)
                total = len(results)
                QtWidgets.QMessageBox.information(
                    self._ctrl.fig.canvas.manager.window,
                    "Load Spectrum",
                    f"Loaded spectrum for {matched}/{total} layers from:\n{path}",
                )
                return True
            else:
                QtWidgets.QMessageBox.warning(
                    self._ctrl.fig.canvas.manager.window,
                    "Load Spectrum",
                    f"No matching layers found in spectrum file:\n{path}",
                )
                return False
        except Exception as e:
            log.error(f"Failed to load spectrum: {e}")
            if self._is_qt_backend():
                try:
                    QtWidgets = self._get_qt_widgets()
                    QtWidgets.QMessageBox.critical(
                        self._ctrl.fig.canvas.manager.window,
                        "Load Spectrum Error",
                        f"Failed to load spectrum:\n{str(e)}",
                    )
                except Exception:
                    pass
            return False

    def prompt_load_spectrum(self, saved_path: str) -> bool:
        """Prompt user to load spectrum file from saved state.

        Parameters
        ----------
        saved_path : str
            Path to spectrum file from saved state.

        Returns
        -------
        bool
            True if loaded successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()
            import os

            file_exists = os.path.exists(saved_path)

            if file_exists:
                reply = QtWidgets.QMessageBox.question(
                    self._ctrl.fig.canvas.manager.window,
                    "Load Spectrum?",
                    f"This state had spectrum data loaded from:\n{saved_path}\n\n"
                    f"Would you like to load it now?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                        results = self._ctrl.spectrum.load_combined_for_layers(saved_path)
                    else:
                        results = self._ctrl.load_combined_spectrum_for_layers(saved_path)
                    if results:
                        matched = sum(1 for v in results.values() if v)
                        log.info(f"Loaded spectrum for {matched} layers from saved path")
                        return True
            else:
                reply = QtWidgets.QMessageBox.question(
                    self._ctrl.fig.canvas.manager.window,
                    "Spectrum File Not Found",
                    f"The spectrum file from the saved state was not found:\n{saved_path}\n\n"
                    f"Would you like to locate it?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )

                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    path, _ = QtWidgets.QFileDialog.getOpenFileName(
                        self._ctrl.fig.canvas.manager.window,
                        "Locate Spectrum File",
                        "",
                        "NPZ files (*.npz);;All Files (*.*)",
                    )
                    if path:
                        if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                            results = self._ctrl.spectrum.load_combined_for_layers(path)
                        else:
                            results = self._ctrl.load_combined_spectrum_for_layers(path)
                        if results:
                            matched = sum(1 for v in results.values() if v)
                            log.info(
                                f"Loaded spectrum for {matched} layers from user-selected path"
                            )
                            return True
            return False
        except Exception as e:
            log.error(f"Failed to prompt for spectrum: {e}")
            return False

    def _gather_visible_data(self):
        """Gather frequency and velocity data from visible layers."""
        vis_freq, vis_vel = [], []
        for idx in range(len(self._ctrl.velocity_arrays)):
            try:
                if self._ctrl.lines_freq[idx].get_visible():
                    vis_freq.extend(self._ctrl.frequency_arrays[idx])
                    vis_vel.extend(self._ctrl.velocity_arrays[idx])
            except Exception:
                continue
        return vis_freq, vis_vel

    def _build_export_curve(
        self, freq_arr: np.ndarray, vel_arr: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """Build export statistics for Geopsy TXT format."""
        bins = int(getattr(self._ctrl, 'export_bins', 50))

        stats = compute_avg_by_frequency(
            vel_arr,
            freq_arr,
            min_freq=float(
                getattr(self._ctrl, 'min_freq', max(0.1, float(np.nanmin(freq_arr))))
            ),
            max_freq=float(getattr(self._ctrl, 'max_freq', float(np.nanmax(freq_arr)))),
            bins=int(max(2, bins)),
            bias=float(getattr(self._ctrl, 'low_bias', 1.0)),
        )

        f = np.asarray(stats['FreqMean'], float)
        v = np.asarray(stats['VelMean'], float)
        s = np.asarray(stats['VelStd'], float)
        m = np.isfinite(f) & np.isfinite(v) & np.isfinite(s) & (v != 0)
        f, v, s = f[m], v[m], s[m]
        slow = np.where(v != 0, 1.0 / v, np.nan)
        dinv = np.where(v != 0, s / v, np.nan)
        nump = np.full_like(f, 0, dtype=int)

        return {
            'FreqMean': f,
            'SlowMean': slow,
            'DinverStd': dinv,
            'NumPoints': nump,
        }
