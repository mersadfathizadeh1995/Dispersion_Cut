"""
Averaging Dialog
================

Dialog for averaging multiple dispersion curves using Geopsy-compatible algorithm.

Algorithm (Geopsy-compatible):
1. Collect union of all frequencies from input curves
2. For each frequency, interpolate slowness from curves that span it
3. Average the interpolated slowness values
4. Set stddev = base_stddev * sqrt(N) where N is number of contributing curves
5. Set weight = N
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QGroupBox, QComboBox, QDoubleSpinBox, QCheckBox,
    QDialogButtonBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from typing import List, Optional
import numpy as np

from .curve_tree import CurveData, CurveType


class AveragingDialog(QDialog):
    """Dialog for averaging multiple dispersion curves using Geopsy-compatible algorithm."""
    
    curves_averaged = Signal(object)  # Emits the averaged CurveData
    
    def __init__(self, curves: List[CurveData], parent=None):
        super().__init__(parent)
        self._curves = [c for c in curves if c.curve_type in 
                       (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED)]
        self._setup_ui()
        self._populate_curves()
        
    def _setup_ui(self):
        self.setWindowTitle("Average Dispersion Curves (Geopsy-compatible)")
        self.setMinimumSize(500, 450)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Select curves to average. Uses Geopsy-compatible averaging:\n"
            "- Union of all frequencies (with interpolation)\n"
            "- Combined stddev = base_stddev * sqrt(N)"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Curve selection
        select_group = QGroupBox("Select Curves to Average")
        select_layout = QVBoxLayout(select_group)
        
        self.curve_list = QListWidget()
        self.curve_list.setSelectionMode(QListWidget.MultiSelection)
        select_layout.addWidget(self.curve_list)
        
        # Select all / none buttons
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self._select_none)
        btn_layout.addWidget(select_none_btn)
        btn_layout.addStretch()
        select_layout.addLayout(btn_layout)
        
        layout.addWidget(select_group)
        
        # Options
        options_group = QGroupBox("Averaging Options")
        options_layout = QFormLayout(options_group)
        
        # Output name
        self.name_edit = QComboBox()
        self.name_edit.setEditable(True)
        self.name_edit.addItems(["average", "Averaged_Rayleigh", "Averaged_Love"])
        options_layout.addRow("Output Name:", self.name_edit)
        
        # Base stddev
        self.stddev_spin = QDoubleSpinBox()
        self.stddev_spin.setRange(1.01, 2.0)
        self.stddev_spin.setValue(1.08)
        self.stddev_spin.setDecimals(2)
        self.stddev_spin.setSingleStep(0.01)
        self.stddev_spin.setToolTip("Log-normalized stddev (1.08 = ~8% uncertainty)")
        options_layout.addRow("Base StdDev:", self.stddev_spin)
        
        layout.addWidget(options_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _populate_curves(self):
        """Populate the curve list."""
        for curve in self._curves:
            item = QListWidgetItem(f"{curve.name} (M{curve.mode})")
            item.setData(Qt.UserRole, curve.uid)
            self.curve_list.addItem(item)
    
    def _select_all(self):
        for i in range(self.curve_list.count()):
            self.curve_list.item(i).setSelected(True)
    
    def _select_none(self):
        for i in range(self.curve_list.count()):
            self.curve_list.item(i).setSelected(False)
    
    def _get_selected_curves(self) -> List[CurveData]:
        """Get the selected curves."""
        selected = []
        for item in self.curve_list.selectedItems():
            uid = item.data(Qt.UserRole)
            for curve in self._curves:
                if curve.uid == uid:
                    selected.append(curve)
                    break
        return selected
    
    def _on_accept(self):
        """Handle OK button."""
        selected = self._get_selected_curves()
        
        if len(selected) < 2:
            QMessageBox.warning(
                self, "Error", 
                "Please select at least 2 curves to average."
            )
            return
        
        # Check same polarization and mode
        first = selected[0]
        for curve in selected[1:]:
            if curve.curve_type != first.curve_type:
                QMessageBox.warning(
                    self, "Error",
                    "All curves must have the same polarization (Rayleigh/Love)."
                )
                return
            if curve.mode != first.mode:
                QMessageBox.warning(
                    self, "Error",
                    "All curves must have the same mode number."
                )
                return
        
        try:
            averaged = self._perform_averaging(selected)
            self.curves_averaged.emit(averaged)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Averaging failed:\n{e}")
    
    def _perform_averaging(self, curves: List[CurveData]) -> CurveData:
        """Perform Geopsy-compatible averaging."""
        from .curve_averaging import (
            load_curve_for_averaging,
            average_curves_geopsy,
            save_averaged_curve
        )
        import tempfile
        import os
        
        base_stddev = self.stddev_spin.value()
        
        # Load curves for averaging
        loaded_curves = []
        for curve_data in curves:
            filepath = curve_data.working_filepath or curve_data.filepath
            loaded = load_curve_for_averaging(
                filepath,
                stddev=base_stddev,
                name=curve_data.name
            )
            loaded_curves.append(loaded)
        
        # Perform Geopsy-compatible averaging
        averaged_points = average_curves_geopsy(loaded_curves, output_stddev=base_stddev)
        
        # Save to temp file
        temp_dir = tempfile.mkdtemp(prefix="averaged_curve_")
        output_name = self.name_edit.currentText()
        temp_file = os.path.join(temp_dir, f"{output_name}.txt")
        
        curve_names = [c.name for c in loaded_curves]
        save_averaged_curve(averaged_points, temp_file, curve_names)
        
        # Get frequency range
        freqs = [pt.frequency for pt in averaged_points]
        
        # Create CurveData for the averaged curve
        first = curves[0]
        averaged_data = CurveData(
            curve_type=CurveType.AVERAGED,
            filepath=temp_file,
            name=output_name,
            mode=first.mode,
            stddev_type="logstd",
            n_points=len(averaged_points),
            freq_min=min(freqs),
            freq_max=max(freqs)
        )
        
        return averaged_data
