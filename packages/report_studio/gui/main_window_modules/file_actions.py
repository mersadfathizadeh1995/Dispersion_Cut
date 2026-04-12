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

        self._populate_sheet(curves, spectra)

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
        """Save all sheets to a new JSON project file."""
        from ...qt_compat import QtWidgets
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Project As",
            "report_project.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self._save_to_path(path)

    def _save_to_path(self, path: str):
        from ...qt_compat import QtWidgets
        from ...io.project import save_project

        try:
            save_project(self._sheets, path)
            self._project_path = path
            self._mark_clean()
            self.statusBar().showMessage(f"Project saved to {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Save Error", f"Failed to save project:\n{e}"
            )

    def _on_load_project(self):
        """Load sheets from a JSON project file."""
        from ...qt_compat import QtWidgets
        from ...io.project import load_project

        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Project",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            sheets = load_project(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Load Error", f"Failed to load project:\n{e}"
            )
            return

        # Replace current sheets
        self._sheets.clear()
        # Remove all existing tabs
        while self.sheet_tabs.count() > 0:
            w = self.sheet_tabs.widget(0)
            self.sheet_tabs.removeTab(0)
            if w:
                w.deleteLater()

        # Recreate tabs from loaded sheets
        from ..canvas.plot_canvas import PlotCanvas
        for sheet in sheets:
            self._sheets.append(sheet)
            canvas = PlotCanvas()
            canvas.curve_clicked.connect(self._on_curve_selected)
            self.sheet_tabs.add_tab(canvas, sheet.name)

        # Render first sheet
        if self._sheets:
            self.sheet_tabs.setCurrentIndex(0)
            self.data_tree.populate(self._sheets[0])
            if hasattr(self, "right_panel"):
                self.right_panel.populate_global(self._sheets[0])
                self.right_panel.update_subplot_list(
                    self._sheets[0].subplot_keys_ordered())
            self._render_current()

        self.statusBar().showMessage(
            f"Loaded project with {len(sheets)} sheets"
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
            safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in key)
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
