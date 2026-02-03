"""
HV Properties Widgets
=====================

Property panels for HV Curve and HV Peak.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QDoubleSpinBox, QPushButton,
    QLabel, QGroupBox, QFileDialog, QCheckBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal
from typing import Optional
import os

from .curve_tree import CurveData, CurveType
from .collapsible import CollapsibleSection


class HVCurvePropertiesWidget(QWidget):
    """Properties panel for HV Curve."""
    
    data_changed = Signal(str, CurveData)  # uid, updated data
    remove_requested = Signal(str)  # uid
    preview_requested = Signal(str)  # uid
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_uid: Optional[str] = None
        self._current_data: Optional[CurveData] = None
        self._updating = False
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        self.title_label = QLabel("HV Curve")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        
        # Basic Info Group
        basic_group = QGroupBox("File")
        basic_layout = QFormLayout(basic_group)
        
        # File
        file_layout = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        file_layout.addWidget(self.file_edit)
        
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        basic_layout.addRow("File:", file_layout)
        
        layout.addWidget(basic_group)
        
        # File Info Group (read-only)
        info_group = QGroupBox("File Info")
        info_layout = QFormLayout(info_group)
        
        self.points_label = QLabel("-")
        info_layout.addRow("Points:", self.points_label)
        
        self.freq_label = QLabel("-")
        info_layout.addRow("Frequency:", self.freq_label)
        
        layout.addWidget(info_group)
        
        # Standard Deviation Section
        self.stddev_section = CollapsibleSection("Standard Deviation", expanded=False)
        stddev_widget = QWidget()
        stddev_layout = QVBoxLayout(stddev_widget)
        stddev_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_group = QButtonGroup(self)
        
        self.file_radio = QRadioButton("Use from file")
        self.file_radio.setChecked(True)
        self.file_radio.toggled.connect(self._on_stddev_changed)
        self.btn_group.addButton(self.file_radio)
        stddev_layout.addWidget(self.file_radio)
        
        # Fixed StdDev
        fixed_layout = QHBoxLayout()
        self.fixed_radio = QRadioButton("Fixed StdDev:")
        self.fixed_radio.toggled.connect(self._on_stddev_changed)
        self.btn_group.addButton(self.fixed_radio)
        fixed_layout.addWidget(self.fixed_radio)
        
        self.fixed_spin = QDoubleSpinBox()
        self.fixed_spin.setRange(0.01, 10.0)
        self.fixed_spin.setValue(0.5)
        self.fixed_spin.setSingleStep(0.1)
        self.fixed_spin.setDecimals(2)
        self.fixed_spin.valueChanged.connect(self._on_stddev_changed)
        fixed_layout.addWidget(self.fixed_spin)
        fixed_layout.addStretch()
        stddev_layout.addLayout(fixed_layout)
        
        # Min StdDev
        min_layout = QHBoxLayout()
        self.min_cb = QCheckBox("Minimum StdDev:")
        self.min_cb.toggled.connect(self._on_stddev_changed)
        min_layout.addWidget(self.min_cb)
        
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(0.01, 5.0)
        self.min_spin.setValue(0.1)
        self.min_spin.setSingleStep(0.05)
        self.min_spin.setDecimals(2)
        self.min_spin.valueChanged.connect(self._on_stddev_changed)
        min_layout.addWidget(self.min_spin)
        min_layout.addStretch()
        stddev_layout.addLayout(min_layout)
        
        self.stddev_section.add_widget(stddev_widget)
        layout.addWidget(self.stddev_section)
        
        # Spacer
        layout.addStretch()
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Preview Data")
        self.preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self.preview_btn)
        
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)
    
    def set_curve(self, uid: str, data: CurveData):
        """Set the curve to display/edit."""
        self._updating = True
        self._current_uid = uid
        self._current_data = data
        
        # Update fields
        self.file_edit.setText(data.filepath or "")
        
        # Update info
        self.points_label.setText(str(data.n_points) if data.n_points else "-")
        if data.freq_min and data.freq_max:
            self.freq_label.setText(f"{data.freq_min:.2f} - {data.freq_max:.2f} Hz")
        else:
            self.freq_label.setText("-")
        
        # Load stddev settings
        if data.stddev_mode == "fixed_cov":
            self.fixed_radio.setChecked(True)
            self.fixed_spin.setValue(data.fixed_cov)
        else:
            self.file_radio.setChecked(True)
        
        self.min_cb.setChecked(data.use_min_cov)
        self.min_spin.setValue(data.min_cov)
        
        self._updating = False
    
    def _on_stddev_changed(self):
        """Handle stddev settings change."""
        if self._updating or not self._current_uid or not self._current_data:
            return
        
        # Save settings to CurveData
        if self.fixed_radio.isChecked():
            self._current_data.stddev_mode = "fixed_cov"
            self._current_data.fixed_cov = self.fixed_spin.value()
        else:
            self._current_data.stddev_mode = "file"
        
        self._current_data.use_min_cov = self.min_cb.isChecked()
        self._current_data.min_cov = self.min_spin.value()
        
        self.data_changed.emit(self._current_uid, self._current_data)
    
    def _browse_file(self):
        """Browse for a new file."""
        file_filter = "Text files (*.txt);;All files (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select HV Curve File", "", file_filter
        )
        if filepath:
            self._load_new_file(filepath)
    
    def _load_new_file(self, filepath: str):
        """Load a new file and update the curve data."""
        if not self._current_data or not self._current_uid:
            return
            
        try:
            from sw_dcml.dinver.target.target_new.models import HVCurve
            
            curve = HVCurve.from_file(filepath)
            
            self._current_data.filepath = filepath
            self._current_data.n_points = curve.n_points
            self._current_data.freq_min = float(curve.frequency.min())
            self._current_data.freq_max = float(curve.frequency.max())
            
            self.file_edit.setText(filepath)
            self.points_label.setText(str(curve.n_points))
            self.freq_label.setText(f"{curve.frequency.min():.2f} - {curve.frequency.max():.2f} Hz")
            
            self.data_changed.emit(self._current_uid, self._current_data)
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", f"Failed to load file: {e}")
    
    def _on_preview(self):
        """Request data preview."""
        if self._current_uid:
            self.preview_requested.emit(self._current_uid)
    
    def _on_remove(self):
        """Request curve removal."""
        if self._current_uid:
            self.remove_requested.emit(self._current_uid)


class HVPeakPropertiesWidget(QWidget):
    """Properties panel for HV Peak."""
    
    data_changed = Signal(str, CurveData)  # uid, updated data
    remove_requested = Signal(str)  # uid
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_uid: Optional[str] = None
        self._current_data: Optional[CurveData] = None
        self._updating = False
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        self.title_label = QLabel("HV Peak")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        
        # Peak Settings Group
        settings_group = QGroupBox("Peak Settings")
        settings_layout = QFormLayout(settings_group)
        
        # Peak Frequency
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.1, 100.0)
        self.freq_spin.setValue(5.0)
        self.freq_spin.setSuffix(" Hz")
        self.freq_spin.setDecimals(2)
        self.freq_spin.valueChanged.connect(self._on_data_changed)
        settings_layout.addRow("Peak Frequency:", self.freq_spin)
        
        # StdDev
        self.stddev_spin = QDoubleSpinBox()
        self.stddev_spin.setRange(0.01, 10.0)
        self.stddev_spin.setValue(0.5)
        self.stddev_spin.setDecimals(2)
        self.stddev_spin.valueChanged.connect(self._on_data_changed)
        settings_layout.addRow("Standard Dev:", self.stddev_spin)
        
        layout.addWidget(settings_group)
        
        # Spacer
        layout.addStretch()
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self.remove_btn)
        
        layout.addLayout(btn_layout)
    
    def set_curve(self, uid: str, data: CurveData):
        """Set the peak to display/edit."""
        self._updating = True
        self._current_uid = uid
        self._current_data = data
        
        # Update fields
        if data.peak_freq is not None:
            self.freq_spin.setValue(data.peak_freq)
        self.stddev_spin.setValue(data.peak_stddev)
        
        self._updating = False
    
    def _on_data_changed(self):
        """Handle data changes."""
        if self._updating or not self._current_data or not self._current_uid:
            return
        
        self._current_data.peak_freq = self.freq_spin.value()
        self._current_data.peak_stddev = self.stddev_spin.value()
        
        self.data_changed.emit(self._current_uid, self._current_data)
    
    def _on_remove(self):
        """Request removal."""
        if self._current_uid:
            self.remove_requested.emit(self._current_uid)
