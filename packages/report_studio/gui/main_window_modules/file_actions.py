"""File actions mixin — open/save/export."""

from __future__ import annotations


class FileActionsMixin:
    """Handles file open, save, and export operations."""

    _project_path: str = ""
    _dirty: bool = False

    def _mark_dirty(self):
        """Mark the project as having unsaved changes."""
        self._dirty = True
        title = self.windowTitle()
        if not title.endswith(" •"):
            self.setWindowTitle(title + " •")

    def _mark_clean(self):
        """Clear the dirty flag."""
        self._dirty = False
        title = self.windowTitle()
        if title.endswith(" •"):
            self.setWindowTitle(title[:-2])

    def _on_open_data(self):
        """Open data files (PKL + NPZ) via AddDataDialog into the first subplot."""
        sheet = self._current_sheet()
        if not sheet:
            return
        first_key = sheet.subplot_keys_ordered()[0] if sheet.subplots else "main"
        self._on_add_data_to_subplot(first_key)

    def _load_from_files(self, pkl_path: str, npz_path: str = "",
                         show_dialog: bool = True):
        """Load curves from PKL and optionally spectra from NPZ."""
        from ...io.pkl_reader import read_pkl
        from ...io.spectrum_reader import read_spectrum_npz

        if not pkl_path:
            return

        # Store paths on current sheet + QSettings
        sheet = self._current_sheet()
        if sheet:
            sheet.pkl_path = pkl_path
            sheet.npz_path = npz_path
        self._pkl_path = pkl_path
        self._npz_path = npz_path
        from ..panels.project_start_dialog import save_data_paths
        save_data_paths(pkl_path, npz_path)

        curves = read_pkl(pkl_path)
        spectra = []
        if npz_path:
            try:
                spectra = read_spectrum_npz(npz_path)
            except Exception:
                pass

        if show_dialog:
            self._populate_sheet(curves, spectra)
        else:
            self._populate_sheet_direct(curves, spectra)

    def _load_from_controller(self, controller):
        """Extract data from a DC Cut controller."""
        from ...core.models import OffsetCurve, SpectrumData, CURVE_COLORS
        import numpy as np

        curves = []
        n = len(controller.velocity_arrays)
        labels = getattr(controller, "offset_labels", [])
        if hasattr(controller, "_layers_model"):
            layers = controller._layers_model.layers
        else:
            layers = []

        for i in range(n):
            freq = np.asarray(controller.frequency_arrays[i], dtype=float)
            vel = np.asarray(controller.velocity_arrays[i], dtype=float)
            wl = np.asarray(controller.wavelength_arrays[i], dtype=float)
            label = str(labels[i]) if i < len(labels) else f"Offset {i+1}"

            curve = OffsetCurve(
                name=label,
                frequency=freq,
                velocity=vel,
                wavelength=wl,
                color=CURVE_COLORS[i % len(CURVE_COLORS)],
            )
            curves.append(curve)

        # Extract spectrum data from layers model
        spectra = []
        for i, layer in enumerate(layers):
            if hasattr(layer, "spectrum_data") and layer.spectrum_data:
                sd = layer.spectrum_data
                if "power" in sd and "frequencies" in sd and "velocities" in sd:
                    spec = SpectrumData(
                        offset_name=str(labels[i]) if i < len(labels) else "",
                        frequencies=np.asarray(sd["frequencies"], dtype=float),
                        velocities=np.asarray(sd["velocities"], dtype=float),
                        power=np.asarray(sd["power"], dtype=float),
                        method=str(sd.get("method", "unknown")),
                    )
                    spectra.append(spec)

        self._populate_sheet_direct(curves, spectra)

    def _on_export_image(self):
        """Export the current canvas via export dialog."""
        from ..panels.export_dialog import ExportDialog
        from ...qt_compat import DialogAccepted

        dlg = ExportDialog(parent=self)
        if dlg.exec() != DialogAccepted:
            return

        canvas = self.sheet_tabs.current_canvas()
        if canvas:
            # Resize figure to requested dimensions
            fig = canvas.figure
            fig.set_size_inches(dlg.width_inches, dlg.height_inches)
            canvas.export_image(dlg.path, dpi=dlg.dpi)
            self.statusBar().showMessage(f"Exported to {dlg.path}")

    # ── Config Preset Save / Load ─────────────────────────────────────

    def _on_save_config_as(self):
        """Export current sheet's look-and-feel settings as a preset file."""
        from ...qt_compat import QtWidgets
        sheet = self._current_sheet()
        if not sheet:
            QtWidgets.QMessageBox.information(
                self, "Save Config", "No active sheet to read settings from.",
            )
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Config Preset", "",
            "Config preset (*.json);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            from ...io.config_preset import save_config
            save_config(path, sheet)
            self.statusBar().showMessage(f"Config preset saved: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Save Error", f"Could not save preset:\n{e}",
            )

    def _on_load_config(self):
        """Load a preset file and apply its settings to the current sheet."""
        from ...qt_compat import QtWidgets
        sheet = self._current_sheet()
        if not sheet:
            QtWidgets.QMessageBox.information(
                self, "Load Config", "Open a sheet before applying a preset.",
            )
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Config Preset", "",
            "Config preset (*.json);;All files (*)",
        )
        if not path:
            return
        try:
            from ...io.config_preset import apply_config
            summary = apply_config(path, sheet)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Load Error", f"Could not apply preset:\n{e}",
            )
            return

        # Refresh UI + canvas with new settings
        if hasattr(self, "data_tree"):
            self.data_tree.populate(sheet)
        if hasattr(self, "right_panel"):
            self.right_panel.populate_global(sheet)
            pkeys, pnames = sheet.populated_subplot_info()
            self.right_panel.update_subplot_list(pkeys, pnames)
        self._mark_dirty()
        self._render_current()
        sec_str = ", ".join(summary.get("sections") or []) or "none"
        applied = summary.get("subplots_applied") or []
        skipped = summary.get("subplots_skipped") or []
        msg = f"Preset applied — sections: {sec_str}"
        if applied:
            msg += f"; subplots: {', '.join(applied)}"
        if skipped:
            msg += f"; skipped: {', '.join(skipped)}"
        self.statusBar().showMessage(msg)

    # ── Sheet Save / Load ─────────────────────────────────────────────

    def _ensure_project_path(self) -> str:
        """Ensure we have a project directory. Prompt if needed."""
        if self._project_path:
            return self._project_path
        from ...qt_compat import QtWidgets
        base = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose Project Directory",
        )
        if not base:
            return ""
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Project Name", "Enter project name:",
        )
        if not ok or not name.strip():
            return ""
        import os
        project_dir = os.path.join(base, name.strip())
        os.makedirs(os.path.join(project_dir, "sheets"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "session"), exist_ok=True)

        # Create minimal project.json
        from ...io.project_v4 import create_project
        pkl = getattr(self, "_pkl_path", "")
        npz = getattr(self, "_npz_path", "")
        create_project(project_dir, name.strip(), pkl, npz)

        self._project_path = project_dir

        from ..panels.project_start_dialog import add_recent_project
        add_recent_project(project_dir)
        if hasattr(self, "_refresh_recent_menu"):
            self._refresh_recent_menu()
        return project_dir

    def _on_save_sheet(self):
        """Save current sheet (reuse existing name or prompt)."""
        sheet = self._current_sheet()
        if not sheet:
            return
        project_dir = self._ensure_project_path()
        if not project_dir:
            return
        self._save_sheet_to_project(project_dir, sheet, sheet.name)

    def _on_save_sheet_as(self):
        """Save current sheet with a new name."""
        from ...qt_compat import QtWidgets
        sheet = self._current_sheet()
        if not sheet:
            return
        project_dir = self._ensure_project_path()
        if not project_dir:
            return
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Save Sheet As", "Sheet name:", text=sheet.name,
        )
        if not ok or not name.strip():
            return
        self._save_sheet_to_project(project_dir, sheet, name.strip())

    def _save_sheet_to_project(self, project_dir: str, sheet, name: str):
        """Save a sheet to the project directory."""
        from ...qt_compat import QtWidgets
        try:
            from ...io.project_v4 import save_sheet_manifest
            save_sheet_manifest(project_dir, sheet, sheet_name=name)
            self._mark_clean()
            self.statusBar().showMessage(f"Sheet saved: {name}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Save Error", f"Failed to save sheet:\n{e}"
            )

    def _on_load_sheet(self):
        """Load a sheet from the project's sheets/ directory."""
        from ...qt_compat import QtWidgets

        project_dir = self._project_path
        if not project_dir:
            # Let user pick a project folder
            d = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Select Project Directory",
            )
            if not d:
                return
            import os
            if not os.path.isfile(os.path.join(d, "project.json")):
                QtWidgets.QMessageBox.warning(
                    self, "Not a Project",
                    f"No project.json found in:\n{d}",
                )
                return
            project_dir = d
            self._project_path = d

        from ...io.project_v4 import list_sheets
        sheets = list_sheets(project_dir)
        if not sheets:
            QtWidgets.QMessageBox.information(
                self, "Load Sheet", "No saved sheets found in this project.",
            )
            return

        names = [n for n, _ in sheets]
        choice, ok = QtWidgets.QInputDialog.getItem(
            self, "Load Sheet", "Select sheet:", names, editable=False,
        )
        if not ok:
            return

        for n, folder in sheets:
            if n == choice:
                self._load_sheet_from_folder(folder)
                break

    def _load_sheet_from_folder(self, sheet_folder: str):
        """Load a sheet from its manifest folder, re-reading data."""
        from ...qt_compat import QtWidgets
        from ...io.project_v4 import (
            load_sheet_manifest, reload_and_apply, compute_fingerprint,
        )
        from ...io.pkl_reader import read_pkl
        from ...io.spectrum_reader import read_spectrum_npz

        try:
            sheet, curve_settings, data_sources, included_names = (
                load_sheet_manifest(sheet_folder)
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Load Error", f"Failed to read sheet:\n{e}",
            )
            return

        pkl_path = data_sources.get("pkl_path", "")
        npz_path = data_sources.get("npz_path", "")
        nf_sidecar_path = data_sources.get("nf_sidecar_path", "")
        saved_fp = data_sources.get("fingerprint", "")

        has_curves_in_manifest = bool(curve_settings)

        # Fallback: if paths are empty but the sheet had curves, try
        # the window-level paths, QSettings, or prompt the user.
        if not pkl_path and has_curves_in_manifest:
            pkl_path = getattr(self, "_pkl_path", "")
            npz_path = getattr(self, "_npz_path", "") or npz_path
        if not pkl_path and has_curves_in_manifest:
            from ..panels.project_start_dialog import load_data_paths
            pkl_path, npz_path = load_data_paths()
        if not pkl_path and has_curves_in_manifest:
            # Last resort: ask user to locate the PKL file
            pkl_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Locate Data File (PKL)",
                "", "Pickle files (*.pkl);;All files (*)",
            )
            if pkl_path:
                npz_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    self, "Locate Spectrum File (NPZ, optional)",
                    "", "NumPy files (*.npz);;All files (*)",
                )

        curves, spectra = [], []
        if pkl_path:
            import os
            if not os.path.isfile(pkl_path):
                QtWidgets.QMessageBox.warning(
                    self, "Data Warning",
                    f"PKL file not found:\n{pkl_path}",
                )
            else:
                try:
                    curves = read_pkl(pkl_path)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self, "Data Warning",
                        f"Could not reload data file:\n{pkl_path}\n{e}",
                    )
        if npz_path:
            import os
            if os.path.isfile(npz_path):
                try:
                    spectra = read_spectrum_npz(npz_path)
                except Exception:
                    pass

        # Validate fingerprint
        if saved_fp and curves:
            current_fp = compute_fingerprint(curves)
            if current_fp != saved_fp:
                QtWidgets.QMessageBox.information(
                    self, "Data Changed",
                    "Source data files appear to have changed since "
                    "the sheet was saved. Settings will be applied "
                    "but results may differ.",
                )

        # Apply data to sheet skeleton
        if curves:
            # Fall back to the saved curve_settings keys for older sheets
            # that did not record `included_curve_names` explicitly.
            effective_included = (
                included_names
                if included_names is not None
                else list(curve_settings.keys())
            )
            reload_and_apply(
                sheet, curve_settings, curves, spectra,
                included_names=effective_included,
            )

        # Store paths on sheet (and globally for future saves)
        sheet.pkl_path = pkl_path or ""
        sheet.npz_path = npz_path or ""
        sheet.nf_sidecar_path = nf_sidecar_path or sheet.nf_sidecar_path
        if pkl_path:
            self._pkl_path = pkl_path
            self._npz_path = npz_path or ""
            from ..panels.project_start_dialog import save_data_paths
            save_data_paths(pkl_path, npz_path or "")

        # Add as new tab
        from ..canvas.plot_canvas import PlotCanvas
        idx = self._add_sheet_with_state(sheet)
        self.sheet_tabs.setCurrentIndex(idx)
        self.data_tree.populate(sheet)
        if hasattr(self, "right_panel"):
            self.right_panel.populate_global(sheet)
            pkeys, pnames = sheet.populated_subplot_info()
            self.right_panel.update_subplot_list(pkeys, pnames)
        self._render_current()
        self.statusBar().showMessage(f"Sheet loaded: {sheet.name}")

    # ── Legacy project load (kept for backward compat) ────────────────

    def _on_load_project(self):
        """Load a project — browse for a project directory."""
        from ...qt_compat import QtWidgets
        from ..panels.project_start_dialog import load_data_paths

        # Start from last-used base directory
        last_pkl, _ = load_data_paths()
        start_dir = ""
        if last_pkl:
            import os
            start_dir = os.path.dirname(os.path.dirname(last_pkl))

        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Open Project Directory", start_dir,
        )
        if not path:
            return

        import os
        pj_path = os.path.join(path, "project.json")
        if not os.path.isfile(pj_path):
            QtWidgets.QMessageBox.warning(
                self, "Not a Project",
                f"No project.json found in:\n{path}\n\n"
                "Please select a directory containing a Report Studio project.",
            )
            return

        import json
        try:
            with open(pj_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            version = data.get("version", 0)
        except Exception:
            version = 0

        self._project_path = path
        if version >= 4 and "data_sources" in data:
            self._load_project_v4(path, data)
        else:
            self._load_project_legacy(pj_path)

        # Add to recent projects and refresh menu
        from ..panels.project_start_dialog import add_recent_project
        add_recent_project(path)
        if hasattr(self, "_refresh_recent_menu"):
            self._refresh_recent_menu()

    def _load_project_v4(self, project_dir: str, manifest: dict):
        """Load a v4 directory-based project."""
        from ...qt_compat import QtWidgets
        from ...io.project_v4 import (
            load_project, reload_and_apply, compute_fingerprint,
        )
        from ...io.pkl_reader import read_pkl
        from ...io.spectrum_reader import read_spectrum_npz

        try:
            _, sheet_skeletons = load_project(project_dir)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Load Error", f"Failed to load project:\n{e}"
            )
            return

        # Reload data from source files
        ds = manifest.get("data_sources", {})
        pkl_path = ds.get("pkl_path", "")
        npz_path = ds.get("npz_path", "")
        saved_fp = ds.get("fingerprint", "")

        curves, spectra = [], []
        if pkl_path:
            try:
                curves = read_pkl(pkl_path)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Data Warning",
                    f"Could not reload PKL file:\n{pkl_path}\n{e}"
                )
        if npz_path:
            try:
                spectra = read_spectrum_npz(npz_path)
            except Exception:
                pass

        # Validate fingerprint
        if saved_fp and curves:
            current_fp = compute_fingerprint(curves)
            if current_fp != saved_fp:
                QtWidgets.QMessageBox.information(
                    self, "Data Changed",
                    "Source data files appear to have changed since "
                    "the project was saved. Settings will be applied "
                    "but results may differ."
                )

        # Store paths for future saves
        self._pkl_path = pkl_path
        self._npz_path = npz_path

        # Replace current sheets
        self._sheets.clear()
        while self.sheet_tabs.count() > 0:
            w = self.sheet_tabs.widget(0)
            self.sheet_tabs.removeTab(0)
            if w:
                w.deleteLater()

        from ..canvas.plot_canvas import PlotCanvas
        for entry in sheet_skeletons:
            # Tolerate both the new 3-tuple and any leftover 2-tuple shape
            if len(entry) == 3:
                sheet, curve_settings, included_names = entry
            else:
                sheet, curve_settings = entry  # type: ignore[misc]
                included_names = None
            effective_included = (
                included_names
                if included_names is not None
                else list(curve_settings.keys())
            )
            reload_and_apply(
                sheet, curve_settings, curves, spectra,
                included_names=effective_included,
            )
            sheet.pkl_path = pkl_path
            sheet.npz_path = npz_path
            self._sheets.append(sheet)
            canvas = PlotCanvas()
            canvas.curve_clicked.connect(self._on_curve_selected)
            canvas.subplot_clicked.connect(self._on_subplot_clicked)
            self.sheet_tabs.add_tab(canvas, sheet.name)

        if self._sheets:
            self.sheet_tabs.setCurrentIndex(0)
            self.data_tree.populate(self._sheets[0])
            if hasattr(self, "right_panel"):
                self.right_panel.populate_global(self._sheets[0])
                pkeys, pnames = self._sheets[0].populated_subplot_info()
                self.right_panel.update_subplot_list(pkeys, pnames)
            self._render_current()

        self.statusBar().showMessage(
            f"Loaded v4 project with {len(sheet_skeletons)} sheets"
        )
        self._project_path = project_dir
        self._mark_clean()

    def _load_project_legacy(self, path: str):
        """Load a legacy v3 single-file project."""
        from ...qt_compat import QtWidgets
        from ...io.project import load_project

        try:
            sheets = load_project(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Load Error", f"Failed to load project:\n{e}"
            )
            return

        self._sheets.clear()
        while self.sheet_tabs.count() > 0:
            w = self.sheet_tabs.widget(0)
            self.sheet_tabs.removeTab(0)
            if w:
                w.deleteLater()

        from ..canvas.plot_canvas import PlotCanvas
        for sheet in sheets:
            self._sheets.append(sheet)
            canvas = PlotCanvas()
            canvas.curve_clicked.connect(self._on_curve_selected)
            canvas.subplot_clicked.connect(self._on_subplot_clicked)
            self.sheet_tabs.add_tab(canvas, sheet.name)

        if self._sheets:
            self.sheet_tabs.setCurrentIndex(0)
            self.data_tree.populate(self._sheets[0])
            if hasattr(self, "right_panel"):
                self.right_panel.populate_global(self._sheets[0])
                pkeys, pnames = self._sheets[0].populated_subplot_info()
                self.right_panel.update_subplot_list(pkeys, pnames)
            self._render_current()

        self.statusBar().showMessage(
            f"Loaded legacy project with {len(sheets)} sheets"
        )
        self._project_path = path
        self._mark_clean()

    # ── Export panel handlers ─────────────────────────────────────────

    def _on_export_figure(self, opts: dict):
        """Export full figure from export panel."""
        sheet = self._current_sheet()
        canvas = self.sheet_tabs.current_canvas()
        if not sheet or not canvas:
            return

        from ...rendering.renderer import render_sheet
        from ...rendering.style import StyleConfig

        style = StyleConfig.from_sheet(sheet)
        import matplotlib.pyplot as mpl_plt
        fig = mpl_plt.figure()
        fig.set_size_inches(opts.get("width", 10), opts.get("height", 7))
        render_sheet(fig, sheet, style, quality="high")
        fig.savefig(opts["path"], dpi=opts.get("dpi", 300),
                    bbox_inches="tight")
        mpl_plt.close(fig)
        self.statusBar().showMessage(f"Exported figure to {opts['path']}")

    def _on_export_subplots(self, opts: dict):
        """Export individual subplots from export panel."""
        import os
        sheet = self._current_sheet()
        if not sheet:
            return

        from ...rendering.renderer import render_sheet
        from ...rendering.style import StyleConfig
        import matplotlib.pyplot as plt

        style = StyleConfig.from_sheet(sheet)

        dpi = opts.get("dpi", 300)
        fmt = opts.get("format", "png")
        keys = opts.get("keys", [])
        out_dir = opts["path"]

        for key in keys:
            if key not in sheet.subplots:
                continue
            # Render single-subplot sheet
            from ...core.models import SheetState
            single = SheetState(name=key, grid_rows=1, grid_cols=1)
            single.set_grid(1, 1)
            sp_key = single.subplot_keys_ordered()[0]
            sp_src = sheet.subplots[key]
            # Copy curves
            for uid in sp_src.curve_uids:
                if uid in sheet.curves:
                    single.add_curve(sheet.curves[uid], sp_key)
            # Copy spectra
            for uid, spec in sheet.spectra.items():
                single.spectra[uid] = spec

            fig = plt.figure()
            fig.set_size_inches(opts.get("width", 6), opts.get("height", 4))
            render_sheet(fig, single, style, quality="high")
            # Use display_name for filename
            fname = sp_src.display_name
            safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in fname)
            fpath = os.path.join(out_dir, f"{safe}.{fmt}")
            fig.savefig(fpath, dpi=dpi, bbox_inches="tight")
            plt.close(fig)

        self.statusBar().showMessage(
            f"Exported {len(keys)} subplots to {out_dir}")

    def _on_export_data(self, opts: dict):
        """Export curve data from export panel."""
        sheet = self._current_sheet()
        if not sheet:
            return

        from ...core.exporters.curve_exporter import CurveExporter
        exporter = CurveExporter()
        if exporter.can_export(sheet):
            msg = exporter.export(sheet, opts["path"], opts)
            self.statusBar().showMessage(msg)
        else:
            self.statusBar().showMessage("No curves to export")
