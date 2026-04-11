"""Report Studio -- standalone window for interactive report generation.

Three-panel layout: plot selector (left), Matplotlib canvas (center),
settings tabs (right).  Debounced rendering re-draws the canvas whenever
a setting changes.  Multi-sheet support, config/sheet persistence, export.
"""
from __future__ import annotations

import copy
import os
import traceback
from functools import partial

from .qt_compat import (
    QtWidgets, QtCore,
    Horizontal, ScrollBarAlwaysOff, WA_DeleteOnClose,
    QAction, QKeySequence,
)

QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QTabWidget = QtWidgets.QTabWidget
QStatusBar = QtWidgets.QStatusBar
QSplitter = QtWidgets.QSplitter
QApplication = QtWidgets.QApplication
QScrollArea = QtWidgets.QScrollArea
QLabel = QtWidgets.QLabel
QMessageBox = QtWidgets.QMessageBox
QFileDialog = QtWidgets.QFileDialog
QInputDialog = QtWidgets.QInputDialog
QTimer = QtCore.QTimer

from ..generator import ReportGenerator
from ..utils import ensure_parent_dir_for_file
from .models import (
    ReportStudioSettings, apply_preset,
    PRESET_LABELS,
)
from .canvas_view import CanvasView
from .renderer import StudioRenderer
from .panels.plot_selector import PlotSelector
from .panels.figure_panel import FigurePanel
from .panels.typography_panel import TypographyPanel
from .panels.axis_panel import AxisPanel
from .panels.legend_panel import LegendPanel
from .panels.layers_panel import LayersPanel
from .panels.export_panel import ExportPanel
from .panels.plot_settings.frequency_settings import FrequencySettings
from .panels.plot_settings.wavelength_settings import WavelengthSettings
from .panels.plot_settings.nearfield_settings import NearFieldSettings
from .panels.plot_settings.offset_settings import OffsetSettings
from .panels.plot_settings.canvas_settings import CanvasSettings
from .sheet_tabs import SheetTabs
from .config_persistence import (
    save_render_config, load_render_config, list_render_configs,
    settings_to_dict,
)
from .sheet_persistence import (
    save_sheet, load_sheet, list_saved_sheets,
)

_FREQUENCY_KEYS = {"aggregated", "per_offset", "uncertainty"}
_WAVELENGTH_KEYS = {"aggregated_wavelength", "per_offset_wavelength", "dual_domain"}
_NEARFIELD_KEYS = {"nacd_curve", "nacd_grid", "nacd_combined", "nacd_comparison", "nacd_summary"}
_OFFSET_KEYS = {"offset_curve_only", "offset_with_spectrum", "offset_spectrum_only", "offset_grid"}
_CANVAS_KEYS = {"canvas_frequency", "canvas_wavelength", "canvas_dual"}


class ReportStudioWindow(QMainWindow):
    """Standalone report generation studio with live preview."""

    PREVIEW_DPI = 100

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._settings = ReportStudioSettings()
        self._generator = ReportGenerator.from_controller(controller)
        self._renderer = StudioRenderer(self._generator)
        self._project_dir = ""

        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(150)
        self._render_timer.timeout.connect(self._do_render)
        self._is_rendering = False

        self.setWindowTitle("Report Studio")
        self.resize(1350, 880)

        self._build_ui()
        self._build_menus()
        self._register_plot_settings()
        self._init_panels()

        QTimer.singleShot(200, self._do_render)

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Sheet tabs at top
        self._sheet_tabs = SheetTabs()
        self._sheet_tabs.setMaximumHeight(32)
        self._sheet_tabs.sheet_changed.connect(self._on_sheet_changed)
        self._sheet_tabs.settings_snapshot_requested.connect(
            self._snapshot_current_settings
        )
        main_layout.addWidget(self._sheet_tabs)

        splitter = QSplitter(Horizontal)

        # Left: plot selector
        self._plot_selector = PlotSelector()
        self._plot_selector.setMinimumWidth(200)
        self._plot_selector.setMaximumWidth(320)
        self._plot_selector.plot_type_changed.connect(self._on_plot_type_changed)
        splitter.addWidget(self._plot_selector)

        # Center: canvas
        w = self._settings.figure.width
        h = self._settings.figure.height
        self._canvas_view = CanvasView(w, h)
        splitter.addWidget(self._canvas_view)

        # Right: settings tabs
        self._tabs = QTabWidget()
        self._tabs.setMinimumWidth(280)
        self._tabs.setMaximumWidth(460)

        self._figure_panel = FigurePanel()
        self._typography_panel = TypographyPanel()
        self._axis_panel = AxisPanel()
        self._legend_panel = LegendPanel()
        self._layers_panel = LayersPanel()
        self._export_panel = ExportPanel()

        for panel, label in [
            (self._figure_panel, "Figure"),
            (self._typography_panel, "Typography"),
            (self._axis_panel, "Axis"),
            (self._legend_panel, "Legend"),
            (self._layers_panel, "Layers"),
            (self._export_panel, "Export"),
        ]:
            scroll = QScrollArea()
            scroll.setWidget(panel)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
            self._tabs.addTab(scroll, label)

        splitter.addWidget(self._tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([250, 700, 400])

        main_layout.addWidget(splitter, stretch=1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # Connect shared panel signals
        self._figure_panel.changed.connect(self._schedule_render)
        self._typography_panel.changed.connect(self._schedule_render)
        self._typography_panel.preset_requested.connect(self._apply_preset)
        self._axis_panel.changed.connect(self._schedule_render)
        self._legend_panel.changed.connect(self._schedule_render)
        self._layers_panel.visibility_changed.connect(self._on_layers_changed)
        self._export_panel.export_requested.connect(self._do_export)
        self._export_panel.batch_requested.connect(self._do_batch_export)

    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        save_cfg_act = QAction("Save Config...", self)
        save_cfg_act.setShortcut(QKeySequence("Ctrl+S"))
        save_cfg_act.triggered.connect(self._on_save_config)
        file_menu.addAction(save_cfg_act)

        load_cfg_act = QAction("Load Config...", self)
        load_cfg_act.setShortcut(QKeySequence("Ctrl+O"))
        load_cfg_act.triggered.connect(self._on_load_config)
        file_menu.addAction(load_cfg_act)

        file_menu.addSeparator()

        save_sheet_act = QAction("Save Sheet...", self)
        save_sheet_act.triggered.connect(self._on_save_sheet)
        file_menu.addAction(save_sheet_act)

        load_sheet_act = QAction("Load Sheet...", self)
        load_sheet_act.triggered.connect(self._on_load_sheet)
        file_menu.addAction(load_sheet_act)

        file_menu.addSeparator()

        export_act = QAction("Export...", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(
            lambda: self._tabs.setCurrentIndex(5)  # Export tab
        )
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        close_act = QAction("Close", self)
        close_act.setShortcut(QKeySequence("Ctrl+W"))
        close_act.triggered.connect(self.close)
        file_menu.addAction(close_act)

        # Sheet menu
        sheet_menu = menu_bar.addMenu("Sheet")
        new_sheet_act = QAction("New Sheet", self)
        new_sheet_act.triggered.connect(self._on_new_sheet)
        sheet_menu.addAction(new_sheet_act)

        # Presets menu
        presets_menu = menu_bar.addMenu("Presets")
        for name, label in PRESET_LABELS.items():
            act = QAction(label, self)
            act.triggered.connect(partial(self._apply_preset, name))
            presets_menu.addAction(act)

        # View menu
        view_menu = menu_bar.addMenu("View")
        refresh_act = QAction("Refresh", self)
        refresh_act.setShortcut(QKeySequence("F5"))
        refresh_act.triggered.connect(self._do_render)
        view_menu.addAction(refresh_act)

        reset_act = QAction("Reset to Defaults", self)
        reset_act.triggered.connect(self._reset_settings)
        view_menu.addAction(reset_act)

    def _register_plot_settings(self) -> None:
        """Create and register per-plot-type settings widgets."""
        n = len(self._generator.velocity_arrays)

        self._freq_settings = FrequencySettings()
        self._wave_settings = WavelengthSettings()
        self._nf_settings = NearFieldSettings(n_offsets=n)
        self._offset_settings = OffsetSettings(n_offsets=n)
        self._canvas_settings = CanvasSettings()

        all_widgets = [
            (self._freq_settings, _FREQUENCY_KEYS),
            (self._wave_settings, _WAVELENGTH_KEYS),
            (self._nf_settings, _NEARFIELD_KEYS),
            (self._offset_settings, _OFFSET_KEYS),
            (self._canvas_settings, _CANVAS_KEYS),
        ]
        for widget, keys in all_widgets:
            widget.changed.connect(self._schedule_render)
            for key in keys:
                self._plot_selector.register_settings_widget(key, widget)

    def _init_panels(self) -> None:
        """Initialize panels from current settings and data."""
        self._figure_panel.read_from(self._settings.figure)
        self._typography_panel.read_from(self._settings.typography)
        self._axis_panel.read_from(self._settings.axis)
        self._legend_panel.read_from(self._settings.legend)
        self._export_panel.read_from_configs(
            self._settings.export, self._settings.output,
        )

        labels = self._generator.layer_labels
        active = list(self._generator.active_flags)
        spec_flags = [sd is not None for sd in self._generator.spectrum_data_list]
        self._layers_panel.populate(labels, active, spec_flags)

    # ── Rendering ─────────────────────────────────────────────────

    def _schedule_render(self) -> None:
        if not self._is_rendering:
            self._render_timer.start()

    def _do_render(self) -> None:
        self._is_rendering = True
        self._status.showMessage("Rendering...")
        QApplication.processEvents()
        try:
            self._collect_settings()
            fig = self._canvas_view.figure
            w = self._settings.figure.width
            h = self._settings.figure.height
            self._canvas_view.update_size(w, h)

            extra_kw = self._build_extra_kwargs()
            self._renderer.render(
                self._settings, fig,
                offset_index=self._get_current_offset_index(),
                extra_kwargs=extra_kw,
            )
            self._canvas_view.refresh()
            self._status.showMessage("Ready", 3000)
        except Exception as e:
            self._status.showMessage(f"Render error: {e}")
            traceback.print_exc()
        finally:
            self._is_rendering = False

    def _collect_settings(self) -> None:
        """Read all panel values into self._settings."""
        self._figure_panel.write_to(self._settings.figure)
        self._typography_panel.write_to(self._settings.typography)
        self._axis_panel.write_to(self._settings.axis)
        self._legend_panel.write_to(self._settings.legend)
        self._export_panel.write_to_configs(
            self._settings.export, self._settings.output,
        )

        key = self._settings.active_plot_type
        if key in _FREQUENCY_KEYS:
            self._freq_settings.write_to(self._settings)
        elif key in _WAVELENGTH_KEYS:
            self._wave_settings.write_to(self._settings)
        elif key in _NEARFIELD_KEYS:
            self._nf_settings.write_to(self._settings)
        elif key in _OFFSET_KEYS:
            self._offset_settings.write_to(self._settings)
        elif key in _CANVAS_KEYS:
            self._canvas_settings.write_to(self._settings)

    def _build_extra_kwargs(self) -> dict:
        key = self._settings.active_plot_type
        kw: dict = {"max_offsets": self._settings.max_offsets}

        if key in _NEARFIELD_KEYS:
            kw["rows"] = self._nf_settings.grid_rows
            kw["cols"] = self._nf_settings.grid_cols
        elif key == "offset_grid":
            kw["rows"] = self._offset_settings.grid_rows
            kw["cols"] = self._offset_settings.grid_cols
            kw["include_spectrum"] = self._offset_settings._include_spectrum.isChecked()
            kw["include_curves"] = True
        return kw

    def _get_current_offset_index(self) -> int:
        key = self._settings.active_plot_type
        if key in _OFFSET_KEYS:
            return self._offset_settings.offset_index
        elif key in _NEARFIELD_KEYS:
            return self._nf_settings.offset_index
        return 0

    # ── Slots ─────────────────────────────────────────────────────

    def _on_plot_type_changed(self, key: str) -> None:
        self._settings.active_plot_type = key
        self._schedule_render()

    def _on_layers_changed(self) -> None:
        flags = self._layers_panel.get_active_flags()
        for i, active in enumerate(flags):
            if i < len(self._generator.active_flags):
                self._generator.active_flags[i] = active
        self._generator._binned_avg = None
        self._generator._binned_std = None
        self._generator._bin_centers = None
        self._generator._nacd_values = None
        self._schedule_render()

    def _apply_preset(self, name: str) -> None:
        apply_preset(self._settings, name)
        self._typography_panel.read_from(self._settings.typography)
        self._schedule_render()
        label = PRESET_LABELS.get(name, name)
        self._status.showMessage(f"Applied preset: {label}", 3000)

    def _reset_settings(self) -> None:
        plot_type = self._settings.active_plot_type
        self._settings = ReportStudioSettings()
        self._settings.active_plot_type = plot_type
        self._generator = ReportGenerator.from_controller(self._controller)
        self._renderer = StudioRenderer(self._generator)
        self._init_panels()
        self._schedule_render()
        self._status.showMessage("Settings reset to defaults", 3000)

    # ── Sheet management ──────────────────────────────────────────

    def _snapshot_current_settings(self) -> None:
        self._collect_settings()
        self._sheet_tabs.save_current_settings(self._settings)

    def _on_sheet_changed(self, name: str) -> None:
        restored = self._sheet_tabs.current_settings()
        self._settings = copy.deepcopy(restored)
        self._init_panels()
        if self._settings.active_plot_type:
            self._plot_selector.select_plot_type(self._settings.active_plot_type)
        self._schedule_render()

    def _on_new_sheet(self) -> None:
        self._snapshot_current_settings()
        count = self._sheet_tabs.count()
        self._sheet_tabs.add_sheet(f"Sheet {count + 1}")

    # ── Export ────────────────────────────────────────────────────

    def _do_export(self, path: str, options: dict) -> None:
        self._collect_settings()
        plot_type = self._settings.active_plot_type
        if not plot_type:
            QMessageBox.warning(self, "Export", "Select a plot type first.")
            return

        resolved = self._export_panel.resolve_filename(plot_type)
        self._status.showMessage(f"Exporting to {resolved}...")
        QApplication.processEvents()

        try:
            from matplotlib.figure import Figure as MplFigure

            config = self._renderer.build_plot_config(self._settings)
            config = config.__class__(
                **{**config.__dict__, "dpi": options.get("dpi", 300)}
            )
            export_fig = MplFigure(
                figsize=(self._settings.figure.width, self._settings.figure.height),
                dpi=options.get("dpi", 300),
            )

            extra_kw = self._build_extra_kwargs()
            self._renderer.render(
                self._settings, export_fig,
                offset_index=self._get_current_offset_index(),
                extra_kwargs=extra_kw,
            )

            ensure_parent_dir_for_file(resolved)
            export_fig.savefig(
                resolved,
                dpi=options.get("dpi", 300),
                transparent=options.get("transparent", False),
                bbox_inches=options.get("bbox_inches", "tight"),
                pad_inches=options.get("pad_inches", 0.1),
                facecolor=options.get("facecolor", "white"),
            )
            import matplotlib.pyplot as plt
            plt.close(export_fig)

            self._status.showMessage(f"Exported: {resolved}", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))
            traceback.print_exc()
            self._status.showMessage("Export failed", 3000)

    def _do_batch_export(self, directory: str, options: dict) -> None:
        self._collect_settings()
        plot_type = self._settings.active_plot_type
        if not plot_type:
            QMessageBox.warning(self, "Batch Export", "Select a plot type first.")
            return

        formats = ["png", "pdf", "svg"]
        exported = []
        for fmt in formats:
            try:
                from matplotlib.figure import Figure as MplFigure

                path = os.path.join(directory, f"{plot_type}.{fmt}")
                export_fig = MplFigure(
                    figsize=(self._settings.figure.width, self._settings.figure.height),
                    dpi=options.get("dpi", 300),
                )
                extra_kw = self._build_extra_kwargs()
                self._renderer.render(
                    self._settings, export_fig,
                    offset_index=self._get_current_offset_index(),
                    extra_kwargs=extra_kw,
                )
                ensure_parent_dir_for_file(path)
                export_fig.savefig(
                    path,
                    dpi=options.get("dpi", 300),
                    bbox_inches="tight",
                    facecolor="white",
                )
                import matplotlib.pyplot as plt
                plt.close(export_fig)
                exported.append(fmt.upper())
            except Exception as e:
                traceback.print_exc()

        self._status.showMessage(
            f"Batch export: {', '.join(exported)} to {directory}", 5000,
        )

    # ── Config persistence ────────────────────────────────────────

    def _on_save_config(self) -> None:
        self._collect_settings()
        proj = self._project_dir or self._export_panel.output_directory

        if proj:
            name, ok = QInputDialog.getText(
                self, "Save Config", "Config name:", text="Publication",
            )
            if not ok or not name.strip():
                return
            try:
                path = save_render_config(proj, name.strip(), self._settings)
                self._project_dir = proj
                self._status.showMessage(f"Config saved: {name.strip()}", 4000)
            except Exception as e:
                QMessageBox.warning(self, "Save Error", str(e))
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Config", "",
                "JSON Files (*.json);;All Files (*)",
            )
            if not path:
                return
            try:
                import json
                data = settings_to_dict(self._settings)
                data["_config_name"] = os.path.splitext(os.path.basename(path))[0]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                self._status.showMessage(f"Config saved: {path}", 4000)
            except Exception as e:
                QMessageBox.warning(self, "Save Error", str(e))

    def _on_load_config(self) -> None:
        proj = self._project_dir or self._export_panel.output_directory
        filepath = None

        if proj:
            configs = list_render_configs(proj)
            if configs:
                names = [n for n, _ in configs] + ["Browse for file..."]
                choice, ok = QInputDialog.getItem(
                    self, "Load Config", "Select config:", names, editable=False,
                )
                if not ok:
                    return
                if choice == "Browse for file...":
                    filepath = self._browse_config_file()
                else:
                    for n, fp in configs:
                        if n == choice:
                            filepath = fp
                            break
            else:
                filepath = self._browse_config_file()
        else:
            filepath = self._browse_config_file()

        if not filepath:
            return
        try:
            loaded = load_render_config(filepath)
            plot_type = self._settings.active_plot_type
            self._settings = loaded
            self._settings.active_plot_type = plot_type
            self._init_panels()
            self._schedule_render()
            self._status.showMessage(f"Config loaded: {filepath}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Load Error", str(e))

    def _browse_config_file(self) -> str | None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Config", "",
            "JSON Files (*.json);;All Files (*)",
        )
        return path or None

    # ── Sheet persistence ─────────────────────────────────────────

    def _on_save_sheet(self) -> None:
        proj = self._project_dir or self._export_panel.output_directory
        if not proj:
            proj = QFileDialog.getExistingDirectory(
                self, "Select Project Directory",
            )
            if not proj:
                return
            self._project_dir = proj

        self._collect_settings()
        default_name = self._sheet_tabs.current_sheet_name()
        name, ok = QInputDialog.getText(
            self, "Save Sheet", "Sheet name:", text=default_name,
        )
        if not ok or not name.strip():
            return
        try:
            save_sheet(proj, name.strip(), self._settings)
            self._status.showMessage(f"Sheet saved: {name.strip()}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e))

    def _on_load_sheet(self) -> None:
        proj = self._project_dir or self._export_panel.output_directory
        if not proj:
            proj = QFileDialog.getExistingDirectory(
                self, "Select Project Directory",
            )
            if not proj:
                return
            self._project_dir = proj

        sheets = list_saved_sheets(proj)
        if not sheets:
            QMessageBox.information(self, "Load Sheet", "No saved sheets found.")
            return

        names = [n for n, _ in sheets]
        choice, ok = QInputDialog.getItem(
            self, "Load Sheet", "Select sheet:", names, editable=False,
        )
        if not ok:
            return

        for n, folder in sheets:
            if n == choice:
                try:
                    sheet_name, loaded_settings = load_sheet(folder)
                    self._snapshot_current_settings()
                    idx = self._sheet_tabs.add_sheet(
                        sheet_name, loaded_settings,
                    )
                    self._settings = copy.deepcopy(loaded_settings)
                    self._init_panels()
                    if self._settings.active_plot_type:
                        self._plot_selector.select_plot_type(
                            self._settings.active_plot_type,
                        )
                    self._schedule_render()
                    self._status.showMessage(
                        f"Sheet loaded: {sheet_name}", 4000,
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Load Error", str(e))
                break
