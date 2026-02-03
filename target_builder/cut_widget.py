"""
Cut/Trim Widget
===============

Widget for cutting/trimming curves to a specific frequency range.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QPushButton, QLabel, QCheckBox
)
from PySide6.QtCore import Signal
from dataclasses import dataclass
from typing import Optional


@dataclass
class CutSettings:
    """Cut/trim settings."""
    enabled: bool = False
    freq_min: Optional[float] = None
    freq_max: Optional[float] = None


class CutWidget(QWidget):
    """Widget for cut/trim frequency range options."""
    
    settings_changed = Signal()
    apply_requested = Signal()  # Emitted when Apply button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable checkbox
        self.enable_cb = QCheckBox("Enable Cut/Trim")
        self.enable_cb.toggled.connect(self._on_enabled_changed)
        layout.addWidget(self.enable_cb)
        
        # Frequency range
        range_layout = QHBoxLayout()
        
        range_layout.addWidget(QLabel("From:"))
        self.freq_min_spin = QDoubleSpinBox()
        self.freq_min_spin.setRange(0.01, 500.0)
        self.freq_min_spin.setValue(1.0)
        self.freq_min_spin.setSuffix(" Hz")
        self.freq_min_spin.setDecimals(2)
        self.freq_min_spin.valueChanged.connect(self._emit_changed)
        self.freq_min_spin.setEnabled(False)
        range_layout.addWidget(self.freq_min_spin)
        
        range_layout.addWidget(QLabel("To:"))
        self.freq_max_spin = QDoubleSpinBox()
        self.freq_max_spin.setRange(0.01, 500.0)
        self.freq_max_spin.setValue(50.0)
        self.freq_max_spin.setSuffix(" Hz")
        self.freq_max_spin.setDecimals(2)
        self.freq_max_spin.valueChanged.connect(self._emit_changed)
        self.freq_max_spin.setEnabled(False)
        range_layout.addWidget(self.freq_max_spin)
        
        range_layout.addStretch()
        layout.addLayout(range_layout)
        
        # Info label
        self.info_label = QLabel("Cut removes data points outside the specified range")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.info_label)
        
        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Cut")
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setEnabled(False)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_enabled_changed(self, checked: bool):
        self.freq_min_spin.setEnabled(checked)
        self.freq_max_spin.setEnabled(checked)
        self.apply_btn.setEnabled(checked)
        self._emit_changed()
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def _on_apply(self):
        self.apply_requested.emit()
    
    def get_settings(self) -> CutSettings:
        """Get current settings."""
        return CutSettings(
            enabled=self.enable_cb.isChecked(),
            freq_min=self.freq_min_spin.value() if self.enable_cb.isChecked() else None,
            freq_max=self.freq_max_spin.value() if self.enable_cb.isChecked() else None
        )
    
    def set_settings(self, settings: CutSettings):
        """Set settings."""
        self.enable_cb.setChecked(settings.enabled)
        if settings.freq_min is not None:
            self.freq_min_spin.setValue(settings.freq_min)
        if settings.freq_max is not None:
            self.freq_max_spin.setValue(settings.freq_max)
        
        self.freq_min_spin.setEnabled(settings.enabled)
        self.freq_max_spin.setEnabled(settings.enabled)
        self.apply_btn.setEnabled(settings.enabled)
    
    def set_frequency_range(self, fmin: float, fmax: float):
        """Set the frequency range from curve data."""
        self.freq_min_spin.setValue(fmin)
        self.freq_max_spin.setValue(fmax)
