"""
Summary Dialog
==============

Preview dialog shown before creating target file.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QGroupBox, QDialogButtonBox, QHeaderView
)
from PySide6.QtCore import Qt
from typing import List

from .curve_tree import CurveData, CurveType


class SummaryDialog(QDialog):
    """Dialog showing summary before target creation."""
    
    def __init__(self, curves: List[CurveData], output_path: str, 
                 weights: dict, parent=None):
        super().__init__(parent)
        self._curves = curves
        self._output_path = output_path
        self._weights = weights
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle("Target File Summary")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Output info
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        output_layout.addRow("File:", QLabel(self._output_path))
        layout.addWidget(output_group)
        
        # Curves table
        curves_group = QGroupBox("Included Curves")
        curves_layout = QVBoxLayout(curves_group)
        
        self.curves_table = QTableWidget()
        self.curves_table.setColumnCount(5)
        self.curves_table.setHorizontalHeaderLabels([
            "Type", "Name", "Mode", "Points", "Freq Range"
        ])
        self.curves_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.curves_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        self._populate_curves_table()
        curves_layout.addWidget(self.curves_table)
        layout.addWidget(curves_group)
        
        # Weights summary
        weights_group = QGroupBox("Misfit Weights")
        weights_layout = QFormLayout(weights_group)
        weights_layout.addRow("Dispersion:", QLabel(f"{self._weights.get('dispersion', 1.0):.2f}"))
        weights_layout.addRow("HV Curve:", QLabel(f"{self._weights.get('hv_curve', 0.1):.2f}"))
        weights_layout.addRow("HV Peak:", QLabel(f"{self._weights.get('hv_peak', 0.05):.2f}"))
        layout.addWidget(weights_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)
        
        dispersion_count = sum(1 for c in self._curves if c.curve_type in 
                              (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED))
        hv_curve_count = sum(1 for c in self._curves if c.curve_type == CurveType.HV_CURVE)
        hv_peak_count = sum(1 for c in self._curves if c.curve_type == CurveType.HV_PEAK)
        total_points = sum(c.n_points for c in self._curves if c.n_points)
        
        stats_layout.addRow("Dispersion Curves:", QLabel(str(dispersion_count)))
        stats_layout.addRow("HV Curves:", QLabel(str(hv_curve_count)))
        stats_layout.addRow("HV Peaks:", QLabel(str(hv_peak_count)))
        stats_layout.addRow("Total Points:", QLabel(str(total_points)))
        layout.addWidget(stats_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.button(QDialogButtonBox.Ok).setText("Create Target")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _populate_curves_table(self):
        """Populate the curves table."""
        self.curves_table.setRowCount(len(self._curves))
        
        for row, curve in enumerate(self._curves):
            # Type
            type_name = curve.curve_type.value.replace("_", " ").title()
            self.curves_table.setItem(row, 0, QTableWidgetItem(type_name))
            
            # Name
            self.curves_table.setItem(row, 1, QTableWidgetItem(curve.name))
            
            # Mode
            if curve.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
                self.curves_table.setItem(row, 2, QTableWidgetItem(str(curve.mode)))
            else:
                self.curves_table.setItem(row, 2, QTableWidgetItem("-"))
            
            # Points
            self.curves_table.setItem(row, 3, QTableWidgetItem(
                str(curve.n_points) if curve.n_points else "-"
            ))
            
            # Freq Range
            if curve.freq_min and curve.freq_max:
                freq_range = f"{curve.freq_min:.1f} - {curve.freq_max:.1f} Hz"
            elif curve.curve_type == CurveType.HV_PEAK:
                freq_range = f"{curve.peak_freq:.1f} Hz" if curve.peak_freq else "-"
            else:
                freq_range = "-"
            self.curves_table.setItem(row, 4, QTableWidgetItem(freq_range))
