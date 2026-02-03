"""
Processing Panel
================

Panel with resampling and uncertainty controls.
"""

from typing import Optional

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
Signal = QtCore.Signal

from .data_model import CurveDataModel


class ResamplingPanel(QtWidgets.QGroupBox):
    """Panel for resampling options."""
    
    apply_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Resampling", parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QFormLayout(self)
        
        # Number of points
        self.n_points_spin = QtWidgets.QSpinBox()
        self.n_points_spin.setRange(10, 500)
        self.n_points_spin.setValue(50)
        layout.addRow("Points:", self.n_points_spin)
        
        # Method
        self.method_combo = QtWidgets.QComboBox()
        self.method_combo.addItems(["Logarithmic", "Linear"])
        layout.addRow("Method:", self.method_combo)
        
        # Frequency range
        freq_layout = QtWidgets.QHBoxLayout()
        
        self.fmin_spin = QtWidgets.QDoubleSpinBox()
        self.fmin_spin.setRange(0.01, 500.0)
        self.fmin_spin.setValue(1.0)
        self.fmin_spin.setDecimals(2)
        self.fmin_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.fmin_spin)
        
        freq_layout.addWidget(QtWidgets.QLabel("-"))
        
        self.fmax_spin = QtWidgets.QDoubleSpinBox()
        self.fmax_spin.setRange(0.01, 500.0)
        self.fmax_spin.setValue(100.0)
        self.fmax_spin.setDecimals(2)
        self.fmax_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.fmax_spin)
        
        layout.addRow("Freq Range:", freq_layout)
        
        # Auto range checkbox
        self.auto_range_cb = QtWidgets.QCheckBox("Use data range")
        self.auto_range_cb.setChecked(True)
        self.auto_range_cb.toggled.connect(self._on_auto_range_changed)
        layout.addRow("", self.auto_range_cb)
        
        self._on_auto_range_changed(True)
        
        # Apply button
        self.apply_btn = QtWidgets.QPushButton("Apply Resample")
        self.apply_btn.clicked.connect(self.apply_requested.emit)
        layout.addRow("", self.apply_btn)
    
    def _on_auto_range_changed(self, checked: bool):
        self.fmin_spin.setEnabled(not checked)
        self.fmax_spin.setEnabled(not checked)
    
    def get_settings(self) -> dict:
        """Get current resampling settings."""
        return {
            'n_points': self.n_points_spin.value(),
            'method': 'log' if self.method_combo.currentIndex() == 0 else 'linear',
            'fmin': None if self.auto_range_cb.isChecked() else self.fmin_spin.value(),
            'fmax': None if self.auto_range_cb.isChecked() else self.fmax_spin.value(),
        }
    
    def set_frequency_range(self, fmin: float, fmax: float):
        """Set frequency range from data."""
        self.fmin_spin.setValue(fmin)
        self.fmax_spin.setValue(fmax)


class UncertaintyPanel(QtWidgets.QGroupBox):
    """Panel for uncertainty settings."""
    
    apply_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Uncertainty", parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QFormLayout(self)
        
        # Mode selection
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["Fixed COV", "Fixed LogStd", "Fixed Velocity"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addRow("Mode:", self.mode_combo)
        
        # COV value
        self.cov_spin = QtWidgets.QDoubleSpinBox()
        self.cov_spin.setRange(0.001, 1.0)
        self.cov_spin.setValue(0.1)
        self.cov_spin.setDecimals(3)
        self.cov_spin.setSingleStep(0.01)
        layout.addRow("COV:", self.cov_spin)
        
        # LogStd value
        self.logstd_spin = QtWidgets.QDoubleSpinBox()
        self.logstd_spin.setRange(1.0, 2.0)
        self.logstd_spin.setValue(1.1)
        self.logstd_spin.setDecimals(3)
        self.logstd_spin.setSingleStep(0.01)
        layout.addRow("LogStd:", self.logstd_spin)
        
        # Velocity uncertainty
        self.vel_spin = QtWidgets.QDoubleSpinBox()
        self.vel_spin.setRange(0.1, 500.0)
        self.vel_spin.setValue(20.0)
        self.vel_spin.setDecimals(1)
        self.vel_spin.setSuffix(" m/s")
        layout.addRow("Uncert (m/s):", self.vel_spin)
        
        self._on_mode_changed(0)
        
        # Apply button
        self.apply_btn = QtWidgets.QPushButton("Apply Uncertainty")
        self.apply_btn.clicked.connect(self.apply_requested.emit)
        layout.addRow("", self.apply_btn)
    
    def _on_mode_changed(self, index: int):
        self.cov_spin.setEnabled(index == 0)
        self.logstd_spin.setEnabled(index == 1)
        self.vel_spin.setEnabled(index == 2)
    
    def get_settings(self) -> dict:
        """Get current uncertainty settings."""
        mode_idx = self.mode_combo.currentIndex()
        modes = ['cov', 'logstd', 'velocity']
        values = [self.cov_spin.value(), self.logstd_spin.value(), self.vel_spin.value()]
        return {
            'mode': modes[mode_idx],
            'value': values[mode_idx],
        }


class TrimPanel(QtWidgets.QGroupBox):
    """Panel for trimming curve to frequency range."""
    
    apply_requested = Signal()
    
    def __init__(self, parent=None):
        super().__init__("Trim Frequency Range", parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QFormLayout(self)
        
        # Frequency range
        freq_layout = QtWidgets.QHBoxLayout()
        
        self.fmin_spin = QtWidgets.QDoubleSpinBox()
        self.fmin_spin.setRange(0.01, 500.0)
        self.fmin_spin.setValue(1.0)
        self.fmin_spin.setDecimals(2)
        self.fmin_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.fmin_spin)
        
        freq_layout.addWidget(QtWidgets.QLabel("-"))
        
        self.fmax_spin = QtWidgets.QDoubleSpinBox()
        self.fmax_spin.setRange(0.01, 500.0)
        self.fmax_spin.setValue(100.0)
        self.fmax_spin.setDecimals(2)
        self.fmax_spin.setSuffix(" Hz")
        freq_layout.addWidget(self.fmax_spin)
        
        layout.addRow("Keep Range:", freq_layout)
        
        # Apply button
        self.apply_btn = QtWidgets.QPushButton("Apply Trim")
        self.apply_btn.clicked.connect(self.apply_requested.emit)
        layout.addRow("", self.apply_btn)
    
    def get_settings(self) -> dict:
        """Get current trim settings."""
        return {
            'fmin': self.fmin_spin.value(),
            'fmax': self.fmax_spin.value(),
        }
    
    def set_frequency_range(self, fmin: float, fmax: float):
        """Set frequency range from data."""
        self.fmin_spin.setValue(fmin)
        self.fmax_spin.setValue(fmax)


class ProcessingPanel(QtWidgets.QWidget):
    """Combined processing panel with all options."""
    
    data_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[CurveDataModel] = None
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.resample_panel = ResamplingPanel()
        layout.addWidget(self.resample_panel)
        
        self.uncertainty_panel = UncertaintyPanel()
        layout.addWidget(self.uncertainty_panel)
        
        self.trim_panel = TrimPanel()
        layout.addWidget(self.trim_panel)
        
        layout.addStretch()
    
    def _connect_signals(self):
        self.resample_panel.apply_requested.connect(self._apply_resample)
        self.uncertainty_panel.apply_requested.connect(self._apply_uncertainty)
        self.trim_panel.apply_requested.connect(self._apply_trim)
    
    def set_model(self, model: CurveDataModel):
        """Set the curve data model."""
        self._model = model
        self._update_from_model()
    
    def _update_from_model(self):
        """Update panel values from model."""
        if self._model is None or self._model.n_points == 0:
            return
        
        fmin = float(self._model.frequency.min())
        fmax = float(self._model.frequency.max())
        
        self.resample_panel.set_frequency_range(fmin, fmax)
        self.trim_panel.set_frequency_range(fmin, fmax)
    
    def _apply_resample(self):
        """Apply resampling to the curve."""
        if self._model is None:
            return
        
        settings = self.resample_panel.get_settings()
        self._model.resample(
            n_points=settings['n_points'],
            method=settings['method'],
            fmin=settings['fmin'],
            fmax=settings['fmax'],
        )
        self._update_from_model()
        self.data_changed.emit()
    
    def _apply_uncertainty(self):
        """Apply uncertainty settings to the curve."""
        if self._model is None:
            return
        
        settings = self.uncertainty_panel.get_settings()
        
        if settings['mode'] == 'cov':
            self._model.apply_fixed_cov(settings['value'])
        elif settings['mode'] == 'logstd':
            self._model.apply_fixed_logstd(settings['value'])
        else:  # velocity
            import numpy as np
            self._model.uncertainty_velocity = np.full(self._model.n_points, settings['value'])
            self._model.uncertainty_cov = self._model.uncertainty_velocity / np.maximum(self._model.velocity, 1e-10)
            self._model.uncertainty_logstd = 1.0 + self._model.uncertainty_cov
        
        self.data_changed.emit()
    
    def _apply_trim(self):
        """Apply frequency trim to the curve."""
        if self._model is None:
            return
        
        settings = self.trim_panel.get_settings()
        self._model.trim_frequency_range(settings['fmin'], settings['fmax'])
        self._update_from_model()
        self.data_changed.emit()
