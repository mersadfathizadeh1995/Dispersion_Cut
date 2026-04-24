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
        """Save current session state, silently overwriting the loaded file.

        When the controller has a ``_loaded_state_path`` pointing at an
        existing ``.pkl``, this writes to that path without prompting.
        Otherwise it falls through to :meth:`save_session_as` so the
        first save of a new session still asks where to put the file.
        This matches the standard "File ▸ Save" pattern — silent
        overwrite of the currently loaded file, with a separate "Save
        As..." action for explicit destinations.

        Returns
        -------
        bool
            True if saved successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            import os

            loaded = getattr(self._ctrl, "_loaded_state_path", "") or ""
            if not loaded or not os.path.isfile(loaded):
                return self.save_session_as(event)

            QtWidgets = self._get_qt_widgets()
            state_dict = self._ctrl.get_current_state()
            save_session(state_dict, loaded)
            try:
                self._ctrl._loaded_state_path = os.path.abspath(loaded)
                self._ctrl._nf_dirty = False
            except Exception:
                pass

            QtWidgets.QMessageBox.information(
                self._ctrl.fig.canvas.manager.window,
                "Save State",
                f"Saved → {loaded}",
            )
            return True
        except Exception as e:
            log.error(f"Failed to save session: {e}")
            return False

    def save_session_as(self, event=None) -> bool:
        """Save current session state to a user-chosen path (always prompts).

        Also updates ``_loaded_state_path`` so a subsequent "Save State"
        silently overwrites the newly chosen file.

        Returns
        -------
        bool
            True if saved successfully.
        """
        if not self._is_qt_backend():
            return False

        try:
            QtWidgets = self._get_qt_widgets()
            loaded = getattr(self._ctrl, "_loaded_state_path", "") or ""
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self._ctrl.fig.canvas.manager.window,
                "Save State As",
                loaded or "",
                "Session State (*.pkl);;All Files (*.*)",
            )
            if not path:
                return False

            state_dict = self._ctrl.get_current_state()
            save_session(state_dict, path)
            try:
                import os
                self._ctrl._loaded_state_path = os.path.abspath(path)
                self._ctrl._nf_dirty = False
            except Exception:
                pass

            QtWidgets.QMessageBox.information(
                self._ctrl.fig.canvas.manager.window,
                "Save State As",
                f"Saved → {path}",
            )
            return True
        except Exception as e:
            log.error(f"Failed to save session as: {e}")
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
        """Open dialog to load a combined or single-offset spectrum NPZ file.

        The file is first tried with the tolerant core readers. If the
        schema is not recognised, the user is offered a 'Map NPZ…'
        recovery action that opens :class:`MapNpzDialog` and retries
        the load with the manually-assigned keys.

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
                "Load Spectrum (single or combined)",
                "",
                "NPZ files (*.npz);;All Files (*.*)",
            )
            if not path:
                return False

            return self._load_spectrum_with_fallback(path)
        except Exception as e:
            log.error(f"Failed to load spectrum: {e}")
            self._show_spectrum_error(str(e))
            return False

    def _load_spectrum_with_fallback(self, path: str) -> bool:
        """Try to load ``path`` as a combined spectrum, with mapper fallback."""
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window

        try:
            from dc_cut.core.io.spectrum import detect_npz_format

            fmt = detect_npz_format(path)
        except Exception as exc:
            log.warning(f"Spectrum format detection failed for {path}: {exc}")
            fmt = "unknown"

        if fmt == "combined":
            return self._apply_combined_to_layers(path, show_status=True)
        if fmt == "single":
            return self._apply_single_to_layer_zero(path, show_status=True)

        # Unknown layout → try combined anyway (it works for every
        # legacy file), and if that fails offer the mapper.
        try:
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                results = self._ctrl.spectrum.load_combined_for_layers(path)
            else:
                results = self._ctrl.load_combined_spectrum_for_layers(path)
        except Exception as exc:
            log.warning(f"Combined spectrum load failed: {exc}")
            results = None

        if results:
            matched = sum(1 for v in results.values() if v)
            total = len(results)
            QtWidgets.QMessageBox.information(
                window,
                "Load Spectrum",
                f"Loaded spectrum for {matched}/{total} layers from:\n{path}",
            )
            return True

        # Offer mapper as recovery
        return self._prompt_map_and_retry(path)

    def _apply_combined_to_layers(self, path: str, show_status: bool) -> bool:
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window
        try:
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                results = self._ctrl.spectrum.load_combined_for_layers(path)
            else:
                results = self._ctrl.load_combined_spectrum_for_layers(path)
        except Exception as exc:
            log.error(f"Combined load raised: {exc}")
            return self._prompt_map_and_retry(path)

        if not results:
            if show_status:
                reply = QtWidgets.QMessageBox.warning(
                    window,
                    "Load Spectrum",
                    f"No matching layers found in spectrum file:\n{path}\n\n"
                    "Open 'Map NPZ…' to configure how this file should be read?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes,
                )
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    return self._prompt_map_and_retry(path)
            return False

        if show_status:
            matched = sum(1 for v in results.values() if v)
            total = len(results)
            QtWidgets.QMessageBox.information(
                window,
                "Load Spectrum",
                f"Loaded spectrum for {matched}/{total} layers from:\n{path}",
            )
        return True

    def _apply_single_to_layer_zero(self, path: str, show_status: bool) -> bool:
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window
        try:
            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                ok = self._ctrl.spectrum.load_for_layer(0, path)
            elif hasattr(self._ctrl, 'load_spectrum_for_layer'):
                ok = self._ctrl.load_spectrum_for_layer(0, path)
            else:
                ok = False
        except Exception as exc:
            log.error(f"Single-offset load raised: {exc}")
            return self._prompt_map_and_retry(path)

        if not ok:
            return self._prompt_map_and_retry(path)

        if show_status:
            QtWidgets.QMessageBox.information(
                window,
                "Load Spectrum",
                f"Loaded single-offset spectrum onto the first layer:\n{path}",
            )
        return True

    def _prompt_map_and_retry(self, path: str) -> bool:
        """Offer the NPZ mapper and re-apply the result to the current layers."""
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window
        try:
            from dc_cut.gui.dialogs.map_npz import (
                MapNpzDialog,
                read_npz_with_spec,
            )
        except Exception as exc:
            log.error(f"Unable to import MapNpzDialog: {exc}")
            self._show_spectrum_error(
                f"The spectrum could not be loaded automatically and the "
                f"fallback 'Map NPZ…' dialog is unavailable: {exc}"
            )
            return False

        dlg = MapNpzDialog(path, parent=window)
        try:
            accepted = dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted
        except AttributeError:
            accepted = dlg.exec_() == QtWidgets.QDialog.Accepted
        if not accepted:
            return False

        spec = dlg.result_spec()
        if spec is None:
            return False

        try:
            records = read_npz_with_spec(path, spec)
        except Exception as exc:
            self._show_spectrum_error(f"Mapping failed:\n{exc}")
            return False

        if not records:
            self._show_spectrum_error("The mapping produced no spectra.")
            return False

        # Apply the records: single → first layer; combined → match by offset.
        if spec.layout == "single":
            return self._apply_records_single(records[0])
        return self._apply_records_combined(records)

    def _apply_records_single(self, record) -> bool:
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window
        data = record.to_dict()
        try:
            model = getattr(self._ctrl, '_layers_model', None)
            if model is None or not model.layers:
                self._show_spectrum_error("No layers are available to attach the spectrum to.")
                return False
            layer = model.layers[0]
            layer.spectrum_data = data
            # Preserve defaults from the real handler when it is around.
            try:
                from dc_cut.services.prefs import get_pref
                layer.spectrum_alpha = get_pref('default_spectrum_alpha', 0.5)
                layer.spectrum_visible = get_pref('show_spectra', True)
            except Exception:
                layer.spectrum_alpha = 0.5
                layer.spectrum_visible = True

            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                self._ctrl.spectrum.render_backgrounds()
            QtWidgets.QMessageBox.information(
                window,
                "Load Spectrum",
                f"Spectrum mapped and attached to layer 0 ({layer.label}).",
            )
            return True
        except Exception as exc:
            log.error(f"Failed to attach mapped record: {exc}")
            self._show_spectrum_error(f"Failed to attach the mapped spectrum:\n{exc}")
            return False

    def _apply_records_combined(self, records) -> bool:
        QtWidgets = self._get_qt_widgets()
        window = self._ctrl.fig.canvas.manager.window
        try:
            model = getattr(self._ctrl, '_layers_model', None)
            if model is None or not model.layers:
                self._show_spectrum_error("No layers are available to attach the spectrum to.")
                return False

            from dc_cut.core.io.spectrum import match_csv_labels_to_spectrum
            spectra_by_offset = {r.offset: r.to_dict() for r in records if r.offset}
            csv_labels = [layer.label for layer in model.layers]
            matches = match_csv_labels_to_spectrum(csv_labels, spectra_by_offset)
            if not matches:
                self._show_spectrum_error(
                    "The mapping produced offsets that do not match any "
                    "current layer label."
                )
                return False

            try:
                from dc_cut.services.prefs import get_pref
                default_alpha = get_pref('default_spectrum_alpha', 0.5)
                show_spectra = get_pref('show_spectra', True)
            except Exception:
                default_alpha = 0.5
                show_spectra = True

            for idx, key in matches.items():
                layer = model.layers[idx]
                layer.spectrum_data = spectra_by_offset[key]
                layer.spectrum_alpha = default_alpha
                layer.spectrum_visible = show_spectra

            if hasattr(self._ctrl, 'spectrum') and self._ctrl.spectrum is not None:
                self._ctrl.spectrum.render_backgrounds()
            QtWidgets.QMessageBox.information(
                window,
                "Load Spectrum",
                f"Mapped {len(matches)}/{len(model.layers)} layers.",
            )
            return True
        except Exception as exc:
            log.error(f"Failed to attach mapped combined spectrum: {exc}")
            self._show_spectrum_error(f"Failed to attach the mapped spectra:\n{exc}")
            return False

    def _show_spectrum_error(self, message: str) -> None:
        if not self._is_qt_backend():
            return
        try:
            QtWidgets = self._get_qt_widgets()
            QtWidgets.QMessageBox.critical(
                self._ctrl.fig.canvas.manager.window,
                "Load Spectrum Error",
                message,
            )
        except Exception:
            pass

    def open_spectrum_npz_dialog(self, event=None) -> bool:
        """Open an NPZ via the mapper, bypassing auto-detection.

        Convenience entry point for 'File ▸ Open Spectrum NPZ…' — users
        can use this when auto-detection would pick the wrong keys, for
        example when a third-party file exposes ``P`` / ``F`` / ``V``
        instead of ``power`` / ``frequencies`` / ``velocities``.
        """
        if not self._is_qt_backend():
            return False
        try:
            QtWidgets = self._get_qt_widgets()
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self._ctrl.fig.canvas.manager.window,
                "Open Spectrum NPZ",
                "",
                "NPZ files (*.npz);;All Files (*.*)",
            )
            if not path:
                return False
            return self._prompt_map_and_retry(path)
        except Exception as exc:
            log.error(f"Failed to open spectrum NPZ: {exc}")
            self._show_spectrum_error(str(exc))
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
