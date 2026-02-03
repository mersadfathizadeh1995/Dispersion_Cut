"""
Curve Properties Widgets
========================

Property panels for Rayleigh and Love dispersion curves.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QPushButton,
    QLabel, QGroupBox, QFileDialog, QScrollArea, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from typing import Optional
import os
import numpy as np

from .curve_tree import CurveData, CurveType
from .collapsible import CollapsibleSection
from .processing_widgets import StdDevWidget, ResamplingWidget, StdDevSettings, ResamplingSettings
from .cut_widget import CutWidget, CutSettings
from .dummy_points_widget import DummyPointsWidget, DummyPointsSettings
from .save_widget import SaveWidget, SaveSettings, save_curve_txt, save_curve_csv, save_curve_json
from .curve_history import get_history_manager


class DispersionPropertiesWidget(QWidget):
    """Properties panel for Rayleigh/Love dispersion curves."""
    
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
        self.title_label = QLabel("Dispersion Curve")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.title_label)
        
        # Scroll area for all sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 5, 0)
        
        # Basic Info Section (collapsible)
        self.basic_section = CollapsibleSection("Basic Info", expanded=True)
        basic_widget = QWidget()
        basic_layout = QFormLayout(basic_widget)
        basic_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        # Name
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_data_changed)
        basic_layout.addRow("Name:", self.name_edit)
        
        # Mode
        self.mode_spin = QSpinBox()
        self.mode_spin.setRange(0, 10)
        self.mode_spin.valueChanged.connect(self._on_data_changed)
        basic_layout.addRow("Mode:", self.mode_spin)
        
        # StdDev Type
        self.stddev_combo = QComboBox()
        self.stddev_combo.addItems(["LogStd", "COV"])
        self.stddev_combo.currentIndexChanged.connect(self._on_data_changed)
        basic_layout.addRow("StdDev Type:", self.stddev_combo)
        
        # Points and Frequency info
        self.points_label = QLabel("-")
        basic_layout.addRow("Points:", self.points_label)
        
        self.freq_label = QLabel("-")
        basic_layout.addRow("Frequency:", self.freq_label)
        
        self.basic_section.add_widget(basic_widget)
        scroll_layout.addWidget(self.basic_section)
        
        # Cut/Trim Section
        self.cut_section = CollapsibleSection("Cut/Trim", expanded=False)
        self.cut_widget = CutWidget()
        self.cut_widget.settings_changed.connect(self._on_processing_changed)
        self.cut_widget.apply_requested.connect(self._apply_cut)
        self.cut_section.add_widget(self.cut_widget)
        scroll_layout.addWidget(self.cut_section)
        
        # Resampling Section
        self.resample_section = CollapsibleSection("Resampling", expanded=False)
        self.resample_widget = ResamplingWidget()
        self.resample_widget.settings_changed.connect(self._on_processing_changed)
        self.resample_widget.apply_requested.connect(self._apply_resample)
        self.resample_section.add_widget(self.resample_widget)
        scroll_layout.addWidget(self.resample_section)
        
        # Standard Deviation Section
        self.stddev_section = CollapsibleSection("Standard Deviation", expanded=False)
        self.stddev_widget = StdDevWidget()
        self.stddev_widget.settings_changed.connect(self._on_processing_changed)
        self.stddev_widget.apply_requested.connect(self._apply_stddev)
        self.stddev_section.add_widget(self.stddev_widget)
        scroll_layout.addWidget(self.stddev_section)
        
        # Dummy Points Section
        self.dummy_section = CollapsibleSection("Dummy Points", expanded=False)
        self.dummy_widget = DummyPointsWidget()
        self.dummy_widget.settings_changed.connect(self._on_processing_changed)
        self.dummy_widget.apply_requested.connect(self._apply_dummy)
        self.dummy_section.add_widget(self.dummy_widget)
        scroll_layout.addWidget(self.dummy_section)
        
        # Save/Export Section
        self.save_section = CollapsibleSection("Save/Export", expanded=False)
        self.save_widget = SaveWidget()
        self.save_widget.save_requested.connect(self._apply_save)
        self.save_section.add_widget(self.save_widget)
        scroll_layout.addWidget(self.save_section)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Preview")
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
        
        # Update title
        type_name = "Rayleigh" if data.curve_type == CurveType.RAYLEIGH else "Love"
        self.title_label.setText(f"{type_name} Curve")
        
        # Update fields
        self.file_edit.setText(data.filepath or "")
        self.name_edit.setText(data.name)
        self.mode_spin.setValue(data.mode)
        self.stddev_combo.setCurrentIndex(0 if data.stddev_type == "logstd" else 1)
        
        # Update info
        self.points_label.setText(str(data.n_points) if data.n_points else "-")
        if data.freq_min and data.freq_max:
            self.freq_label.setText(f"{data.freq_min:.2f} - {data.freq_max:.2f} Hz")
        else:
            self.freq_label.setText("-")
        
        # Load processing settings from CurveData
        # Convert stored dicts to FreqRangeStdDev objects
        freq_ranges = None
        if data.stddev_freq_ranges:
            from .processing_widgets import FreqRangeStdDev
            freq_ranges = [
                FreqRangeStdDev(
                    freq_min=fr['freq_min'],
                    freq_max=fr['freq_max'],
                    value=fr['value']
                ) for fr in data.stddev_freq_ranges
            ]
        
        stddev_settings = StdDevSettings(
            mode=data.stddev_mode,
            fixed_logstd=data.fixed_logstd,
            fixed_cov=data.fixed_cov,
            use_min_cov=data.use_min_cov,
            min_cov=data.min_cov,
            freq_ranges=freq_ranges
        )
        self.stddev_widget.set_settings(stddev_settings)
        
        resample_settings = ResamplingSettings(
            enabled=data.resample_enabled,
            method=data.resample_method,
            npoints=data.resample_npoints,
            fmin=data.resample_fmin,
            fmax=data.resample_fmax
        )
        self.resample_widget.set_settings(resample_settings)
        
        # Load cut settings
        cut_settings = CutSettings(
            enabled=data.cut_enabled,
            freq_min=data.cut_freq_min,
            freq_max=data.cut_freq_max
        )
        self.cut_widget.set_settings(cut_settings)
        if data.freq_min and data.freq_max:
            self.cut_widget.set_frequency_range(data.freq_min, data.freq_max)
        
        # Load dummy points settings
        dummy_settings = DummyPointsSettings(
            enabled=data.dummy_enabled,
            mode=data.dummy_mode,
            extend_low=data.dummy_extend_low,
            extend_high=data.dummy_extend_high,
            custom_freqs=data.dummy_custom_freqs,
            custom_vels=data.dummy_custom_vels
        )
        self.dummy_widget.set_settings(dummy_settings)
        if data.freq_min and data.freq_max:
            self.dummy_widget.set_frequency_range(data.freq_min, data.freq_max)
        
        # Set save widget defaults
        self.save_widget.set_curve_name(data.name)
        
        self._updating = False
    
    def _browse_file(self):
        """Browse for a new file."""
        if not self._current_data:
            return
            
        file_filter = "Text files (*.txt);;All files (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Curve File", "", file_filter
        )
        if filepath:
            self._load_new_file(filepath)
    
    def _load_new_file(self, filepath: str):
        """Load a new file and update the curve data."""
        if not self._current_data or not self._current_uid:
            return
            
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self.mode_spin.value(),
                stddev_type="logstd" if self.stddev_combo.currentIndex() == 0 else "cov"
            )
            
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
    
    def _on_data_changed(self):
        """Handle data changes."""
        if self._updating or not self._current_data or not self._current_uid:
            return
        
        self._current_data.name = self.name_edit.text()
        self._current_data.mode = self.mode_spin.value()
        self._current_data.stddev_type = "logstd" if self.stddev_combo.currentIndex() == 0 else "cov"
        
        self.data_changed.emit(self._current_uid, self._current_data)
    
    def _on_processing_changed(self):
        """Handle processing settings change."""
        if self._updating or not self._current_uid or not self._current_data:
            return
        
        # Save stddev settings to CurveData
        stddev = self.stddev_widget.get_settings()
        self._current_data.stddev_mode = stddev.mode
        self._current_data.fixed_logstd = stddev.fixed_logstd
        self._current_data.fixed_cov = stddev.fixed_cov
        self._current_data.use_min_cov = stddev.use_min_cov
        self._current_data.min_cov = stddev.min_cov
        # Save multiple frequency ranges
        if stddev.freq_ranges:
            self._current_data.stddev_freq_ranges = [
                {'freq_min': fr.freq_min, 'freq_max': fr.freq_max, 'value': fr.value}
                for fr in stddev.freq_ranges
            ]
        else:
            self._current_data.stddev_freq_ranges = None
        
        # Save resample settings to CurveData
        resample = self.resample_widget.get_settings()
        self._current_data.resample_enabled = resample.enabled
        self._current_data.resample_method = resample.method
        self._current_data.resample_npoints = resample.npoints
        self._current_data.resample_fmin = resample.fmin
        self._current_data.resample_fmax = resample.fmax
        
        self.data_changed.emit(self._current_uid, self._current_data)
    
    def _on_preview(self):
        """Request data preview."""
        if self._current_uid:
            self.preview_requested.emit(self._current_uid)
    
    def _on_remove(self):
        """Request curve removal."""
        if self._current_uid:
            self.remove_requested.emit(self._current_uid)
    
    def get_stddev_settings(self) -> StdDevSettings:
        """Get current stddev settings."""
        return self.stddev_widget.get_settings()
    
    def get_resample_settings(self) -> ResamplingSettings:
        """Get current resampling settings."""
        return self.resample_widget.get_settings()
    
    def _apply_cut(self):
        """Apply cut/trim to the curve."""
        if not self._current_uid or not self._current_data:
            return
        
        settings = self.cut_widget.get_settings()
        if not settings.enabled or not settings.freq_min or not settings.freq_max:
            QMessageBox.warning(self, "Error", "Please enable cut and set frequency range.")
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            
            # Load current working file
            filepath = self._current_data.working_filepath or self._current_data.filepath
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self._current_data.mode,
                stddev_type=self._current_data.stddev_type
            )
            
            # Apply cut
            mask = (curve.frequency >= settings.freq_min) & (curve.frequency <= settings.freq_max)
            new_freq = curve.frequency[mask]
            new_vel = curve.velocity[mask]
            new_std = curve.velstd[mask]
            
            if len(new_freq) < 2:
                QMessageBox.warning(self, "Error", "Cut would result in too few points.")
                return
            
            # Save to temp file
            history = get_history_manager()
            import tempfile
            temp_file = os.path.join(history.temp_dir, f"{self._current_uid}_cut.txt")
            save_curve_txt(temp_file, new_freq, new_vel, new_std)
            
            # Update history and working file
            working_path = history.push_state(
                self._current_uid, temp_file,
                f"Cut to {settings.freq_min:.1f}-{settings.freq_max:.1f} Hz"
            )
            self._current_data.working_filepath = working_path
            
            # Update metadata
            self._current_data.n_points = len(new_freq)
            self._current_data.freq_min = float(new_freq.min())
            self._current_data.freq_max = float(new_freq.max())
            self._update_info_labels()
            
            self.data_changed.emit(self._current_uid, self._current_data)
            QMessageBox.information(self, "Success", f"Cut applied: {len(new_freq)} points remaining.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cut failed: {e}")
    
    def _apply_resample(self):
        """Apply resampling to the curve."""
        if not self._current_uid or not self._current_data:
            return
        
        settings = self.resample_widget.get_settings()
        if not settings.enabled:
            QMessageBox.warning(self, "Error", "Please enable resampling first.")
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            from sw_dcml.dinver.target.target_new.resample import resample_dispersion_curve
            
            # Load current working file
            filepath = self._current_data.working_filepath or self._current_data.filepath
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self._current_data.mode,
                stddev_type=self._current_data.stddev_type
            )
            
            # Apply resample
            fmin = settings.fmin if settings.fmin else float(curve.frequency.min())
            fmax = settings.fmax if settings.fmax else float(curve.frequency.max())
            resampled = resample_dispersion_curve(
                curve, pmin=fmin, pmax=fmax,
                pn=settings.npoints, res_type=settings.method
            )
            
            # Save to temp file
            history = get_history_manager()
            import tempfile
            temp_file = os.path.join(history.temp_dir, f"{self._current_uid}_resampled.txt")
            save_curve_txt(temp_file, resampled.frequency, resampled.velocity, resampled.velstd)
            
            # Update history and working file
            working_path = history.push_state(
                self._current_uid, temp_file,
                f"Resampled to {settings.npoints} points ({settings.method})"
            )
            self._current_data.working_filepath = working_path
            
            # Update metadata
            self._current_data.n_points = resampled.n_points
            self._current_data.freq_min = float(resampled.frequency.min())
            self._current_data.freq_max = float(resampled.frequency.max())
            self._update_info_labels()
            
            self.data_changed.emit(self._current_uid, self._current_data)
            QMessageBox.information(self, "Success", f"Resampled to {settings.npoints} points.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Resample failed: {e}")
    
    def _apply_stddev(self):
        """Apply standard deviation modifications to the curve."""
        if not self._current_uid or not self._current_data:
            return
        
        settings = self.stddev_widget.get_settings()
        if settings.mode == "file" and not settings.freq_ranges:
            QMessageBox.warning(self, "Info", "Using stddev from file (no changes to apply).")
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            
            # Load current working file
            filepath = self._current_data.working_filepath or self._current_data.filepath
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self._current_data.mode,
                stddev_type=self._current_data.stddev_type
            )
            
            # Apply global stddev
            if settings.mode == "fixed_logstd":
                curve.set_fixed_logstd(settings.fixed_logstd)
            elif settings.mode == "fixed_cov":
                curve.set_fixed_cov(settings.fixed_cov)
            
            # Apply frequency-specific ranges
            if settings.freq_ranges:
                for fr in settings.freq_ranges:
                    mask = (curve.frequency >= fr.freq_min) & (curve.frequency <= fr.freq_max)
                    curve.velstd[mask] = curve.velocity[mask] * fr.value
            
            # Apply min COV
            if settings.use_min_cov:
                curve.set_min_cov(settings.min_cov)
            
            # Save to temp file
            history = get_history_manager()
            temp_file = os.path.join(history.temp_dir, f"{self._current_uid}_stddev.txt")
            save_curve_txt(temp_file, curve.frequency, curve.velocity, curve.velstd)
            
            # Update history and working file
            working_path = history.push_state(
                self._current_uid, temp_file, f"StdDev modified ({settings.mode})"
            )
            self._current_data.working_filepath = working_path
            
            self.data_changed.emit(self._current_uid, self._current_data)
            QMessageBox.information(self, "Success", "Standard deviation applied.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"StdDev apply failed: {e}")
    
    def _apply_dummy(self):
        """Apply dummy points to the curve."""
        if not self._current_uid or not self._current_data:
            return
        
        settings = self.dummy_widget.get_settings()
        if not settings.enabled:
            QMessageBox.warning(self, "Error", "Please enable dummy points first.")
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            
            # Load current working file
            filepath = self._current_data.working_filepath or self._current_data.filepath
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self._current_data.mode,
                stddev_type=self._current_data.stddev_type
            )
            
            freq = curve.frequency.tolist()
            vel = curve.velocity.tolist()
            std = curve.velstd.tolist()
            
            if settings.mode == "extend":
                # Extend low
                if settings.extend_low and settings.extend_low < freq[0]:
                    freq.insert(0, settings.extend_low)
                    vel.insert(0, vel[0])  # Use first velocity
                    std.insert(0, vel[0] * 0.3)  # 30% uncertainty for dummy
                
                # Extend high
                if settings.extend_high and settings.extend_high > freq[-1]:
                    freq.append(settings.extend_high)
                    vel.append(vel[-1])  # Use last velocity
                    std.append(vel[-1] * 0.3)  # 30% uncertainty for dummy
            else:
                # Custom points
                custom_freqs = [float(f.strip()) for f in settings.custom_freqs.split(",") if f.strip()]
                custom_vels = [float(v.strip()) for v in settings.custom_vels.split(",") if v.strip()]
                
                for f, v in zip(custom_freqs, custom_vels):
                    freq.append(f)
                    vel.append(v)
                    std.append(v * 0.3)
                
                # Sort by frequency
                sorted_data = sorted(zip(freq, vel, std))
                freq, vel, std = zip(*sorted_data)
            
            freq = np.array(freq)
            vel = np.array(vel)
            std = np.array(std)
            
            # Save to temp file
            history = get_history_manager()
            temp_file = os.path.join(history.temp_dir, f"{self._current_uid}_dummy.txt")
            save_curve_txt(temp_file, freq, vel, std)
            
            # Update history and working file
            working_path = history.push_state(
                self._current_uid, temp_file, f"Dummy points added ({settings.mode})"
            )
            self._current_data.working_filepath = working_path
            
            # Update metadata
            self._current_data.n_points = len(freq)
            self._current_data.freq_min = float(freq.min())
            self._current_data.freq_max = float(freq.max())
            self._update_info_labels()
            
            self.data_changed.emit(self._current_uid, self._current_data)
            QMessageBox.information(self, "Success", f"Dummy points added: {len(freq)} points total.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Dummy points failed: {e}")
    
    def _apply_save(self):
        """Save the curve to a file."""
        if not self._current_uid or not self._current_data:
            return
        
        settings = self.save_widget.get_settings()
        if not settings.directory:
            QMessageBox.warning(self, "Error", "Please select an output directory.")
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            
            # Load current working file
            filepath = self._current_data.working_filepath or self._current_data.filepath
            curve = DispersionCurve.from_file(
                filepath,
                polarization=self._current_data.curve_type.value,
                mode=self._current_data.mode,
                stddev_type=self._current_data.stddev_type
            )
            
            output_path = self.save_widget.get_output_path()
            
            if settings.format == "txt":
                save_curve_txt(output_path, curve.frequency, curve.velocity, curve.velstd)
            elif settings.format == "csv":
                save_curve_csv(output_path, curve.frequency, curve.velocity, curve.velstd)
            elif settings.format == "json":
                metadata = {
                    "name": self._current_data.name,
                    "polarization": self._current_data.curve_type.value,
                    "mode": self._current_data.mode
                }
                save_curve_json(output_path, curve.frequency, curve.velocity, curve.velstd, metadata)
            
            QMessageBox.information(self, "Success", f"Saved to:\n{output_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Save failed: {e}")
    
    def _update_info_labels(self):
        """Update the info labels with current data."""
        if self._current_data:
            self.points_label.setText(str(self._current_data.n_points) if self._current_data.n_points else "-")
            if self._current_data.freq_min and self._current_data.freq_max:
                self.freq_label.setText(f"{self._current_data.freq_min:.2f} - {self._current_data.freq_max:.2f} Hz")
            else:
                self.freq_label.setText("-")
