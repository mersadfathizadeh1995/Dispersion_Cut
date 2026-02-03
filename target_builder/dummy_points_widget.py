"""
Dummy Points Widget
===================

Widget for adding dummy points to curves.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QDoubleSpinBox, QPushButton, QLabel, QCheckBox,
    QComboBox, QLineEdit, QGroupBox
)
from PySide6.QtCore import Signal
from dataclasses import dataclass
from typing import Optional


@dataclass
class DummyPointsSettings:
    """Dummy points settings."""
    enabled: bool = False
    mode: str = "extend"  # "extend", "custom"
    extend_low: Optional[float] = None
    extend_high: Optional[float] = None
    custom_freqs: str = ""
    custom_vels: str = ""


class DummyPointsWidget(QWidget):
    """Widget for dummy points options."""
    
    settings_changed = Signal()
    apply_requested = Signal()  # Emitted when Apply button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable checkbox
        self.enable_cb = QCheckBox("Enable Dummy Points")
        self.enable_cb.toggled.connect(self._on_enabled_changed)
        layout.addWidget(self.enable_cb)
        
        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Extend Range", "Custom Points"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_combo.setEnabled(False)
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Extend mode options
        self.extend_group = QGroupBox("Extend Range")
        extend_layout = QFormLayout(self.extend_group)
        
        self.extend_low_spin = QDoubleSpinBox()
        self.extend_low_spin.setRange(0.001, 100.0)
        self.extend_low_spin.setValue(0.5)
        self.extend_low_spin.setSuffix(" Hz")
        self.extend_low_spin.setDecimals(3)
        self.extend_low_spin.valueChanged.connect(self._emit_changed)
        extend_layout.addRow("Extend Low to:", self.extend_low_spin)
        
        self.extend_high_spin = QDoubleSpinBox()
        self.extend_high_spin.setRange(1.0, 500.0)
        self.extend_high_spin.setValue(100.0)
        self.extend_high_spin.setSuffix(" Hz")
        self.extend_high_spin.setDecimals(1)
        self.extend_high_spin.valueChanged.connect(self._emit_changed)
        extend_layout.addRow("Extend High to:", self.extend_high_spin)
        
        self.extend_group.setEnabled(False)
        layout.addWidget(self.extend_group)
        
        # Custom mode options
        self.custom_group = QGroupBox("Custom Points")
        custom_layout = QFormLayout(self.custom_group)
        
        self.custom_freqs_edit = QLineEdit()
        self.custom_freqs_edit.setPlaceholderText("e.g., 0.5, 1.0, 100.0")
        self.custom_freqs_edit.textChanged.connect(self._emit_changed)
        custom_layout.addRow("Frequencies (Hz):", self.custom_freqs_edit)
        
        self.custom_vels_edit = QLineEdit()
        self.custom_vels_edit.setPlaceholderText("e.g., 300, 280, 200")
        self.custom_vels_edit.textChanged.connect(self._emit_changed)
        custom_layout.addRow("Velocities (m/s):", self.custom_vels_edit)
        
        self.custom_group.setEnabled(False)
        self.custom_group.setVisible(False)
        layout.addWidget(self.custom_group)
        
        # Info label
        self.info_label = QLabel("Dummy points extend the curve with fixed uncertainty")
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.info_label)
        
        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Dummy Points")
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setEnabled(False)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_enabled_changed(self, checked: bool):
        self.mode_combo.setEnabled(checked)
        self.apply_btn.setEnabled(checked)
        self._update_mode_visibility()
        self._emit_changed()
    
    def _on_mode_changed(self, index: int):
        self._update_mode_visibility()
        self._emit_changed()
    
    def _update_mode_visibility(self):
        enabled = self.enable_cb.isChecked()
        is_extend = self.mode_combo.currentIndex() == 0
        
        self.extend_group.setEnabled(enabled and is_extend)
        self.extend_group.setVisible(is_extend)
        self.custom_group.setEnabled(enabled and not is_extend)
        self.custom_group.setVisible(not is_extend)
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def _on_apply(self):
        self.apply_requested.emit()
    
    def get_settings(self) -> DummyPointsSettings:
        """Get current settings."""
        mode = "extend" if self.mode_combo.currentIndex() == 0 else "custom"
        
        return DummyPointsSettings(
            enabled=self.enable_cb.isChecked(),
            mode=mode,
            extend_low=self.extend_low_spin.value() if mode == "extend" else None,
            extend_high=self.extend_high_spin.value() if mode == "extend" else None,
            custom_freqs=self.custom_freqs_edit.text() if mode == "custom" else "",
            custom_vels=self.custom_vels_edit.text() if mode == "custom" else ""
        )
    
    def set_settings(self, settings: DummyPointsSettings):
        """Set settings."""
        self.enable_cb.setChecked(settings.enabled)
        self.mode_combo.setCurrentIndex(0 if settings.mode == "extend" else 1)
        
        if settings.extend_low is not None:
            self.extend_low_spin.setValue(settings.extend_low)
        if settings.extend_high is not None:
            self.extend_high_spin.setValue(settings.extend_high)
        
        self.custom_freqs_edit.setText(settings.custom_freqs)
        self.custom_vels_edit.setText(settings.custom_vels)
        
        self.mode_combo.setEnabled(settings.enabled)
        self.apply_btn.setEnabled(settings.enabled)
        self._update_mode_visibility()
    
    def set_frequency_range(self, fmin: float, fmax: float):
        """Set default extend values based on curve frequency range."""
        self.extend_low_spin.setValue(fmin * 0.5)  # Extend to half the min
        self.extend_high_spin.setValue(fmax * 2.0)  # Extend to double the max
