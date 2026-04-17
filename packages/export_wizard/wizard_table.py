"""
Wizard Table Widget
===================

Editable table for curve data manipulation.
"""

from typing import Optional, List
import numpy as np

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui
Signal = QtCore.Signal

from .data_model import CurveDataModel, ColumnConfig


class WizardTable(QtWidgets.QWidget):
    """
    Editable table widget for curve data.
    
    Features:
    - Dynamic columns (show/hide, add/remove)
    - Cell editing with automatic derived value updates
    - Row selection and deletion
    - Copy/paste support
    - Bulk value application
    """
    
    data_changed = Signal()
    selection_changed = Signal(int)  # Emits selected row index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[CurveDataModel] = None
        self._updating = False  # Prevent recursive updates
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        self.add_point_btn = QtWidgets.QPushButton("+ Add Point")
        self.add_point_btn.clicked.connect(self._on_add_point)
        toolbar.addWidget(self.add_point_btn)
        
        self.remove_point_btn = QtWidgets.QPushButton("- Remove Point")
        self.remove_point_btn.clicked.connect(self._on_remove_point)
        toolbar.addWidget(self.remove_point_btn)
        
        toolbar.addStretch()
        
        self.columns_btn = QtWidgets.QPushButton("Columns...")
        self.columns_btn.clicked.connect(self._show_columns_menu)
        toolbar.addWidget(self.columns_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows if hasattr(QtWidgets.QAbstractItemView, 'SelectionBehavior') else QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection if hasattr(QtWidgets.QAbstractItemView, 'SelectionMode') else QtWidgets.QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch if hasattr(QtWidgets.QHeaderView, 'ResizeMode') else QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(True)
        
        layout.addWidget(self.table)
    
    def _connect_signals(self):
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
    
    def set_model(self, model: CurveDataModel):
        """Set the curve data model."""
        self._model = model
        self.refresh_table()
    
    def refresh_table(self):
        """Rebuild the table from the model."""
        self._updating = True
        try:
            self.table.clear()
            
            if self._model is None:
                return
            
            # Get visible columns
            visible_cols = [c for c in self._model.columns if c.visible]
            
            # Setup headers
            self.table.setColumnCount(len(visible_cols))
            self.table.setRowCount(self._model.n_points)
            
            headers = []
            for col in visible_cols:
                header = col.display_name
                if col.unit:
                    header += f" ({col.unit})"
                headers.append(header)
            self.table.setHorizontalHeaderLabels(headers)
            
            # Populate data
            for row in range(self._model.n_points):
                for col_idx, col in enumerate(visible_cols):
                    data = self._model.get_column_data(col.name)
                    value = data[row] if row < len(data) else 0.0
                    
                    item = QtWidgets.QTableWidgetItem(col.format_value(value))
                    item.setData(QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole, col.name)
                    
                    if not col.editable:
                        item.setFlags(item.flags() & ~(QtCore.Qt.ItemFlag.ItemIsEditable if hasattr(QtCore.Qt, 'ItemFlag') else QtCore.Qt.ItemIsEditable))
                    
                    self.table.setItem(row, col_idx, item)
        finally:
            self._updating = False
    
    def _on_cell_changed(self, row: int, col: int):
        """Handle cell value change."""
        if self._updating or self._model is None:
            return
        
        item = self.table.item(row, col)
        if item is None:
            return
        
        col_name = item.data(QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole)
        if col_name is None:
            return
        
        try:
            value = float(item.text())
            self._model.set_value(row, col_name, value)
            self.refresh_table()
            self.data_changed.emit()
        except ValueError:
            # Revert to previous value
            self.refresh_table()
    
    def _on_selection_changed(self):
        """Handle row selection change."""
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.selection_changed.emit(rows[0].row())
    
    def _on_add_point(self):
        """Add a new point to the curve."""
        if self._model is None:
            return
        
        # Add at end with default values
        if self._model.n_points > 0:
            # Use values near the end of the curve
            f = self._model.frequency[-1] * 1.1
            v = self._model.velocity[-1]
        else:
            f = 10.0
            v = 200.0
        
        self._model.add_point(f, v)
        self.refresh_table()
        self.data_changed.emit()
    
    def _on_remove_point(self):
        """Remove selected point."""
        if self._model is None:
            return
        
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QtWidgets.QMessageBox.information(self, "Remove Point", "Please select a row to remove.")
            return
        
        row = rows[0].row()
        self._model.remove_point(row)
        self.refresh_table()
        self.data_changed.emit()
    
    def _show_columns_menu(self):
        """Show column visibility menu."""
        if self._model is None:
            return
        
        menu = QtWidgets.QMenu(self)
        
        for col in self._model.columns:
            action = QtGui.QAction(col.display_name, menu)
            action.setCheckable(True)
            action.setChecked(col.visible)
            action.setData(col.name)
            action.triggered.connect(lambda checked, c=col: self._toggle_column(c, checked))
            menu.addAction(action)
        
        menu.exec_(self.columns_btn.mapToGlobal(self.columns_btn.rect().bottomLeft()))
    
    def _toggle_column(self, col: ColumnConfig, visible: bool):
        """Toggle column visibility."""
        col.visible = visible
        self.refresh_table()
    
    def select_row(self, row: int):
        """Select a specific row."""
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)
    
    def apply_bulk_uncertainty(self, value: float, mode: str = "cov"):
        """
        Apply bulk uncertainty to all points.
        
        Args:
            value: Uncertainty value
            mode: 'cov', 'logstd', or 'velocity'
        """
        if self._model is None:
            return
        
        if mode == "cov":
            self._model.apply_fixed_cov(value)
        elif mode == "logstd":
            self._model.apply_fixed_logstd(value)
        elif mode == "velocity":
            self._model.uncertainty_velocity = np.full(self._model.n_points, value)
            self._model.uncertainty_cov = self._model.uncertainty_velocity / np.maximum(self._model.velocity, 1e-10)
            self._model.uncertainty_logstd = 1.0 + self._model.uncertainty_cov
        
        self.refresh_table()
        self.data_changed.emit()
