"""
Dialogs for Target Builder
==========================

Dialog windows for adding curves and other interactions.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QPushButton, QFileDialog, QLabel, QGroupBox,
    QMessageBox
)
from PySide6.QtCore import Qt
from pathlib import Path
from typing import Optional
import os

from .curve_tree import CurveType, CurveData


class AddCurveDialog(QDialog):
    """Dialog for adding a new curve."""
    
    def __init__(self, curve_type: CurveType, parent=None):
        super().__init__(parent)
        self.curve_type = curve_type
        self._curve_data: Optional[CurveData] = None
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle(f"Add {self._get_title()}")
        self.setMinimumWidth(450)
        
        layout = QVBoxLayout(self)
        
        if self.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.HV_CURVE):
            self._setup_file_ui(layout)
        elif self.curve_type == CurveType.HV_PEAK:
            self._setup_peak_ui(layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.add_btn = QPushButton("Add Curve")
        self.add_btn.clicked.connect(self._on_add)
        self.add_btn.setDefault(True)
        btn_layout.addWidget(self.add_btn)
        
        layout.addLayout(btn_layout)
    
    def _get_title(self) -> str:
        titles = {
            CurveType.RAYLEIGH: "Rayleigh Curve",
            CurveType.LOVE: "Love Curve",
            CurveType.HV_CURVE: "HV Curve",
            CurveType.HV_PEAK: "HV Peak",
        }
        return titles.get(self.curve_type, "Curve")
    
    def _setup_file_ui(self, layout: QVBoxLayout):
        """Setup UI for file-based curves (Rayleigh, Love, HV Curve)."""
        form = QFormLayout()
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a file...")
        self.file_edit.textChanged.connect(self._on_file_changed)
        file_layout.addWidget(self.file_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)
        
        form.addRow("File:", file_layout)
        
        # Mode (for dispersion curves only)
        if self.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE):
            self.mode_spin = QSpinBox()
            self.mode_spin.setRange(0, 10)
            self.mode_spin.setValue(0)
            form.addRow("Mode:", self.mode_spin)
            
            # Custom name
            self.name_edit = QLineEdit()
            self.name_edit.setPlaceholderText("Auto-generated from filename")
            form.addRow("Name:", self.name_edit)
            
            # StdDev type
            self.stddev_combo = QComboBox()
            self.stddev_combo.addItems(["LogStd (Dinver 3.4.2)", "COV"])
            form.addRow("StdDev Type:", self.stddev_combo)
        
        layout.addLayout(form)
        
        # Info group (read-only, populated after file selection)
        info_group = QGroupBox("File Info")
        info_layout = QFormLayout(info_group)
        
        self.points_label = QLabel("-")
        info_layout.addRow("Points:", self.points_label)
        
        self.freq_label = QLabel("-")
        info_layout.addRow("Frequency Range:", self.freq_label)
        
        layout.addWidget(info_group)
    
    def _setup_peak_ui(self, layout: QVBoxLayout):
        """Setup UI for HV Peak."""
        form = QFormLayout()
        
        self.peak_freq_spin = QDoubleSpinBox()
        self.peak_freq_spin.setRange(0.1, 100.0)
        self.peak_freq_spin.setValue(5.0)
        self.peak_freq_spin.setSuffix(" Hz")
        self.peak_freq_spin.setDecimals(2)
        form.addRow("Peak Frequency:", self.peak_freq_spin)
        
        self.peak_stddev_spin = QDoubleSpinBox()
        self.peak_stddev_spin.setRange(0.01, 10.0)
        self.peak_stddev_spin.setValue(0.5)
        self.peak_stddev_spin.setDecimals(2)
        form.addRow("Standard Deviation:", self.peak_stddev_spin)
        
        layout.addLayout(form)
    
    def _browse_file(self):
        """Open file browser."""
        file_filter = "Text files (*.txt);;All files (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Curve File", "", file_filter
        )
        if filepath:
            self.file_edit.setText(filepath)
    
    def _on_file_changed(self, filepath: str):
        """Handle file path change - read and display file info."""
        if not filepath or not os.path.exists(filepath):
            self.points_label.setText("-")
            self.freq_label.setText("-")
            return
        
        try:
            # Try to read the file and get basic info
            if self.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE):
                from sw_dcml.dinver.target.target_new.models import DispersionCurve
                curve = DispersionCurve.from_file(
                    filepath,
                    polarization=self.curve_type.value,
                    stddev_type="logstd"
                )
                self.points_label.setText(str(curve.n_points))
                self.freq_label.setText(f"{curve.frequency.min():.2f} - {curve.frequency.max():.2f} Hz")
                
                # Auto-generate name from filename
                if not self.name_edit.text():
                    name = Path(filepath).stem
                    self.name_edit.setPlaceholderText(name)
                    
            elif self.curve_type == CurveType.HV_CURVE:
                from sw_dcml.dinver.target.target_new.models import HVCurve
                curve = HVCurve.from_file(filepath)
                self.points_label.setText(str(curve.n_points))
                self.freq_label.setText(f"{curve.frequency.min():.2f} - {curve.frequency.max():.2f} Hz")
                
        except Exception as e:
            self.points_label.setText("Error reading file")
            self.freq_label.setText(str(e)[:50])
    
    def _on_add(self):
        """Handle Add button click."""
        try:
            self._curve_data = self._create_curve_data()
            if self._curve_data:
                self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add curve: {e}")
    
    def _create_curve_data(self) -> Optional[CurveData]:
        """Create CurveData from dialog inputs."""
        if self.curve_type == CurveType.HV_PEAK:
            return CurveData(
                curve_type=CurveType.HV_PEAK,
                name="HV Peak",
                peak_freq=self.peak_freq_spin.value(),
                peak_stddev=self.peak_stddev_spin.value(),
                included=True
            )
        
        # File-based curves
        filepath = self.file_edit.text()
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "Error", "Please select a valid file.")
            return None
        
        if self.curve_type == CurveType.HV_CURVE:
            from sw_dcml.dinver.target.target_new.models import HVCurve
            curve = HVCurve.from_file(filepath)
            return CurveData(
                curve_type=CurveType.HV_CURVE,
                filepath=filepath,
                name="HV Curve",
                n_points=curve.n_points,
                freq_min=float(curve.frequency.min()),
                freq_max=float(curve.frequency.max()),
                included=True
            )
        
        # Dispersion curves
        from sw_dcml.dinver.target.target_new.models import DispersionCurve
        stddev_type = "logstd" if self.stddev_combo.currentIndex() == 0 else "cov"
        
        curve = DispersionCurve.from_file(
            filepath,
            polarization=self.curve_type.value,
            mode=self.mode_spin.value(),
            stddev_type=stddev_type
        )
        
        name = self.name_edit.text() or Path(filepath).stem
        
        return CurveData(
            curve_type=self.curve_type,
            filepath=filepath,
            name=name,
            mode=self.mode_spin.value(),
            stddev_type=stddev_type,
            n_points=curve.n_points,
            freq_min=float(curve.frequency.min()),
            freq_max=float(curve.frequency.max()),
            included=True
        )
    
    def get_curve_data(self) -> Optional[CurveData]:
        """Get the created curve data."""
        return self._curve_data
