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
    Horizontal, ScrollBarAlwaysOff,
    QAction, QKeySequence,
    MsgBoxYes, MsgBoxNo, DialogAccepted,
)

QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QTabWidget = QtWidgets.QTabWidget
QStatusBar = QtWidgets.QStatusBar
QSplitter = QtWidgets.QSplitter
QStackedWidget = QtWidgets.QStackedWidget
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
from .figure_model import FigureModel
from .preset_builder import build_from_preset
from .canvas_view import CanvasView
from .renderer import StudioRenderer
from .composable_renderer import ComposableRenderer
from .project_dialog import StudioProjectDialog
from .panels.plot_selector import PlotSelector
from .panels.data_tree import DataTree
from .panels.properties_router import PropertiesRouter
from .panels.figure_panel import FigurePanel
from .panels.typography_panel import TypographyPanel
from .panels.axis_panel import AxisPanel
from .panels.legend_panel import LegendPanel
from .panels.layers_panel import LayersPanel
from .panels.export_panel import ExportPanel
from .panels.spectrum_theme_panel import SpectrumThemePanel
from .panels.style_panel import StylePanel
from .panels.axis_legend_panel import AxisLegendPanel
from .panels.plot_settings.frequency_settings import FrequencySettings
from .panels.plot_settings.wavelength_settings import WavelengthSettings
from .panels.plot_settings.nearfield_settings import NearFieldSettings
from .panels.plot_settings.offset_settings import OffsetSettings
from .panels.plot_settings.canvas_settings import CanvasSettings
from .panels.plot_settings.offset_grid_settings import OffsetGridSettings
from .sheet_tabs import SheetTabs
from .config_persistence import (
    save_render_config, load_render_config, list_render_configs,
    settings_to_dict,
)
from .sheet_persistence import (
    save_sheet, load_sheet_with_fingerprint,
    check_data_match, list_saved_sheets,
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
        self._project_dir = ""

        # Show project dialog before initializing
        dlg = StudioProjectDialog(controller=controller, parent=parent)
        if dlg.exec() != DialogAccepted:
            # User cancelled; schedule close after event loop starts
            QTimer.singleShot(0, self.close)
            self._generator = None
            self._renderer = None
            self._composable_renderer = None
            return

        # Determine data source
        if dlg.use_controller:
            self._generator = ReportGenerator.from_controller(controller)
        else:
            self._generator = self._load_generator_from_files(
                dlg.pkl_path, dlg.npz_path,
            )
            if self._generator is None:
                QTimer.singleShot(0, self.close)
                self._renderer = None
                self._composable_renderer = None
                return

        self._renderer = StudioRenderer(self._generator)
        self._composable_renderer = ComposableRenderer(self._generator)

        # Store project dir to apply after UI build
        self._pending_project_dir = dlg.project_dir or ""

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

        # Apply project directory now that UI is ready
        if self._pending_project_dir:
            self._set_project_dir(self._pending_project_dir)
        del self._pending_project_dir

        QTimer.singleShot(200, self._do_render)
        # Try restoring previous session sheets
        QTimer.singleShot(400, self._try_restore_session_quiet)

    def _try_restore_session_quiet(self) -> None:
        """Attempt session restore without prompting if no sheets found."""
        try:
            self._try_restore_session()
        except Exception:
            pass

    @staticmethod
    def _load_generator_from_files(
        pkl_path: str, npz_path: str = "",
    ) -> "ReportGenerator | None":
        """Load a ReportGenerator from saved session (.pkl) and optional .npz.

        Returns None on failure.
        """
        import numpy as np
        from dc_cut.core.io.state import load_session

        try:
            state = load_session(pkl_path)
        except Exception as e:
            QMessageBox.critical(
                None, "Load Error",
                f"Failed to load session file:\n{e}",
            )
            return None

        vel = [np.asarray(a, float) for a in state.get("velocity_arrays", [])]
        freq = [np.asarray(a, float) for a in state.get("frequency_arrays", [])]
        wave = [np.asarray(a, float) for a in state.get("wavelength_arrays", [])]
        labels = list(state.get("set_leg", [f"Layer {i+1}" for i in range(len(vel))]))

        if not vel:
            QMessageBox.critical(
                None, "Load Error",
                "Session file contains no data arrays.",
            )
            return None

        # Load spectrum if provided
        spectrum_data_list = None
        if npz_path and os.path.isfile(npz_path):
            try:
                from dc_cut.core.io.spectrum import load_combined_spectrum_npz
                spec_dict = load_combined_spectrum_npz(npz_path)
                # Convert offset-keyed dict to ordered list matching labels
                spectrum_data_list = []
                for lbl in labels[:len(vel)]:
                    matched = spec_dict.get(lbl)
                    if matched is None:
                        # Try matching without 'm' suffix, etc.
                        for k, v in spec_dict.items():
                            if k.strip("m ") == lbl.strip("m "):
                                matched = v
                                break
                    spectrum_data_list.append(matched)
            except Exception:
                spectrum_data_list = None

        gen = ReportGenerator.from_arrays(
            velocity_arrays=vel,
            frequency_arrays=freq,
            wavelength_arrays=wave,
            layer_labels=labels[:len(vel)],
        )
        if spectrum_data_list:
            gen.spectrum_data_list = spectrum_data_list
            gen.spectrum_visible_flags = [s is not None for s in spectrum_data_list]
        return gen

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

        # Left: stacked widget (page 0 = plot selector, page 1 = layer editor)
        self._left_stack = QStackedWidget()
        self._left_stack.setMinimumWidth(200)
        self._left_stack.setMaximumWidth(360)

        # Page 0: plot selector + commit button
        selector_page = QWidget()
        selector_layout = QVBoxLayout(selector_page)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_layout.setSpacing(2)
        self._plot_selector = PlotSelector()
        self._plot_selector.plot_type_changed.connect(self._on_plot_type_changed)
        selector_layout.addWidget(self._plot_selector, stretch=1)
        self._commit_btn = QtWidgets.QPushButton("Commit to Sheet")
        self._commit_btn.setToolTip("Lock this plot type and switch to layer editing")
        self._commit_btn.clicked.connect(self._on_commit_to_sheet)
        selector_layout.addWidget(self._commit_btn)
        self._left_stack.addWidget(selector_page)

        # Page 1: data tree (composable mode)
        self._data_tree = DataTree()
        self._data_tree.set_offset_labels(list(self._generator.layer_labels))
        self._data_tree.back_requested.connect(self._on_back_to_selector)
        self._data_tree.selection_changed.connect(self._on_tree_selection_changed)
        self._data_tree.data_visibility_changed.connect(self._on_data_visibility_changed)
        self._data_tree.structure_changed.connect(self._on_tree_structure_changed)
        self._left_stack.addWidget(self._data_tree)

        self._left_stack.setCurrentIndex(0)
        splitter.addWidget(self._left_stack)

        # Center: canvas
        w = self._settings.figure.width
        h = self._settings.figure.height
        self._canvas_view = CanvasView(w, h)
        self._canvas_view.preview_dpi_changed.connect(self._on_preview_dpi_changed)
        splitter.addWidget(self._canvas_view)

        # Right: context-sensitive properties via PropertiesRouter
        self._tabs = QTabWidget()

        self._figure_panel = FigurePanel()
        self._typography_panel = TypographyPanel()
        self._axis_panel = AxisPanel()
        self._legend_panel = LegendPanel()
        self._spectrum_panel = SpectrumThemePanel()
        self._layers_panel = LayersPanel()
        self._export_panel = ExportPanel()

        # Merged composite panels
        self._style_panel = StylePanel(self._typography_panel, self._spectrum_panel)
        self._axis_legend_panel = AxisLegendPanel(self._axis_panel, self._legend_panel)

        for panel, label in [
            (self._figure_panel, "Figure"),
            (self._style_panel, "Style"),
            (self._axis_legend_panel, "Axis && Legend"),
            (self._export_panel, "Export"),
        ]:
            scroll = QScrollArea()
            scroll.setWidget(panel)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
            self._tabs.addTab(scroll, label)

        self._properties_router = PropertiesRouter(self._tabs)
        self._properties_router.setMinimumWidth(280)
        self._properties_router.setMaximumWidth(460)
        self._properties_router.style_changed.connect(self._schedule_render)
        splitter.addWidget(self._properties_router)

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
        self._style_panel.changed.connect(self._schedule_render)
        self._style_panel.preset_requested.connect(self._apply_preset)
        self._axis_legend_panel.changed.connect(self._schedule_render)
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
        export_act.triggered.connect(self._show_export_tab)
        file_menu.addAction(export_act)

        file_menu.addSeparator()

        chg_project_act = QAction("Change Project Directory...", self)
        chg_project_act.triggered.connect(self._prompt_project_dir)
        file_menu.addAction(chg_project_act)

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
        labels = list(self._generator.layer_labels)
        spec_flags = [sd is not None for sd in self._generator.spectrum_data_list]

        self._freq_settings = FrequencySettings()
        self._wave_settings = WavelengthSettings()
        self._nf_settings = NearFieldSettings(offset_labels=labels)
        self._offset_settings = OffsetSettings(
            offset_labels=labels, spectrum_flags=spec_flags,
        )
        self._canvas_settings = CanvasSettings()
        self._grid_settings = OffsetGridSettings(
            offset_labels=labels, spectrum_flags=spec_flags,
        )

        _single_offset_keys = {"offset_curve_only", "offset_with_spectrum", "offset_spectrum_only"}
        all_widgets = [
            (self._freq_settings, _FREQUENCY_KEYS),
            (self._wave_settings, _WAVELENGTH_KEYS),
            (self._nf_settings, _NEARFIELD_KEYS - {"nacd_grid"}),
            (self._offset_settings, _single_offset_keys),
            (self._canvas_settings, _CANVAS_KEYS),
            (self._grid_settings, {"offset_grid", "nacd_grid"}),
        ]
        for widget, keys in all_widgets:
            widget.changed.connect(self._schedule_render)
            for key in keys:
                self._plot_selector.register_settings_widget(key, widget)

    def _init_panels(self) -> None:
        """Initialize panels from current settings and data."""
        self._canvas_view.set_preview_dpi(self._settings.figure.preview_dpi)
        self._figure_panel.read_from(self._settings.figure)
        self._typography_panel.read_from(self._settings.typography)
        self._axis_panel.read_from(self._settings.axis)
        self._legend_panel.read_from(self._settings.legend)
        self._spectrum_panel.read_from(self._settings.spectrum)
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
            self._canvas_view.set_preview_dpi(self._settings.figure.preview_dpi)
            self._canvas_view.update_size(w, h)

            model = self._settings.figure_model
            if self._settings.committed and isinstance(model, FigureModel):
                self._composable_renderer.render(model, self._settings, fig)
            elif self._should_use_live_grid_preview():
                temp_model = self._build_live_grid_model()
                self._composable_renderer.render(
                    temp_model, self._settings, fig,
                )
            else:
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
        self._spectrum_panel.write_to(self._settings.spectrum)
        self._export_panel.write_to_configs(
            self._settings.export, self._settings.output,
        )

        key = self._settings.active_plot_type
        if key in _FREQUENCY_KEYS:
            self._freq_settings.write_to(self._settings)
        elif key in _WAVELENGTH_KEYS:
            self._wave_settings.write_to(self._settings)
        elif key in {"offset_grid", "nacd_grid"}:
            self._grid_settings.write_to(self._settings)
        elif key in _NEARFIELD_KEYS:
            self._nf_settings.write_to(self._settings)
        elif key in _OFFSET_KEYS:
            self._offset_settings.write_to(self._settings)
        elif key in _CANVAS_KEYS:
            self._canvas_settings.write_to(self._settings)

    def _build_extra_kwargs(self) -> dict:
        key = self._settings.active_plot_type
        kw: dict = {"max_offsets": self._settings.max_offsets}

        if key in {"offset_grid", "nacd_grid"}:
            kw["rows"] = self._grid_settings.grid_rows
            kw["cols"] = self._grid_settings.grid_cols
            kw["include_spectrum"] = self._grid_settings.include_spectrum
            kw["include_curves"] = self._grid_settings.include_curves
        elif key in _NEARFIELD_KEYS:
            kw["rows"] = self._nf_settings.grid_rows
            kw["cols"] = self._nf_settings.grid_cols
        return kw

    def _get_current_offset_index(self) -> int:
        key = self._settings.active_plot_type
        if key in _OFFSET_KEYS:
            return self._offset_settings.offset_index
        elif key in _NEARFIELD_KEYS:
            return self._nf_settings.offset_index
        return 0

    def _should_use_live_grid_preview(self) -> bool:
        """Check if the offset settings configure a multi-offset grid."""
        key = self._settings.active_plot_type
        if key not in _OFFSET_KEYS:
            return False
        selected = self._offset_settings.get_selected_indices()
        if len(selected) < 2:
            return False
        rows = self._offset_settings.grid_rows
        cols = self._offset_settings.grid_cols
        return (rows is not None and rows > 1) or (cols is not None and cols > 1)

    def _build_live_grid_model(self) -> FigureModel:
        """Build a temporary FigureModel from offset settings for live preview."""
        plot_type = self._settings.active_plot_type
        return build_from_preset(
            plot_type,
            self._generator,
            self._settings,
            offset_indices=self._offset_settings.get_selected_indices() or [0],
            grid_rows=self._offset_settings.grid_rows,
            grid_cols=self._offset_settings.grid_cols,
            assignment_map=self._offset_settings.get_assignment_map(),
        )

    # ── Slots ─────────────────────────────────────────────────────

    def _show_export_tab(self) -> None:
        self._properties_router.show_global()
        self._tabs.setCurrentIndex(6)

    def _on_preview_dpi_changed(self, dpi: int) -> None:
        self._settings.figure.preview_dpi = dpi
        self._schedule_render()

    def _on_plot_type_changed(self, key: str) -> None:
        self._settings.active_plot_type = key
        self._schedule_render()

    def _on_commit_to_sheet(self) -> None:
        """Lock the current plot type and switch to data tree."""
        plot_type = self._settings.active_plot_type
        if not plot_type:
            QMessageBox.information(self, "Commit", "Select a plot type first.")
            return
        self._settings.committed = True

        extra = {}
        if plot_type in _OFFSET_KEYS:
            extra["offset_indices"] = self._offset_settings.get_selected_indices() or [0]
            extra["grid_rows"] = self._offset_settings.grid_rows
            extra["grid_cols"] = self._offset_settings.grid_cols
            extra["assignment_map"] = self._offset_settings.get_assignment_map()
        elif plot_type in {"offset_grid", "nacd_grid"}:
            extra["offset_indices"] = self._grid_settings.get_selected_indices()
            extra["grid_rows"] = self._grid_settings.grid_rows
            extra["grid_cols"] = self._grid_settings.grid_cols

        model = build_from_preset(
            plot_type, self._generator, self._settings, **extra,
        )
        self._settings.figure_model = model
        self._properties_router.set_model(model)
        self._data_tree.populate(model)
        # Set spectrum availability based on generator data
        if hasattr(self._generator, "spectrum_data_list"):
            flags = [
                d is not None for d in self._generator.spectrum_data_list
            ]
            self._data_tree.set_spectrum_availability(flags)
        self._left_stack.setCurrentIndex(1)
        self._schedule_render()
        self._status.showMessage(f"Committed: {plot_type}", 3000)

    def _on_back_to_selector(self) -> None:
        """Return to the plot selector from the data tree."""
        self._settings.committed = False
        self._settings.figure_model = None
        self._properties_router.set_model(None)
        self._properties_router.show_global()
        self._left_stack.setCurrentIndex(0)
        self._schedule_render()

    def _on_tree_selection_changed(self, item_type: str, key: str) -> None:
        """Respond to selection changes in the data tree."""
        if hasattr(self, "_properties_router"):
            self._properties_router.show_for(item_type, key, self._settings)

    def _on_data_visibility_changed(self, uid: str, visible: bool) -> None:
        """Respond to checkbox toggle on a data series."""
        self._schedule_render()

    def _on_tree_structure_changed(self) -> None:
        """Respond to add/remove subplot or data, or drag-drop reorder."""
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
        self._composable_renderer = ComposableRenderer(self._generator)
        self._properties_router.set_model(None)
        self._properties_router.show_global()
        self._left_stack.setCurrentIndex(0)
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
        model = self._settings.figure_model
        if self._settings.committed and isinstance(model, FigureModel):
            self._properties_router.set_model(model)
            self._data_tree.populate(model)
            self._left_stack.setCurrentIndex(1)
        else:
            self._properties_router.set_model(None)
            self._properties_router.show_global()
            self._left_stack.setCurrentIndex(0)
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

            export_dpi = options.get("dpi", 300)
            export_fig = MplFigure(
                figsize=(self._settings.figure.width, self._settings.figure.height),
                dpi=export_dpi,
            )

            model = self._settings.figure_model
            if self._settings.committed and isinstance(model, FigureModel):
                self._composable_renderer.render(model, self._settings, export_fig)
            else:
                extra_kw = self._build_extra_kwargs()
                self._renderer.render(
                    self._settings, export_fig,
                    offset_index=self._get_current_offset_index(),
                    extra_kwargs=extra_kw,
                )

            ensure_parent_dir_for_file(resolved)
            export_fig.savefig(
                resolved,
                dpi=export_dpi,
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
                export_dpi = options.get("dpi", 300)
                export_fig = MplFigure(
                    figsize=(self._settings.figure.width, self._settings.figure.height),
                    dpi=export_dpi,
                )

                model = self._settings.figure_model
                if self._settings.committed and isinstance(model, FigureModel):
                    self._composable_renderer.render(model, self._settings, export_fig)
                else:
                    extra_kw = self._build_extra_kwargs()
                    self._renderer.render(
                        self._settings, export_fig,
                        offset_index=self._get_current_offset_index(),
                        extra_kwargs=extra_kw,
                    )

                ensure_parent_dir_for_file(path)
                export_fig.savefig(
                    path, dpi=export_dpi,
                    bbox_inches="tight", facecolor="white",
                )
                import matplotlib.pyplot as plt
                plt.close(export_fig)
                exported.append(fmt.upper())
            except Exception as e:
                traceback.print_exc()

        self._status.showMessage(
            f"Batch export: {', '.join(exported)} to {directory}", 5000,
        )

    # ── Project directory ───────────────────────────────────────

    def _prompt_project_dir(self) -> None:
        """Allow user to change the project directory via file dialog."""
        d = QFileDialog.getExistingDirectory(
            self, "Select Project Directory",
            self._project_dir or "",
        )
        if d:
            self._set_project_dir(d)

    def _set_project_dir(self, path: str) -> None:
        self._project_dir = path
        for sub in ("render", "sheets", "exports", "session"):
            os.makedirs(os.path.join(path, sub), exist_ok=True)
        self._export_panel.set_output_directory(path)
        self.setWindowTitle(f"Report Studio — {os.path.basename(path)}")
        self._status.showMessage(f"Project: {path}", 4000)

    def _auto_save_session(self) -> None:
        """Save all sheet states to session/ for restore on next open."""
        if not self._project_dir:
            return
        session_dir = os.path.join(self._project_dir, "session")
        os.makedirs(session_dir, exist_ok=True)
        import json
        self._snapshot_current_settings()
        manifest = {"sheets": []}
        for i, name in enumerate(self._sheet_tabs.all_sheet_names()):
            settings = self._sheet_tabs._sheet_settings.get(i)
            if settings is None:
                continue
            d = settings_to_dict(settings)
            d["_sheet_name"] = name
            fpath = os.path.join(session_dir, f"sheet_{i}.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2, ensure_ascii=False)
            manifest["sheets"].append({"index": i, "name": name, "file": f"sheet_{i}.json"})
        with open(os.path.join(session_dir, "session_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    def _try_restore_session(self) -> bool:
        """Attempt to restore sheets from a previous session. Returns True if restored."""
        if not self._project_dir:
            return False
        import json
        manifest_path = os.path.join(self._project_dir, "session", "session_manifest.json")
        if not os.path.isfile(manifest_path):
            return False
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            sheets = manifest.get("sheets", [])
            if not sheets:
                return False
            reply = QMessageBox.question(
                self, "Restore Session",
                f"Found {len(sheets)} sheet(s) from a previous session.\nRestore them?",
                MsgBoxYes | MsgBoxNo,
            )
            if reply != MsgBoxYes:
                return False
            from .config_persistence import settings_from_dict
            session_dir = os.path.join(self._project_dir, "session")
            for entry in sheets:
                fpath = os.path.join(session_dir, entry["file"])
                if not os.path.isfile(fpath):
                    continue
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data.pop("_sheet_name", None)
                loaded = settings_from_dict(data)
                self._sheet_tabs.add_sheet(entry["name"], loaded)
            self._on_sheet_changed(self._sheet_tabs.current_sheet_name())
            return True
        except Exception:
            return False

    def closeEvent(self, event) -> None:
        if self._generator is not None:
            self._auto_save_session()
        super().closeEvent(event)

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
            save_sheet(
                proj, name.strip(), self._settings,
                layer_labels=list(self._generator.layer_labels),
                freq_arrays=list(self._generator.frequency_arrays),
                vel_arrays=list(self._generator.velocity_arrays),
            )
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
                    sheet_name, loaded_settings, fp = load_sheet_with_fingerprint(folder)
                    if fp and not check_data_match(
                        fp,
                        list(self._generator.layer_labels),
                        list(self._generator.frequency_arrays),
                        list(self._generator.velocity_arrays),
                    ):
                        QMessageBox.warning(
                            self, "Data Mismatch",
                            "The loaded data has changed since this sheet was saved.\n"
                            "Layer states and point masks may not match.",
                        )
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
                    model = self._settings.figure_model
                    if self._settings.committed and isinstance(model, FigureModel):
                        self._properties_router.set_model(model)
                        self._data_tree.populate(model)
                        self._left_stack.setCurrentIndex(1)
                    else:
                        self._properties_router.set_model(None)
                        self._properties_router.show_global()
                        self._left_stack.setCurrentIndex(0)
                    self._schedule_render()
                    self._status.showMessage(
                        f"Sheet loaded: {sheet_name}", 4000,
                    )
                except Exception as e:
                    QMessageBox.warning(self, "Load Error", str(e))
                break
