"""
Export Wizard Main Window
=========================

Main window for the export wizard application.
Can be launched standalone or from DC Cut.
"""

import sys
from typing import Optional
from pathlib import Path

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui

from .data_model import CurveDataModel
from .wizard_canvas import WizardCanvas
from .wizard_table import WizardTable
from .processing_panel import ProcessingPanel
from .export_dialog import ExportDialog


class ExportWizardWindow(QtWidgets.QMainWindow):
    """
    Main window for the Export Wizard.
    
    Features:
    - Load curve data from file or from DC Cut
    - Interactive canvas visualization
    - Editable data table
    - Processing tools (resample, uncertainty, trim)
    - Export to multiple formats
    """
    
    def __init__(self, parent=None, suggested_file: Optional[str] = None):
        super().__init__(parent)
        self._model: Optional[CurveDataModel] = None
        self._undo_stack = []
        self._redo_stack = []
        self._suggested_file = suggested_file  # Pre-filled path for browse dialog
        
        self.setWindowTitle("Export Wizard - DC Cut")
        self.setMinimumSize(1200, 700)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the main UI layout."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        
        main_layout = QtWidgets.QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter: left (canvas + table) | right (processing)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal if hasattr(QtCore.Qt, 'Orientation') else QtCore.Qt.Horizontal)
        
        # Left side: canvas on top, table on bottom
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical if hasattr(QtCore.Qt, 'Orientation') else QtCore.Qt.Vertical)
        
        # Canvas
        self.canvas = WizardCanvas()
        self.left_splitter.addWidget(self.canvas)
        
        # Table
        self.table = WizardTable()
        self.left_splitter.addWidget(self.table)
        
        self.left_splitter.setSizes([400, 300])
        left_layout.addWidget(self.left_splitter)
        
        self.main_splitter.addWidget(left_widget)
        
        # Right side: processing panel
        self.processing = ProcessingPanel()
        self.processing.setMaximumWidth(300)
        self.main_splitter.addWidget(self.processing)
        
        self.main_splitter.setSizes([900, 300])
        
        main_layout.addWidget(self.main_splitter)
        
        # Status bar
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self._update_status()
    
    def _setup_menu(self):
        """Setup menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QtGui.QAction("&Open...", self)
        open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open if hasattr(QtGui.QKeySequence, 'StandardKey') else QtGui.QKeySequence.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        export_action = QtGui.QAction("&Export...", self)
        export_action.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self._show_export_dialog)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        close_action = QtGui.QAction("&Close", self)
        close_action.setShortcut(QtGui.QKeySequence.StandardKey.Close if hasattr(QtGui.QKeySequence, 'StandardKey') else QtGui.QKeySequence.Close)
        close_action.triggered.connect(self.close)
        file_menu.addAction(close_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        self.undo_action = QtGui.QAction("&Undo", self)
        self.undo_action.setShortcut(QtGui.QKeySequence.StandardKey.Undo if hasattr(QtGui.QKeySequence, 'StandardKey') else QtGui.QKeySequence.Undo)
        self.undo_action.triggered.connect(self._undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = QtGui.QAction("&Redo", self)
        self.redo_action.setShortcut(QtGui.QKeySequence.StandardKey.Redo if hasattr(QtGui.QKeySequence, 'StandardKey') else QtGui.QKeySequence.Redo)
        self.redo_action.triggered.connect(self._redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)
    
    def _setup_toolbar(self):
        """Setup toolbar."""
        toolbar = QtWidgets.QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        open_action = QtGui.QAction("Open", self)
        open_action.triggered.connect(self._open_file)
        toolbar.addAction(open_action)
        
        export_action = QtGui.QAction("Export", self)
        export_action.triggered.connect(self._show_export_dialog)
        toolbar.addAction(export_action)
        
        toolbar.addSeparator()
        
        undo_action = QtGui.QAction("Undo", self)
        undo_action.triggered.connect(self._undo)
        toolbar.addAction(undo_action)
        
        redo_action = QtGui.QAction("Redo", self)
        redo_action.triggered.connect(self._redo)
        toolbar.addAction(redo_action)
    
    def _connect_signals(self):
        """Connect widget signals."""
        # Canvas-table synchronization
        self.canvas.point_clicked.connect(self.table.select_row)
        self.table.selection_changed.connect(self.canvas.select_point)
        
        # Data change propagation
        self.table.data_changed.connect(self._on_data_changed)
        self.processing.data_changed.connect(self._on_data_changed)
    
    def _on_data_changed(self):
        """Handle data changes - save state for undo and refresh views."""
        self._save_undo_state()
        self._refresh_views()
        self._update_status()
    
    def _refresh_views(self):
        """Refresh all views with current model data."""
        if self._model is None:
            return
        self.canvas.update_plot()
        self.table.refresh_table()
    
    def _update_status(self):
        """Update status bar."""
        if self._model is None:
            self.status_bar.showMessage("No data loaded")
        else:
            msg = f"Points: {self._model.n_points}"
            if self._model.n_points > 0:
                msg += f" | Freq: {self._model.frequency.min():.2f} - {self._model.frequency.max():.2f} Hz"
            self.status_bar.showMessage(msg)
    
    def _save_undo_state(self):
        """Save current state to undo stack."""
        if self._model is not None:
            self._undo_stack.append(self._model.to_dict())
            self._redo_stack.clear()
            # Limit undo stack size
            if len(self._undo_stack) > 50:
                self._undo_stack.pop(0)
        self._update_undo_actions()
    
    def _update_undo_actions(self):
        """Update undo/redo action enabled states."""
        self.undo_action.setEnabled(len(self._undo_stack) > 0)
        self.redo_action.setEnabled(len(self._redo_stack) > 0)
    
    def _undo(self):
        """Undo last action."""
        if not self._undo_stack:
            return
        
        # Save current state to redo
        if self._model is not None:
            self._redo_stack.append(self._model.to_dict())
        
        # Restore previous state
        state = self._undo_stack.pop()
        self._model = CurveDataModel.from_dict(state)
        self._set_model(self._model)
        self._update_undo_actions()
    
    def _redo(self):
        """Redo last undone action."""
        if not self._redo_stack:
            return
        
        # Save current state to undo
        if self._model is not None:
            self._undo_stack.append(self._model.to_dict())
        
        # Restore redo state
        state = self._redo_stack.pop()
        self._model = CurveDataModel.from_dict(state)
        self._set_model(self._model)
        self._update_undo_actions()
    
    def _open_file(self):
        """Open a curve data file."""
        # Use suggested file path as starting point for browse dialog
        start_dir = ""
        if self._suggested_file:
            start_dir = str(Path(self._suggested_file).parent)
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Curve Data",
            start_dir,
            "Text Files (*.txt *.csv);;All Files (*)"
        )
        
        if path:
            self.load_file(path)
    
    def set_suggested_file(self, file_path: str):
        """Set a suggested file path for the browse dialog (does not auto-load)."""
        self._suggested_file = file_path
    
    def prompt_for_file(self):
        """Show file open dialog on startup if no data loaded."""
        if self._model is None or self._model.n_points == 0:
            self._open_file()
    
    def load_file(self, path: str):
        """Load curve data from a file."""
        try:
            self._model = CurveDataModel.from_file(path)
            self._set_model(self._model)
            self.setWindowTitle(f"Export Wizard - {Path(path).name}")
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._update_undo_actions()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load Error", f"Failed to load file:\n{str(e)}")
    
    def load_from_arrays(self, frequency, velocity, wavelength=None, 
                         uncertainty=None, name: str = "Curve"):
        """
        Load curve data from numpy arrays.
        
        This is used when launching from DC Cut to pass the average curve data.
        """
        self._model = CurveDataModel.from_arrays(
            frequency, velocity, wavelength, uncertainty, name
        )
        self._set_model(self._model)
        self.setWindowTitle(f"Export Wizard - {name}")
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._update_undo_actions()
    
    def _set_model(self, model: CurveDataModel):
        """Set model on all widgets."""
        self._model = model
        self.canvas.set_model(model)
        self.table.set_model(model)
        self.processing.set_model(model)
        self._update_status()
    
    def _show_export_dialog(self):
        """Show the export configuration dialog."""
        if self._model is None or self._model.n_points == 0:
            QtWidgets.QMessageBox.warning(self, "Export", "No data to export.")
            return
        
        dialog = ExportDialog(self._model, self)
        dialog.exec()


def launch_wizard(file_path: Optional[str] = None):
    """
    Launch the Export Wizard as a standalone application.
    
    Args:
        file_path: Optional path to a curve data file to load
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    
    window = ExportWizardWindow()
    
    if file_path:
        window.load_file(file_path)
    
    window.show()
    
    # Only start event loop if we created the app
    if not QtWidgets.QApplication.instance():
        sys.exit(app.exec())
    
    return window


if __name__ == "__main__":
    # Standalone launch
    file_arg = sys.argv[1] if len(sys.argv) > 1 else None
    launch_wizard(file_arg)
