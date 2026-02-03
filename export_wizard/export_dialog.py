"""
Export Dialog
=============

Dialog for configuring export options and saving files.
"""

from typing import Optional, List
from pathlib import Path
import numpy as np

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore

from .data_model import CurveDataModel


class ExportDialog(QtWidgets.QDialog):
    """Dialog for configuring and executing export."""
    
    def __init__(self, model: CurveDataModel, parent=None):
        super().__init__(parent)
        self._model = model
        self.setWindowTitle("Export Curve Data")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self._setup_ui()
        self._update_preview()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Output file
        file_group = QtWidgets.QGroupBox("Output File")
        file_layout = QtWidgets.QHBoxLayout(file_group)
        
        self.file_edit = QtWidgets.QLineEdit()
        self.file_edit.setPlaceholderText("Select output file...")
        file_layout.addWidget(self.file_edit)
        
        self.browse_btn = QtWidgets.QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        
        layout.addWidget(file_group)
        
        # Format options
        format_group = QtWidgets.QGroupBox("Format Options")
        format_layout = QtWidgets.QFormLayout(format_group)
        
        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(["TXT (Dinver)", "CSV", "TXT (Simple)"])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addRow("Format:", self.format_combo)
        
        self.header_cb = QtWidgets.QCheckBox("Include header row")
        self.header_cb.setChecked(True)
        self.header_cb.toggled.connect(self._update_preview)
        format_layout.addRow("", self.header_cb)
        
        self.delimiter_combo = QtWidgets.QComboBox()
        self.delimiter_combo.addItems(["Tab", "Space", "Comma", "Semicolon"])
        self.delimiter_combo.currentIndexChanged.connect(self._update_preview)
        format_layout.addRow("Delimiter:", self.delimiter_combo)
        
        layout.addWidget(format_group)
        
        # Column selection
        columns_group = QtWidgets.QGroupBox("Columns to Export")
        columns_layout = QtWidgets.QVBoxLayout(columns_group)
        
        self.columns_list = QtWidgets.QListWidget()
        self.columns_list.setMaximumHeight(120)
        
        # Add available columns
        column_options = [
            ("frequency", "Frequency (Hz)"),
            ("velocity", "Velocity (m/s)"),
            ("wavelength", "Wavelength (m)"),
            ("slowness", "Slowness (s/km)"),
            ("uncertainty_velocity", "Uncertainty (m/s)"),
            ("uncertainty_cov", "COV"),
            ("uncertainty_logstd", "LogStd"),
        ]
        
        # Default selections based on format
        default_cols = {"frequency", "slowness", "uncertainty_logstd"}
        
        for name, display in column_options:
            item = QtWidgets.QListWidgetItem(display)
            item.setData(QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole, name)
            item.setFlags(item.flags() | (QtCore.Qt.ItemFlag.ItemIsUserCheckable if hasattr(QtCore.Qt, 'ItemFlag') else QtCore.Qt.ItemIsUserCheckable))
            item.setCheckState(QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') and name in default_cols else (QtCore.Qt.Checked if name in default_cols else QtCore.Qt.Unchecked))
            self.columns_list.addItem(item)
        
        self.columns_list.itemChanged.connect(self._update_preview)
        columns_layout.addWidget(self.columns_list)
        
        layout.addWidget(columns_group)
        
        # Preview
        preview_group = QtWidgets.QGroupBox("Preview (first 5 rows)")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        
        self.preview_text = QtWidgets.QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(120)
        self.preview_text.setFontFamily("Courier New")
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        self.export_btn = QtWidgets.QPushButton("Export")
        self.export_btn.clicked.connect(self._do_export)
        self.export_btn.setDefault(True)
        btn_layout.addWidget(self.export_btn)
        
        layout.addLayout(btn_layout)
        
        self._on_format_changed(0)
    
    def _browse_file(self):
        """Browse for output file."""
        format_idx = self.format_combo.currentIndex()
        
        if format_idx == 0:  # Dinver TXT
            filter_str = "Text Files (*.txt);;All Files (*)"
            default_ext = ".txt"
        elif format_idx == 1:  # CSV
            filter_str = "CSV Files (*.csv);;All Files (*)"
            default_ext = ".csv"
        else:
            filter_str = "Text Files (*.txt);;All Files (*)"
            default_ext = ".txt"
        
        default_name = self._model.name if self._model.name else "curve"
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Curve Data", default_name + default_ext, filter_str
        )
        
        if path:
            self.file_edit.setText(path)
    
    def _on_format_changed(self, index: int):
        """Handle format selection change."""
        if index == 0:  # Dinver
            self.delimiter_combo.setCurrentIndex(0)  # Tab
            self.delimiter_combo.setEnabled(False)
            # Set default Dinver columns
            self._set_columns_checked(["frequency", "slowness", "uncertainty_logstd"])
        elif index == 1:  # CSV
            self.delimiter_combo.setCurrentIndex(2)  # Comma
            self.delimiter_combo.setEnabled(True)
        else:
            self.delimiter_combo.setCurrentIndex(0)  # Tab
            self.delimiter_combo.setEnabled(True)
        
        self._update_preview()
    
    def _set_columns_checked(self, column_names: List[str]):
        """Set which columns are checked."""
        for i in range(self.columns_list.count()):
            item = self.columns_list.item(i)
            name = item.data(QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole)
            checked = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
            unchecked = QtCore.Qt.CheckState.Unchecked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Unchecked
            item.setCheckState(checked if name in column_names else unchecked)
    
    def _get_selected_columns(self) -> List[str]:
        """Get list of selected column names."""
        columns = []
        for i in range(self.columns_list.count()):
            item = self.columns_list.item(i)
            checked = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
            if item.checkState() == checked:
                columns.append(item.data(QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole))
        return columns
    
    def _get_delimiter(self) -> str:
        """Get selected delimiter."""
        delimiters = ["\t", " ", ",", ";"]
        return delimiters[self.delimiter_combo.currentIndex()]
    
    def _update_preview(self):
        """Update the preview text."""
        if self._model is None or self._model.n_points == 0:
            self.preview_text.setText("No data to preview")
            return
        
        columns = self._get_selected_columns()
        if not columns:
            self.preview_text.setText("No columns selected")
            return
        
        delimiter = self._get_delimiter()
        lines = []
        
        # Header
        if self.header_cb.isChecked():
            headers = []
            for col in columns:
                for config in self._model.columns:
                    if config.name == col:
                        headers.append(config.display_name)
                        break
                else:
                    headers.append(col)
            lines.append(delimiter.join(headers))
        
        # Data rows (first 5)
        n_preview = min(5, self._model.n_points)
        for row in range(n_preview):
            values = []
            for col in columns:
                data = self._model.get_column_data(col)
                if row < len(data):
                    values.append(f"{data[row]:.6g}")
                else:
                    values.append("0")
            lines.append(delimiter.join(values))
        
        if self._model.n_points > 5:
            lines.append(f"... ({self._model.n_points - 5} more rows)")
        
        self.preview_text.setText("\n".join(lines))
    
    def _do_export(self):
        """Execute the export."""
        path = self.file_edit.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(self, "Export", "Please specify an output file.")
            return
        
        columns = self._get_selected_columns()
        if not columns:
            QtWidgets.QMessageBox.warning(self, "Export", "Please select at least one column.")
            return
        
        try:
            self._write_file(path, columns)
            QtWidgets.QMessageBox.information(self, "Export", f"Exported {self._model.n_points} points to:\n{path}")
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
    
    def _write_file(self, path: str, columns: List[str]):
        """Write the data to file."""
        delimiter = self._get_delimiter()
        
        with open(path, 'w') as f:
            # Header
            if self.header_cb.isChecked():
                headers = []
                for col in columns:
                    for config in self._model.columns:
                        if config.name == col:
                            headers.append(config.display_name)
                            break
                    else:
                        headers.append(col)
                f.write(delimiter.join(headers) + "\n")
            
            # Data
            for row in range(self._model.n_points):
                values = []
                for col in columns:
                    data = self._model.get_column_data(col)
                    if row < len(data):
                        # Dinver format uses specific precision
                        if self.format_combo.currentIndex() == 0:
                            if col == "frequency":
                                values.append(f"{data[row]:.8e}")
                            elif col == "slowness":
                                values.append(f"{data[row]:.8e}")
                            elif col == "uncertainty_logstd":
                                # Dinver uses low and high bounds (same for symmetric)
                                values.append(f"{data[row]:.8e}")
                                values.append(f"{data[row]:.8e}")
                        else:
                            values.append(f"{data[row]:.6g}")
                    else:
                        values.append("0")
                f.write(delimiter.join(values) + "\n")
