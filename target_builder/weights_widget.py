"""
Weights Widget
==============

Widget for misfit weights with sliders.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSlider, QDoubleSpinBox, QLabel, QCheckBox, QGroupBox
)
from PySide6.QtCore import Signal, Qt
from dataclasses import dataclass


@dataclass
class WeightSettings:
    """Misfit weight settings."""
    dispersion: float = 1.0
    hv_curve: float = 0.1
    hv_peak: float = 0.05
    normalize: bool = False


class WeightSlider(QWidget):
    """Slider with spinbox for weight input."""
    
    value_changed = Signal(float)
    
    def __init__(self, label: str, initial: float = 1.0, parent=None):
        super().__init__(parent)
        self._updating = False
        self._setup_ui(label, initial)
        
    def _setup_ui(self, label: str, initial: float):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        self.label = QLabel(label)
        self.label.setMinimumWidth(80)
        layout.addWidget(self.label)
        
        # Slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(int(initial * 100))
        self.slider.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider, 1)
        
        # Spinbox
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.0, 1.0)
        self.spinbox.setSingleStep(0.05)
        self.spinbox.setDecimals(2)
        self.spinbox.setValue(initial)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.spinbox.setFixedWidth(70)
        layout.addWidget(self.spinbox)
    
    def _on_slider_changed(self, value: int):
        if self._updating:
            return
        self._updating = True
        float_val = value / 100.0
        self.spinbox.setValue(float_val)
        self.value_changed.emit(float_val)
        self._updating = False
    
    def _on_spinbox_changed(self, value: float):
        if self._updating:
            return
        self._updating = True
        self.slider.setValue(int(value * 100))
        self.value_changed.emit(value)
        self._updating = False
    
    def value(self) -> float:
        return self.spinbox.value()
    
    def set_value(self, value: float):
        self._updating = True
        self.spinbox.setValue(value)
        self.slider.setValue(int(value * 100))
        self._updating = False


class WeightsWidget(QWidget):
    """Widget for misfit weights configuration."""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title = QLabel("Misfit Weights")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)
        
        # Sliders
        self.dispersion_slider = WeightSlider("Dispersion:", 1.0)
        self.dispersion_slider.value_changed.connect(self._on_weight_changed)
        layout.addWidget(self.dispersion_slider)
        
        self.hv_curve_slider = WeightSlider("HV Curve:", 0.1)
        self.hv_curve_slider.value_changed.connect(self._on_weight_changed)
        layout.addWidget(self.hv_curve_slider)
        
        self.hv_peak_slider = WeightSlider("HV Peak:", 0.05)
        self.hv_peak_slider.value_changed.connect(self._on_weight_changed)
        layout.addWidget(self.hv_peak_slider)
        
        # Normalize checkbox
        self.normalize_cb = QCheckBox("Normalize weights (sum = 1.0)")
        self.normalize_cb.toggled.connect(self._on_normalize_changed)
        layout.addWidget(self.normalize_cb)
    
    def _on_weight_changed(self, value: float):
        if self.normalize_cb.isChecked():
            self._normalize_weights()
        self.settings_changed.emit()
    
    def _on_normalize_changed(self, checked: bool):
        if checked:
            self._normalize_weights()
        self.settings_changed.emit()
    
    def _normalize_weights(self):
        total = (self.dispersion_slider.value() + 
                 self.hv_curve_slider.value() + 
                 self.hv_peak_slider.value())
        
        if total > 0:
            self.dispersion_slider.set_value(self.dispersion_slider.value() / total)
            self.hv_curve_slider.set_value(self.hv_curve_slider.value() / total)
            self.hv_peak_slider.set_value(self.hv_peak_slider.value() / total)
    
    def get_settings(self) -> WeightSettings:
        """Get current weight settings."""
        return WeightSettings(
            dispersion=self.dispersion_slider.value(),
            hv_curve=self.hv_curve_slider.value(),
            hv_peak=self.hv_peak_slider.value(),
            normalize=self.normalize_cb.isChecked()
        )
    
    def set_settings(self, settings: WeightSettings):
        """Set weight settings."""
        self.dispersion_slider.set_value(settings.dispersion)
        self.hv_curve_slider.set_value(settings.hv_curve)
        self.hv_peak_slider.set_value(settings.hv_peak)
        self.normalize_cb.setChecked(settings.normalize)
