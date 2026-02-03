"""
Processing Widgets
==================

Widgets for standard deviation, resampling, and dummy point options.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QRadioButton, QButtonGroup, QDoubleSpinBox, QSpinBox,
    QCheckBox, QComboBox, QLineEdit, QLabel, QGroupBox,
    QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Signal
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class FreqRangeStdDev:
    """Standard deviation for a specific frequency range."""
    freq_min: float = 1.0
    freq_max: float = 50.0
    mode: str = "fixed_cov"  # "fixed_logstd", "fixed_cov"
    value: float = 0.1


@dataclass
class StdDevSettings:
    """Standard deviation settings."""
    mode: str = "file"  # "file", "fixed_logstd", "fixed_cov"
    fixed_logstd: float = 1.1
    fixed_cov: float = 0.1
    use_min_cov: bool = False
    min_cov: float = 0.05
    # Multiple frequency ranges for applying custom stddev
    freq_ranges: Optional[List] = None  # List of FreqRangeStdDev


@dataclass
class ResamplingSettings:
    """Resampling settings."""
    enabled: bool = False
    method: str = "log"  # "log", "linear"
    npoints: int = 50
    fmin: Optional[float] = None
    fmax: Optional[float] = None


@dataclass
class DummyPointsSettings:
    """Dummy points settings."""
    enabled: bool = False
    mode: str = "extend"  # "extend", "custom"
    extend_low: Optional[float] = None
    extend_high: Optional[float] = None
    custom_freqs: str = ""
    custom_vels: str = ""


class StdDevWidget(QWidget):
    """Widget for standard deviation options."""
    
    settings_changed = Signal()
    apply_requested = Signal()  # Emitted when Apply button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Radio buttons for mode
        self.btn_group = QButtonGroup(self)
        
        self.file_radio = QRadioButton("Use from file")
        self.file_radio.setChecked(True)
        self.file_radio.toggled.connect(self._on_mode_changed)
        self.btn_group.addButton(self.file_radio)
        layout.addWidget(self.file_radio)
        
        # Fixed LogStd
        logstd_layout = QHBoxLayout()
        self.logstd_radio = QRadioButton("Fixed LogStd:")
        self.logstd_radio.toggled.connect(self._on_mode_changed)
        self.btn_group.addButton(self.logstd_radio)
        logstd_layout.addWidget(self.logstd_radio)
        
        self.logstd_spin = QDoubleSpinBox()
        self.logstd_spin.setRange(1.0, 2.0)
        self.logstd_spin.setValue(1.1)
        self.logstd_spin.setSingleStep(0.01)
        self.logstd_spin.setDecimals(2)
        self.logstd_spin.valueChanged.connect(self._emit_changed)
        logstd_layout.addWidget(self.logstd_spin)
        logstd_layout.addStretch()
        layout.addLayout(logstd_layout)
        
        # Fixed COV
        cov_layout = QHBoxLayout()
        self.cov_radio = QRadioButton("Fixed COV:")
        self.cov_radio.toggled.connect(self._on_mode_changed)
        self.btn_group.addButton(self.cov_radio)
        cov_layout.addWidget(self.cov_radio)
        
        self.cov_spin = QDoubleSpinBox()
        self.cov_spin.setRange(0.01, 1.0)
        self.cov_spin.setValue(0.1)
        self.cov_spin.setSingleStep(0.01)
        self.cov_spin.setDecimals(2)
        self.cov_spin.valueChanged.connect(self._emit_changed)
        cov_layout.addWidget(self.cov_spin)
        cov_layout.addStretch()
        layout.addLayout(cov_layout)
        
        # Min COV
        min_layout = QHBoxLayout()
        self.min_cov_cb = QCheckBox("Minimum COV:")
        self.min_cov_cb.toggled.connect(self._emit_changed)
        min_layout.addWidget(self.min_cov_cb)
        
        self.min_cov_spin = QDoubleSpinBox()
        self.min_cov_spin.setRange(0.01, 0.5)
        self.min_cov_spin.setValue(0.05)
        self.min_cov_spin.setSingleStep(0.01)
        self.min_cov_spin.setDecimals(2)
        self.min_cov_spin.valueChanged.connect(self._emit_changed)
        min_layout.addWidget(self.min_cov_spin)
        min_layout.addStretch()
        layout.addLayout(min_layout)
        
        # Custom frequency ranges section
        ranges_header = QHBoxLayout()
        ranges_header.addWidget(QLabel("Custom Frequency Ranges:"))
        ranges_header.addStretch()
        
        self.add_range_btn = QPushButton("+ Add Range")
        self.add_range_btn.setFixedWidth(80)
        self.add_range_btn.clicked.connect(self._add_freq_range)
        ranges_header.addWidget(self.add_range_btn)
        layout.addLayout(ranges_header)
        
        # Container for frequency ranges
        self.ranges_container = QWidget()
        self.ranges_layout = QVBoxLayout(self.ranges_container)
        self.ranges_layout.setContentsMargins(0, 0, 0, 0)
        self.ranges_layout.setSpacing(2)
        layout.addWidget(self.ranges_container)
        
        self._freq_range_widgets = []  # List of range widget tuples
        
        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.apply_btn = QPushButton("Apply StdDev")
        self.apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)
        
        self._update_enabled_states()
    
    def _on_mode_changed(self):
        self._update_enabled_states()
        self._emit_changed()
    
    def _add_freq_range(self):
        """Add a new frequency range row."""
        row_widget = QFrame()
        row_widget.setFrameShape(QFrame.StyledPanel)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(4, 2, 4, 2)
        
        # Freq min
        fmin_spin = QDoubleSpinBox()
        fmin_spin.setRange(0.1, 200.0)
        fmin_spin.setValue(1.0)
        fmin_spin.setSuffix(" Hz")
        fmin_spin.setDecimals(1)
        fmin_spin.valueChanged.connect(self._emit_changed)
        row_layout.addWidget(fmin_spin)
        
        row_layout.addWidget(QLabel("-"))
        
        # Freq max
        fmax_spin = QDoubleSpinBox()
        fmax_spin.setRange(0.1, 200.0)
        fmax_spin.setValue(50.0)
        fmax_spin.setSuffix(" Hz")
        fmax_spin.setDecimals(1)
        fmax_spin.valueChanged.connect(self._emit_changed)
        row_layout.addWidget(fmax_spin)
        
        row_layout.addWidget(QLabel("COV:"))
        
        # COV value
        cov_spin = QDoubleSpinBox()
        cov_spin.setRange(0.01, 1.0)
        cov_spin.setValue(0.1)
        cov_spin.setSingleStep(0.01)
        cov_spin.setDecimals(2)
        cov_spin.valueChanged.connect(self._emit_changed)
        row_layout.addWidget(cov_spin)
        
        # Remove button
        remove_btn = QPushButton("X")
        remove_btn.setFixedWidth(24)
        remove_btn.clicked.connect(lambda: self._remove_freq_range(row_widget))
        row_layout.addWidget(remove_btn)
        
        self.ranges_layout.addWidget(row_widget)
        self._freq_range_widgets.append((row_widget, fmin_spin, fmax_spin, cov_spin))
        self._emit_changed()
    
    def _remove_freq_range(self, widget):
        """Remove a frequency range row."""
        for i, (row, fmin, fmax, cov) in enumerate(self._freq_range_widgets):
            if row == widget:
                self._freq_range_widgets.pop(i)
                widget.deleteLater()
                self._emit_changed()
                break
    
    def _update_enabled_states(self):
        self.logstd_spin.setEnabled(self.logstd_radio.isChecked())
        self.cov_spin.setEnabled(self.cov_radio.isChecked())
        self.min_cov_spin.setEnabled(self.min_cov_cb.isChecked())
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def _on_apply(self):
        self.apply_requested.emit()
    
    def get_settings(self) -> StdDevSettings:
        """Get current settings."""
        if self.logstd_radio.isChecked():
            mode = "fixed_logstd"
        elif self.cov_radio.isChecked():
            mode = "fixed_cov"
        else:
            mode = "file"
        
        # Collect frequency ranges
        freq_ranges = []
        for row, fmin, fmax, cov in self._freq_range_widgets:
            freq_ranges.append(FreqRangeStdDev(
                freq_min=fmin.value(),
                freq_max=fmax.value(),
                mode="fixed_cov",
                value=cov.value()
            ))
        
        return StdDevSettings(
            mode=mode,
            fixed_logstd=self.logstd_spin.value(),
            fixed_cov=self.cov_spin.value(),
            use_min_cov=self.min_cov_cb.isChecked(),
            min_cov=self.min_cov_spin.value(),
            freq_ranges=freq_ranges if freq_ranges else None
        )
    
    def set_settings(self, settings: StdDevSettings):
        """Set settings."""
        if settings.mode == "fixed_logstd":
            self.logstd_radio.setChecked(True)
        elif settings.mode == "fixed_cov":
            self.cov_radio.setChecked(True)
        else:
            self.file_radio.setChecked(True)
        
        self.logstd_spin.setValue(settings.fixed_logstd)
        self.cov_spin.setValue(settings.fixed_cov)
        self.min_cov_cb.setChecked(settings.use_min_cov)
        self.min_cov_spin.setValue(settings.min_cov)
        
        # Clear existing frequency ranges
        for row, _, _, _ in self._freq_range_widgets:
            row.deleteLater()
        self._freq_range_widgets.clear()
        
        # Add frequency ranges from settings
        if settings.freq_ranges:
            for fr in settings.freq_ranges:
                self._add_freq_range()
                row, fmin, fmax, cov = self._freq_range_widgets[-1]
                fmin.setValue(fr.freq_min)
                fmax.setValue(fr.freq_max)
                cov.setValue(fr.value)
        
        self._update_enabled_states()


class ResamplingWidget(QWidget):
    """Widget for resampling options."""
    
    settings_changed = Signal()
    apply_requested = Signal()  # Emitted when Apply button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable checkbox
        self.enable_cb = QCheckBox("Enable resampling")
        self.enable_cb.toggled.connect(self._on_enable_changed)
        layout.addWidget(self.enable_cb)
        
        # Options container
        self.options_widget = QWidget()
        options_layout = QFormLayout(self.options_widget)
        options_layout.setContentsMargins(20, 5, 0, 0)
        
        # Method
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Logarithmic", "Linear"])
        self.method_combo.currentIndexChanged.connect(self._emit_changed)
        options_layout.addRow("Method:", self.method_combo)
        
        # Points
        self.npoints_spin = QSpinBox()
        self.npoints_spin.setRange(10, 500)
        self.npoints_spin.setValue(50)
        self.npoints_spin.valueChanged.connect(self._emit_changed)
        options_layout.addRow("Points:", self.npoints_spin)
        
        # Frequency range
        freq_layout = QHBoxLayout()
        self.fmin_spin = QDoubleSpinBox()
        self.fmin_spin.setRange(0.1, 200.0)
        self.fmin_spin.setSpecialValueText("Auto")
        self.fmin_spin.setValue(0.1)
        self.fmin_spin.valueChanged.connect(self._emit_changed)
        freq_layout.addWidget(self.fmin_spin)
        
        freq_layout.addWidget(QLabel("-"))
        
        self.fmax_spin = QDoubleSpinBox()
        self.fmax_spin.setRange(0.1, 200.0)
        self.fmax_spin.setSpecialValueText("Auto")
        self.fmax_spin.setValue(0.1)
        self.fmax_spin.valueChanged.connect(self._emit_changed)
        freq_layout.addWidget(self.fmax_spin)
        
        freq_layout.addWidget(QLabel("Hz"))
        freq_layout.addStretch()
        options_layout.addRow("Freq Range:", freq_layout)
        
        layout.addWidget(self.options_widget)
        self.options_widget.setEnabled(False)
        
        # Apply button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.apply_btn = QPushButton("Apply Resample")
        self.apply_btn.clicked.connect(self._on_apply)
        self.apply_btn.setEnabled(False)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)
    
    def _on_enable_changed(self, enabled: bool):
        self.options_widget.setEnabled(enabled)
        self.apply_btn.setEnabled(enabled)
        self._emit_changed()
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def _on_apply(self):
        self.apply_requested.emit()
    
    def get_settings(self) -> ResamplingSettings:
        """Get current settings."""
        fmin = self.fmin_spin.value() if self.fmin_spin.value() > 0.1 else None
        fmax = self.fmax_spin.value() if self.fmax_spin.value() > 0.1 else None
        
        return ResamplingSettings(
            enabled=self.enable_cb.isChecked(),
            method="log" if self.method_combo.currentIndex() == 0 else "linear",
            npoints=self.npoints_spin.value(),
            fmin=fmin,
            fmax=fmax
        )
    
    def set_settings(self, settings: ResamplingSettings):
        """Set settings."""
        self.enable_cb.setChecked(settings.enabled)
        self.method_combo.setCurrentIndex(0 if settings.method == "log" else 1)
        self.npoints_spin.setValue(settings.npoints)
        self.fmin_spin.setValue(settings.fmin if settings.fmin else 0.1)
        self.fmax_spin.setValue(settings.fmax if settings.fmax else 0.1)


class DummyPointsWidget(QWidget):
    """Widget for dummy points options."""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Enable checkbox
        self.enable_cb = QCheckBox("Add dummy points (weight=0)")
        self.enable_cb.toggled.connect(self._on_enable_changed)
        layout.addWidget(self.enable_cb)
        
        # Options container
        self.options_widget = QWidget()
        options_layout = QVBoxLayout(self.options_widget)
        options_layout.setContentsMargins(20, 5, 0, 0)
        
        # Mode radio buttons
        self.btn_group = QButtonGroup(self)
        
        # Extend mode
        extend_layout = QHBoxLayout()
        self.extend_radio = QRadioButton("Extend:")
        self.extend_radio.setChecked(True)
        self.extend_radio.toggled.connect(self._on_mode_changed)
        self.btn_group.addButton(self.extend_radio)
        extend_layout.addWidget(self.extend_radio)
        
        extend_layout.addWidget(QLabel("Low:"))
        self.extend_low_spin = QDoubleSpinBox()
        self.extend_low_spin.setRange(0.0, 100.0)
        self.extend_low_spin.setSpecialValueText("None")
        self.extend_low_spin.setValue(0.0)
        self.extend_low_spin.setSuffix(" Hz")
        self.extend_low_spin.valueChanged.connect(self._emit_changed)
        extend_layout.addWidget(self.extend_low_spin)
        
        extend_layout.addWidget(QLabel("High:"))
        self.extend_high_spin = QDoubleSpinBox()
        self.extend_high_spin.setRange(0.0, 200.0)
        self.extend_high_spin.setSpecialValueText("None")
        self.extend_high_spin.setValue(0.0)
        self.extend_high_spin.setSuffix(" Hz")
        self.extend_high_spin.valueChanged.connect(self._emit_changed)
        extend_layout.addWidget(self.extend_high_spin)
        extend_layout.addStretch()
        options_layout.addLayout(extend_layout)
        
        # Custom mode
        custom_layout = QHBoxLayout()
        self.custom_radio = QRadioButton("Custom:")
        self.custom_radio.toggled.connect(self._on_mode_changed)
        self.btn_group.addButton(self.custom_radio)
        custom_layout.addWidget(self.custom_radio)
        options_layout.addLayout(custom_layout)
        
        # Custom inputs
        custom_inputs = QFormLayout()
        custom_inputs.setContentsMargins(20, 0, 0, 0)
        
        self.freqs_edit = QLineEdit()
        self.freqs_edit.setPlaceholderText("e.g., 2, 3, 70, 80")
        self.freqs_edit.textChanged.connect(self._emit_changed)
        custom_inputs.addRow("Freqs (Hz):", self.freqs_edit)
        
        self.vels_edit = QLineEdit()
        self.vels_edit.setPlaceholderText("e.g., 600, 550, 150, 140")
        self.vels_edit.textChanged.connect(self._emit_changed)
        custom_inputs.addRow("Vels (m/s):", self.vels_edit)
        
        options_layout.addLayout(custom_inputs)
        
        layout.addWidget(self.options_widget)
        self.options_widget.setEnabled(False)
        self._update_enabled_states()
    
    def _on_enable_changed(self, enabled: bool):
        self.options_widget.setEnabled(enabled)
        self._emit_changed()
    
    def _on_mode_changed(self):
        self._update_enabled_states()
        self._emit_changed()
    
    def _update_enabled_states(self):
        extend_mode = self.extend_radio.isChecked()
        self.extend_low_spin.setEnabled(extend_mode)
        self.extend_high_spin.setEnabled(extend_mode)
        self.freqs_edit.setEnabled(not extend_mode)
        self.vels_edit.setEnabled(not extend_mode)
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def get_settings(self) -> DummyPointsSettings:
        """Get current settings."""
        extend_low = self.extend_low_spin.value() if self.extend_low_spin.value() > 0 else None
        extend_high = self.extend_high_spin.value() if self.extend_high_spin.value() > 0 else None
        
        return DummyPointsSettings(
            enabled=self.enable_cb.isChecked(),
            mode="extend" if self.extend_radio.isChecked() else "custom",
            extend_low=extend_low,
            extend_high=extend_high,
            custom_freqs=self.freqs_edit.text(),
            custom_vels=self.vels_edit.text()
        )
    
    def set_settings(self, settings: DummyPointsSettings):
        """Set settings."""
        self.enable_cb.setChecked(settings.enabled)
        if settings.mode == "extend":
            self.extend_radio.setChecked(True)
        else:
            self.custom_radio.setChecked(True)
        
        self.extend_low_spin.setValue(settings.extend_low if settings.extend_low else 0.0)
        self.extend_high_spin.setValue(settings.extend_high if settings.extend_high else 0.0)
        self.freqs_edit.setText(settings.custom_freqs)
        self.vels_edit.setText(settings.custom_vels)
        self._update_enabled_states()


class GlobalProcessingWidget(QWidget):
    """Widget for global processing options that override all curves."""
    
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # StdDev override
        stddev_layout = QHBoxLayout()
        self.stddev_cb = QCheckBox("Override StdDev:")
        self.stddev_cb.toggled.connect(self._on_stddev_toggled)
        stddev_layout.addWidget(self.stddev_cb)
        
        self.stddev_widget = StdDevWidget()
        self.stddev_widget.setEnabled(False)
        self.stddev_widget.settings_changed.connect(self._emit_changed)
        layout.addLayout(stddev_layout)
        layout.addWidget(self.stddev_widget)
        
        # Resample override
        resample_layout = QHBoxLayout()
        self.resample_cb = QCheckBox("Resample All:")
        self.resample_cb.toggled.connect(self._on_resample_toggled)
        resample_layout.addWidget(self.resample_cb)
        layout.addLayout(resample_layout)
        
        self.resample_widget = ResamplingWidget()
        self.resample_widget.setEnabled(False)
        self.resample_widget.settings_changed.connect(self._emit_changed)
        layout.addWidget(self.resample_widget)
        
        # Dummy points
        self.dummy_widget = DummyPointsWidget()
        self.dummy_widget.settings_changed.connect(self._emit_changed)
        layout.addWidget(self.dummy_widget)
    
    def _on_stddev_toggled(self, checked: bool):
        self.stddev_widget.setEnabled(checked)
        self._emit_changed()
    
    def _on_resample_toggled(self, checked: bool):
        self.resample_widget.setEnabled(checked)
        self._emit_changed()
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def get_stddev_override(self) -> Optional[StdDevSettings]:
        """Get stddev override if enabled."""
        if self.stddev_cb.isChecked():
            return self.stddev_widget.get_settings()
        return None
    
    def get_resample_override(self) -> Optional[ResamplingSettings]:
        """Get resample override if enabled."""
        if self.resample_cb.isChecked():
            settings = self.resample_widget.get_settings()
            settings.enabled = True
            return settings
        return None
    
    def get_dummy_settings(self) -> DummyPointsSettings:
        """Get dummy points settings."""
        return self.dummy_widget.get_settings()
