"""Dialog for appending additional data to an existing session."""
from __future__ import annotations

import os
from typing import Optional, Dict, Any

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui


class AppendDataDialog(QtWidgets.QDialog):
    """Dialog for selecting a file to append to the current session."""
    
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Append Data")
        self.setMinimumWidth(500)
        self.result: Optional[Dict[str, Any]] = None
        self._mapping: Optional[Dict[str, int]] = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # File selection
        file_group = QtWidgets.QGroupBox("Data File")
        file_layout = QtWidgets.QGridLayout(file_group)
        
        file_layout.addWidget(QtWidgets.QLabel("File:"), 0, 0)
        self.file_edit = QtWidgets.QLineEdit()
        self.file_edit.setPlaceholderText("Select a .mat or .csv file...")
        file_layout.addWidget(self.file_edit, 0, 1)
        
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn, 0, 2)
        
        # Map button for column mapping
        self.map_btn = QtWidgets.QPushButton("Map Columns...")
        self.map_btn.clicked.connect(self._map_columns)
        self.map_btn.setEnabled(False)
        file_layout.addWidget(self.map_btn, 0, 3)
        
        layout.addWidget(file_group)
        
        # Label for the source
        label_group = QtWidgets.QGroupBox("Source Label")
        label_layout = QtWidgets.QHBoxLayout(label_group)
        
        label_layout.addWidget(QtWidgets.QLabel("Branch name:"))
        self.label_edit = QtWidgets.QLineEdit()
        self.label_edit.setPlaceholderText("Enter a name for this data source...")
        label_layout.addWidget(self.label_edit)
        
        layout.addWidget(label_group)
        
        # Velocity filter
        filter_group = QtWidgets.QGroupBox("Velocity Filter")
        filter_layout = QtWidgets.QHBoxLayout(filter_group)
        
        filter_layout.addWidget(QtWidgets.QLabel("Min:"))
        self.vmin_spin = QtWidgets.QSpinBox()
        self.vmin_spin.setRange(0, 10000)
        self.vmin_spin.setValue(0)
        self.vmin_spin.setSuffix(" m/s")
        filter_layout.addWidget(self.vmin_spin)
        
        filter_layout.addWidget(QtWidgets.QLabel("Max:"))
        self.vmax_spin = QtWidgets.QSpinBox()
        self.vmax_spin.setRange(0, 10000)
        self.vmax_spin.setValue(5000)
        self.vmax_spin.setSuffix(" m/s")
        filter_layout.addWidget(self.vmax_spin)
        
        layout.addWidget(filter_group)
        
        # Info label
        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.ok_btn = QtWidgets.QPushButton("Append")
        self.ok_btn.clicked.connect(self._on_accept)
        self.ok_btn.setEnabled(False)
        btn_layout.addWidget(self.ok_btn)
        
        layout.addLayout(btn_layout)
        
        # Connect file edit to update UI
        self.file_edit.textChanged.connect(self._on_file_changed)
    
    def _browse_file(self):
        """Browse for a data file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Data File", "",
            "Data Files (*.mat *.csv *.txt);;MATLAB Files (*.mat);;CSV Files (*.csv);;All Files (*.*)"
        )
        if path:
            self.file_edit.setText(path)
            # Auto-generate label from filename
            basename = os.path.splitext(os.path.basename(path))[0]
            if not self.label_edit.text():
                self.label_edit.setText(basename)
    
    def _on_file_changed(self, path: str):
        """Handle file path change."""
        valid = bool(path) and os.path.exists(path)
        self.ok_btn.setEnabled(valid)
        self.map_btn.setEnabled(valid)
        
        if valid:
            ext = os.path.splitext(path)[1].lower()
            if ext == '.mat':
                self.info_label.setText("MAT file detected. Auto-detection will be attempted for standard MASW format.")
            elif ext == '.csv':
                self.info_label.setText("CSV file detected. Auto-detection will be attempted for combined format.")
            else:
                self.info_label.setText("Use 'Map Columns...' to specify column mapping for this file.")
        else:
            self.info_label.setText("")
    
    def _map_columns(self):
        """Show column mapping dialog."""
        path = self.file_edit.text()
        if not path or not os.path.exists(path):
            return
        
        try:
            from dc_cut.gui.dialogs.open_data import UniversalColumnMapperDialog
            dlg = UniversalColumnMapperDialog(path, self)
            if dlg.exec() == 1:
                self._mapping = dlg.get_mapping()
                if self._mapping:
                    self.info_label.setText(f"Column mapping configured: {len(self._mapping)} columns mapped.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open column mapper:\n{e}")
    
    def _on_accept(self):
        """Handle accept button."""
        path = self.file_edit.text()
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Error", "Please select a valid file.")
            return
        
        label = self.label_edit.text().strip()
        if not label:
            label = os.path.splitext(os.path.basename(path))[0]
        
        self.result = {
            'path': path,
            'label': label,
            'mapping': self._mapping,
            'vmin': self.vmin_spin.value(),
            'vmax': self.vmax_spin.value(),
        }
        
        self.accept()
