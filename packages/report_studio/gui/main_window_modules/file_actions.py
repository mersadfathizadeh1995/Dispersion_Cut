"""File actions mixin — open/save/export."""

from __future__ import annotations


class FileActionsMixin:
    """Handles file open, save, and export operations."""

    def _on_open_data(self):
        """Open data files (PKL + NPZ) and load into current sheet."""
        from ..panels.project_dialog import ProjectDialog
        from ...qt_compat import DialogAccepted

        dlg = ProjectDialog(parent=self)
        if dlg.exec() != DialogAccepted:
            return

        self._load_from_files(dlg.pkl_path, dlg.npz_path)

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
        """Save all sheets to a JSON project file."""
        from ...qt_compat import QtWidgets
        from ...io.project import save_project

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Project",
            "report_project.json",
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            try:
                save_project(self._sheets, path)
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
            if hasattr(self, "sheet_panel"):
                self.sheet_panel.populate(self._sheets[0])
            self._render_current()

        self.statusBar().showMessage(
            f"Loaded project with {len(sheets)} sheets"
        )
