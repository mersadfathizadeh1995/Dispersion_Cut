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

    def __init__(self, parent=None, controller=None, show_startup: bool = True):
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

        # Show project startup dialog (skip in tests)
        if show_startup:
            QtCore.QTimer.singleShot(0, self._show_startup_dialog)

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
        self.data_tree.remove_curves_requested.connect(self._on_curves_removed)
        self.data_tree.add_data_requested.connect(self._on_add_data_to_subplot)
        self.data_tree.subplot_renamed.connect(self._on_subplot_renamed)
        self.data_tree.aggregated_selected.connect(self._on_aggregated_selected)

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
        self.right_panel.aggregated_style_changed.connect(
            self._on_aggregated_style_changed
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
        return self._add_sheet_with_state(sheet)

    def _add_sheet_with_state(self, sheet: SheetState) -> int:
        """Add a sheet (with existing state) and its canvas."""
        self._sheets.append(sheet)
        canvas = PlotCanvas()
        canvas.curve_clicked.connect(self._on_curve_selected)
        canvas.subplot_clicked.connect(self._on_subplot_clicked)
        idx = self.sheet_tabs.add_tab(canvas, sheet.name)
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
            pkeys, pnames = sheet.populated_subplot_info()
            self.right_panel.update_subplot_list(pkeys, pnames)
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
        pkeys, pnames = sheet.populated_subplot_info()
        self.right_panel.update_subplot_list(pkeys, pnames)
        self._render_current()

        n = len(curves)
        ns = len(spectra)
        self.statusBar().showMessage(f"Loaded {n} curves, {ns} spectra")

    # ── Per-subplot data addition ────────────────────────────────────────

    def _on_add_data_to_subplot(self, subplot_key: str):
        """Open AddDataDialog and insert selected curves into a subplot."""
        from .panels.add_data_dialog import AddDataDialog
        from ..qt_compat import DialogAccepted

        sheet = self._current_sheet()
        if not sheet:
            return
        # Validate subplot key
        if subplot_key not in sheet.subplots:
            subplot_key = sheet.subplot_keys_ordered()[0] if sheet.subplots else "main"

        dlg = AddDataDialog(parent=self, subplot_key=subplot_key)
        if dlg.exec() != DialogAccepted:
            return

        # Use the plugin to load data
        from ..core.figure_types import registry
        plugin = registry.get(dlg.selected_type_id)
        if not plugin:
            return

        result = plugin.load_data(
            pkl_path=dlg.pkl_path,
            npz_path=dlg.npz_path,
            selected_offsets=dlg.selected_offsets,
        )

        curves = result.get("curves", [])
        spectra = result.get("spectra", [])
        aggregated = result.get("aggregated", None)
        shadow_curves = result.get("shadow_curves", [])

        if not curves and not shadow_curves and aggregated is None:
            return

        # Add regular curves to the target subplot
        for curve in curves:
            sheet.add_curve(curve, subplot_key)

        # Handle aggregated average figure
        if aggregated is not None:
            # Add shadow curves first
            shadow_uids = []
            for sc in shadow_curves:
                sheet.add_curve(sc, subplot_key)
                shadow_uids.append(sc.uid)
            aggregated.shadow_curve_uids = shadow_uids
            sheet.add_aggregated(aggregated)
            # Link the subplot to this aggregated curve
            sp = sheet.subplots.get(subplot_key)
            if sp:
                sp.aggregated_uid = aggregated.uid

        self._finalize_sheet(sheet, curves + shadow_curves, spectra)

    # ── Rendering ──────────────────────────────────────────────────────

    def _render_current(self):
        """Schedule a debounced re-render (50 ms coalescing window)."""
        if hasattr(self, '_mark_dirty'):
            self._mark_dirty()
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

        # Keep export panel in sync with current sheet dimensions
        if hasattr(self, 'right_panel'):
            self.right_panel.set_export_sheet(sheet)

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

    def _show_startup_dialog(self):
        """Show the ProjectStartDialog, then load accordingly."""
        from .panels.project_start_dialog import ProjectStartDialog
        from ..qt_compat import DialogAccepted

        dlg = ProjectStartDialog(controller=self._controller, parent=self)
        if dlg.exec() != DialogAccepted:
            # User cancelled — start with empty studio
            return

        project_dir = dlg.project_dir
        if project_dir:
            self._project_path = project_dir

        if dlg.is_open_existing:
            # Open existing project from directory
            self._open_project_dir(project_dir)
        elif dlg.use_controller and self._controller is not None:
            self._load_from_controller(self._controller)
            if project_dir:
                self._on_save_sheet()
        else:
            pkl = dlg.pkl_path
            npz = dlg.npz_path
            if pkl:
                self._load_from_files(pkl, npz, show_dialog=True)
                if project_dir:
                    self._on_save_sheet()

    def _open_project_dir(self, project_dir: str):
        """Open a v4 project from its directory — then offer to load sheets."""
        import os
        import json

        # Try to read project-level data source paths (fallback for sheets)
        pj_path = os.path.join(project_dir, "project.json")
        proj_pkl, proj_npz = "", ""
        if os.path.isfile(pj_path):
            try:
                with open(pj_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                ds = manifest.get("data_sources", {})
                proj_pkl = ds.get("pkl_path", "")
                proj_npz = ds.get("npz_path", "")
            except Exception:
                manifest = {}
        else:
            manifest = {}

        # Store project-level paths so sheet loader can use them as fallback
        if proj_pkl:
            self._pkl_path = proj_pkl
            self._npz_path = proj_npz

        # Check for saved sheets
        from ..io.project_v4 import list_sheets
        saved = list_sheets(project_dir)
        if saved:
            from ..qt_compat import QtWidgets
            names = [n for n, _ in saved]
            choice, ok = QtWidgets.QInputDialog.getItem(
                self, "Load Sheet",
                f"Project has {len(saved)} saved sheet(s). Select one to load:",
                names, editable=False,
            )
            if ok:
                for n, folder in saved:
                    if n == choice:
                        self._load_sheet_from_folder(folder)
                        return

        # No saved sheets — fall back to project-level data
        if not manifest:
            return
        version = manifest.get("version", 0)
        if version >= 4 and "data_sources" in manifest:
            self._load_project_v4(project_dir, manifest)
        elif os.path.isfile(pj_path):
            self._load_project_legacy(pj_path)

    def _try_restore_session(self, project_dir: str):
        """Check for auto-saved session and offer to restore (with data reload)."""
        from ..io.project_v4 import load_session_manifest

        entries = load_session_manifest(project_dir)
        if not entries:
            return

        from ..qt_compat import QtWidgets
        reply = QtWidgets.QMessageBox.question(
            self, "Restore Session",
            f"Found {len(entries)} auto-saved sheet(s) from a previous session.\n"
            "Restore unsaved changes?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        import os
        import json
        from ..io.project_v4 import _dict_to_sheet_skeleton, reload_and_apply
        from ..io.pkl_reader import read_pkl
        from ..io.spectrum_reader import read_spectrum_npz
        session_dir = os.path.join(project_dir, "session")

        restored = []
        for entry in entries:
            fpath = os.path.join(session_dir, entry.get("file", ""))
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sheet = _dict_to_sheet_skeleton(data)

                # Re-read data from per-sheet paths
                pkl = getattr(sheet, "pkl_path", "") or ""
                npz = getattr(sheet, "npz_path", "") or ""
                curves, spectra = [], []
                if pkl and os.path.isfile(pkl):
                    try:
                        curves = read_pkl(pkl)
                    except Exception:
                        pass
                if npz and os.path.isfile(npz):
                    try:
                        spectra = read_spectrum_npz(npz)
                    except Exception:
                        pass

                # Apply curve settings from session
                curve_settings = {}
                for cdict in data.get("curves", {}).values():
                    cname = cdict.get("name", "")
                    if cname:
                        curve_settings[cname] = cdict
                if curves:
                    reload_and_apply(sheet, curve_settings, curves, spectra)

                restored.append(sheet)
            except Exception:
                continue

        if not restored:
            return

        # Replace current sheets with restored ones
        self._sheets.clear()
        self.sheet_tabs.clear()
        for sheet in restored:
            self._add_sheet_with_state(sheet)

        self.sheet_tabs.setCurrentIndex(0)
        if self._sheets:
            self.data_tree.populate(self._sheets[0])
            if hasattr(self, "right_panel"):
                self.right_panel.populate_global(self._sheets[0])
                pkeys, pnames = self._sheets[0].populated_subplot_info()
                self.right_panel.update_subplot_list(pkeys, pnames)
        self._render_current()

    def _initial_load(self, controller):
        """Legacy entry point — kept for backward compatibility."""
        if controller is not None:
            self._load_from_controller(controller)

    # ── Close event ────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Auto-save session, then prompt to save if dirty."""
        self._auto_save_session()

        if getattr(self, "_dirty", False):
            from ..qt_compat import QtWidgets
            btn = QtWidgets.QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QtWidgets.QMessageBox.StandardButton.Save
                | QtWidgets.QMessageBox.StandardButton.Discard
                | QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            if btn == QtWidgets.QMessageBox.StandardButton.Save:
                self._on_save_sheet()
                event.accept()
            elif btn == QtWidgets.QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
                return
        super().closeEvent(event)

    def _auto_save_session(self):
        """Auto-save all sheet states to {project}/session/ on close."""
        import os
        project_dir = getattr(self, "_project_path", "")
        if not project_dir or not os.path.isdir(project_dir):
            return

        try:
            from ..io.project_v4 import save_session
            save_session(project_dir, self._sheets)
        except Exception:
            pass
