"""
Main window — thin mixin-based orchestrator for Report Studio.

Signal flow:
    Panels emit → MainWindow handler → update SheetState → render → canvas refresh
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..qt_compat import (
    QtWidgets, QtCore, Signal,
    LeftDockWidgetArea, RightDockWidgetArea,
)
from ..core.models import SheetState, OffsetCurve, SpectrumData

from .canvas.plot_canvas import PlotCanvas
from .canvas.sheet_tabs import SheetTabs
from .panels.data_tree import DataTreePanel
from .panels.right_panel import RightPanel

from .main_window_modules.menu_setup import MenuSetupMixin
from .main_window_modules.file_actions import FileActionsMixin
from .main_window_modules.data_handlers import DataHandlersMixin
from .main_window_modules.subplot_handlers import SubplotHandlersMixin


class ReportStudioWindow(
    MenuSetupMixin,
    FileActionsMixin,
    DataHandlersMixin,
    SubplotHandlersMixin,
    QtWidgets.QMainWindow,
):
    """
    Report Studio v2 — lightweight main window.

    This class:
    - Creates the layout (central canvas, docks)
    - Connects signals between panels and handlers
    - Maintains per-sheet SheetState objects
    - Delegates rendering to render_sheet()
    """

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.setWindowTitle("DC Cut — Report Studio")
        self.resize(1200, 800)

        self._controller = controller
        self._sheets: List[SheetState] = []
        self._selected_uid: Optional[str] = None

        # Debounce timer for rapid setting changes
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(50)  # 50 ms debounce
        self._render_timer.timeout.connect(self._do_render)

        self._build_ui()
        self._setup_menubar()
        self._connect_signals()

        # Show project dialog on startup
        QtCore.QTimer.singleShot(0, lambda: self._initial_load(controller))

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self):
        # Central: sheet tabs with canvases
        self.sheet_tabs = SheetTabs()
        self.setCentralWidget(self.sheet_tabs)

        # Create first sheet with canvas
        self._add_new_sheet("Sheet 1")

        # Left dock: data tree
        self.data_tree = DataTreePanel()
        left_dock = QtWidgets.QDockWidget("Data", self)
        left_dock.setWidget(self.data_tree)
        self.addDockWidget(LeftDockWidgetArea, left_dock)

        # Right dock: 3-tab right panel (Context / Global / Export)
        self.right_panel = RightPanel()
        right_dock = QtWidgets.QDockWidget("Settings", self)
        right_dock.setWidget(self.right_panel)
        self.addDockWidget(RightDockWidgetArea, right_dock)

        # Status bar
        self.statusBar().showMessage("Report Studio ready")

    def _connect_signals(self):
        """Wire signals from panels to handler methods."""
        # Menu
        self._connect_menu_signals()
        self._act_open.triggered.connect(self._on_open_data)
        self._act_export_img.triggered.connect(self._on_export_image)

        # Sheet tabs
        self.sheet_tabs.sheet_changed.connect(self._on_sheet_changed)
        self.sheet_tabs.add_sheet_requested.connect(
            lambda: self._add_new_sheet(f"Sheet {len(self._sheets) + 1}")
        )

        # Data tree
        self.data_tree.curve_selected.connect(self._on_curve_selected)
        self.data_tree.curves_selected.connect(self._on_curves_selected)
        self.data_tree.spectrum_selected.connect(self._on_spectrum_selected)
        self.data_tree.spectra_selected.connect(self._on_spectra_selected)
        self.data_tree.subplot_selected.connect(self._on_subplot_selected)
        self.data_tree.subplots_selected.connect(self._on_subplots_selected)
        self.data_tree.curve_visibility_changed.connect(
            self._on_curve_visibility_changed
        )
        self.data_tree.spectrum_visibility_changed.connect(
            self._on_spectrum_visibility_changed
        )
        self.data_tree.curve_moved.connect(self._on_curve_moved)
        self.data_tree.remove_curve_requested.connect(self._on_curve_removed)
        self.data_tree.add_data_requested.connect(self._on_open_data)

        # Right panel — Context tab (subplot / curve / spectrum settings)
        self.right_panel.subplot_setting_changed.connect(
            self._on_subplot_setting_changed
        )
        self.right_panel.curve_style_changed.connect(
            self._on_style_changed
        )
        self.right_panel.spectrum_style_changed.connect(
            self._on_style_changed
        )

        # Right panel — Global tab
        self.right_panel.grid_changed.connect(self._on_grid_changed)
        self.right_panel.layout_changed.connect(self._on_layout_changed)
        self.right_panel.legend_changed.connect(self._on_legend_changed)

        # Right panel — Export tab
        self.right_panel.export_figure_requested.connect(
            self._on_export_figure)
        self.right_panel.export_subplots_requested.connect(
            self._on_export_subplots)
        self.right_panel.export_data_requested.connect(
            self._on_export_data)

    # ── Sheet management ───────────────────────────────────────────────

    def _add_new_sheet(self, name: str) -> int:
        """Create a new empty sheet with its own canvas."""
        sheet = SheetState(name=name)
        self._sheets.append(sheet)
        canvas = PlotCanvas()
        canvas.curve_clicked.connect(self._on_curve_selected)
        canvas.subplot_clicked.connect(self._on_subplot_clicked)
        idx = self.sheet_tabs.add_tab(canvas, name)
        return idx

    def _current_sheet_index(self) -> int:
        return self.sheet_tabs.currentIndex()

    def _current_sheet(self) -> Optional[SheetState]:
        idx = self._current_sheet_index()
        if 0 <= idx < len(self._sheets):
            return self._sheets[idx]
        return None

    def _on_sheet_changed(self, index: int):
        """Tab changed — sync tree + right panel to new sheet."""
        sheet = self._current_sheet()
        if sheet:
            self.data_tree.populate(sheet)
            self.right_panel.populate_global(sheet)
            self.right_panel.update_subplot_list(sheet.subplot_keys_ordered())
            self._selected_uid = None
            self.right_panel.show_empty()
        self.statusBar().showMessage(f"Sheet: {sheet.name}" if sheet else "")

    # ── Data population ────────────────────────────────────────────────

    def _populate_sheet(self, curves: List[OffsetCurve],
                        spectra: List[SpectrumData]):
        """Show assignment dialog then add curves to the current sheet."""
        sheet = self._current_sheet()
        if not sheet or not curves:
            return

        # Show assignment dialog for grid-first workflow
        from .panels.assignment_dialog import AssignmentDialog
        from ..qt_compat import DialogAccepted

        dlg = AssignmentDialog(curves, parent=self)
        if dlg.exec() != DialogAccepted:
            return

        # Apply grid from dialog
        rows, cols = dlg.grid_rows, dlg.grid_cols
        if rows != sheet.grid_rows or cols != sheet.grid_cols:
            sheet.set_grid(rows, cols)

        # Add curves to their assigned subplots
        assignments = dlg.assignments
        for key, uids in assignments.items():
            if key not in sheet.subplots:
                continue
            for uid in uids:
                curve = next((c for c in curves if c.uid == uid), None)
                if curve:
                    sheet.add_curve(curve, key)

        # Add any unassigned curves to the first subplot
        assigned_uids = set()
        for uid_list in assignments.values():
            assigned_uids.update(uid_list)
        first_key = sheet.subplot_keys_ordered()[0] if sheet.subplots else "main"
        for curve in curves:
            if curve.uid not in assigned_uids:
                sheet.add_curve(curve, first_key)

        self._finalize_sheet(sheet, curves, spectra)

    def _populate_sheet_direct(self, curves: List[OffsetCurve],
                               spectra: List[SpectrumData]):
        """Add curves to the current sheet without showing a dialog.

        Used for programmatic loading (tests, controller data).
        """
        sheet = self._current_sheet()
        if not sheet:
            return
        for curve in curves:
            sheet.add_curve(curve)
        self._finalize_sheet(sheet, curves, spectra)

    def _finalize_sheet(self, sheet: SheetState,
                        curves: List[OffsetCurve],
                        spectra: List[SpectrumData]):
        """Link spectra, refresh panels, render."""
        from ..io.spectrum_reader import normalize_offset

        # Link spectra to curves by normalized offset (e.g. '+66', '-20')
        for spec in spectra:
            sheet.spectra[spec.uid] = spec
            spec_norm = normalize_offset(spec.offset_name)
            for c in sheet.curves.values():
                offset_tag = c.name.split("/")[-1].strip()
                curve_norm = normalize_offset(offset_tag)
                if curve_norm == spec_norm:
                    c.spectrum_uid = spec.uid
                    break

        self.data_tree.populate(sheet)
        self.right_panel.populate_global(sheet)
        self.right_panel.update_subplot_list(sheet.subplot_keys_ordered())
        self._render_current()

        n = len(curves)
        ns = len(spectra)
        self.statusBar().showMessage(f"Loaded {n} curves, {ns} spectra")

    # ── Rendering ──────────────────────────────────────────────────────

    def _render_current(self):
        """Schedule a debounced re-render (50 ms coalescing window)."""
        if hasattr(self, '_render_timer'):
            self._render_timer.start()
        else:
            self._do_render()

    def _do_render(self):
        """Actually re-render the current sheet's canvas."""
        sheet = self._current_sheet()
        canvas = self.sheet_tabs.current_canvas()
        if not sheet or not canvas:
            return

        from ..rendering.renderer import render_sheet
        from ..rendering.style import StyleConfig

        # Build style from sheet's legend + typography settings
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
        canvas.render(sheet, style, selected_uid=self._selected_uid)

    # ── Initial load ───────────────────────────────────────────────────

    def _initial_load(self, controller):
        """Show project dialog on startup."""
        if controller is not None:
            self._load_from_controller(controller)
        else:
            from .panels.project_dialog import ProjectDialog
            from ..qt_compat import DialogAccepted

            dlg = ProjectDialog(parent=self, controller=controller)
            if dlg.exec() == DialogAccepted:
                if dlg.use_controller and controller:
                    self._load_from_controller(controller)
                else:
                    self._load_from_files(dlg.pkl_path, dlg.npz_path)
