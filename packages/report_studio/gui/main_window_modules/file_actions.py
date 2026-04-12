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

        # Store paths for v4 project save + QSettings
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

    def _on_save_project(self):
        """Save all sheets — reuse existing path or prompt."""
        if self._project_path:
            self._save_to_path(self._project_path)
        else:
            self._on_save_project_as()

    def _on_save_project_as(self):
        """Save all sheets to a new project directory (v4 format)."""
        from ...qt_compat import QtWidgets
        # Ask for base directory
        base = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose Base Directory for Project",
        )
        if not base:
            return
        # Ask for project name
        name, ok = QtWidgets.QInputDialog.getText(
            self, "Project Name", "Enter project name:",
        )
        if not ok or not name.strip():
            return
        import os
        project_dir = os.path.join(base, name.strip())
        os.makedirs(os.path.join(project_dir, "sheets"), exist_ok=True)
        os.makedirs(os.path.join(project_dir, "session"), exist_ok=True)
        self._save_to_path(project_dir)

        # Add to recent projects
        from ..panels.project_start_dialog import add_recent_project
        add_recent_project(project_dir)

    def _save_to_path(self, path: str):
        from ...qt_compat import QtWidgets
        import os

        try:
            # Detect if path is a directory (v4) or file (legacy v3)
            if os.path.isfile(path) and path.endswith(".json"):
                # Legacy save to single JSON file
                from ...io.project import save_project
                save_project(self._sheets, path)
            else:
                # New v4 directory-based save
                from ...io.project_v4 import save_project, compute_fingerprint
                from ...core.models import OffsetCurve

                pkl = getattr(self, "_pkl_path", "")
                npz = getattr(self, "_npz_path", "")
                all_curves = []
                for s in self._sheets:
                    all_curves.extend(s.curves.values())
                fp = compute_fingerprint(all_curves)

                save_project(path, self._sheets,
                             pkl_path=pkl, npz_path=npz,
                             fingerprint=fp)

            self._project_path = path
            self._mark_clean()
            self.statusBar().showMessage(f"Project saved to {path}")

            # Update recent projects
            from ..panels.project_start_dialog import add_recent_project
            add_recent_project(path)
            if hasattr(self, "_refresh_recent_menu"):
                self._refresh_recent_menu()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Save Error", f"Failed to save project:\n{e}"
            )

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
        for sheet, curve_settings in sheet_skeletons:
            reload_and_apply(sheet, curve_settings, curves, spectra)
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

        style = StyleConfig(
            title_size=sheet.typography.title_size,
            axis_label_size=sheet.typography.axis_label_size,
            tick_label_size=sheet.typography.tick_label_size,
            font_family=sheet.typography.font_family,
            legend_visible=sheet.legend.visible,
            legend_position=sheet.legend.position,
            legend_font_size=sheet.legend.font_size,
            legend_frame_on=sheet.legend.frame_on,
            legend_alpha=sheet.legend.alpha,
        )
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

        style = StyleConfig(
            title_size=sheet.typography.title_size,
            axis_label_size=sheet.typography.axis_label_size,
            tick_label_size=sheet.typography.tick_label_size,
            font_family=sheet.typography.font_family,
            legend_visible=sheet.legend.visible,
            legend_position=sheet.legend.position,
            legend_font_size=sheet.legend.font_size,
            legend_frame_on=sheet.legend.frame_on,
            legend_alpha=sheet.legend.alpha,
        )

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
