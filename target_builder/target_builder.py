"""
Target Builder Widget
=====================

Main widget for the Target Builder GUI.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QFormLayout, QLineEdit, QPushButton,
    QFileDialog, QLabel, QCheckBox, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path
from typing import Optional, List
import os

from .curve_tree import CurveTreeWidget, CurveData, CurveType
from .properties_panel import PropertiesPanel
from .collapsible import CollapsibleSection
from .processing_widgets import GlobalProcessingWidget
from .weights_widget import WeightsWidget
from .canvas_preview import CanvasPreviewWindow
from .averaging_dialog import AveragingDialog
from .summary_dialog import SummaryDialog
from .curve_history import get_history_manager

from ..project import get_project_manager


class TargetBuilderWidget(QWidget):
    """Main Target Builder widget."""
    
    target_created = Signal(str)  # Emits path to created target file
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_window: Optional[CanvasPreviewWindow] = None
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header with active run info and undo/redo
        header_layout = QHBoxLayout()
        header_label = QLabel("Target Builder")
        header_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(header_label)
        
        # Undo/Redo buttons
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setFixedWidth(60)
        self.undo_btn.clicked.connect(self._on_undo)
        self.undo_btn.setEnabled(False)
        header_layout.addWidget(self.undo_btn)
        
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setFixedWidth(60)
        self.redo_btn.clicked.connect(self._on_redo)
        self.redo_btn.setEnabled(False)
        header_layout.addWidget(self.redo_btn)
        
        header_layout.addStretch()
        
        # Active run indicator
        header_layout.addWidget(QLabel("Active Run:"))
        self.active_run_label = QLabel("No project")
        self.active_run_label.setStyleSheet("font-weight: bold; color: #0078d4;")
        self.active_run_label.setMinimumWidth(100)
        header_layout.addWidget(self.active_run_label)
        
        layout.addLayout(header_layout)
        
        # Track current curve for undo/redo
        self._current_curve_uid: Optional[str] = None
        
        # Main content - splitter with tree and properties
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Curve Tree
        self.curve_tree = CurveTreeWidget()
        self.curve_tree.setMinimumWidth(200)
        self.curve_tree.setMaximumWidth(350)
        self.splitter.addWidget(self.curve_tree)
        
        # Right panel - Properties
        self.properties_panel = PropertiesPanel()
        self.properties_panel.setMinimumWidth(300)
        self.splitter.addWidget(self.properties_panel)
        
        # Set initial sizes (30% left, 70% right)
        self.splitter.setSizes([250, 550])
        
        layout.addWidget(self.splitter, 1)  # stretch factor 1
        
        # Bottom section with scroll for small windows
        bottom_scroll = QScrollArea()
        bottom_scroll.setWidgetResizable(True)
        bottom_scroll.setMaximumHeight(250)
        bottom_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Global Processing Section
        self.global_section = CollapsibleSection("Global Processing (Override All)", expanded=False)
        self.global_processing = GlobalProcessingWidget()
        self.global_section.add_widget(self.global_processing)
        bottom_layout.addWidget(self.global_section)
        
        # Weights Section
        self.weights_widget = WeightsWidget()
        bottom_layout.addWidget(self.weights_widget)
        
        bottom_scroll.setWidget(bottom_container)
        layout.addWidget(bottom_scroll)
        
        # Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        
        # File path
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Output File:"))
        
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Select output .target file...")
        file_layout.addWidget(self.output_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        file_layout.addWidget(browse_btn)
        
        output_layout.addLayout(file_layout)
        
        # Options and Create button
        options_layout = QHBoxLayout()
        
        self.export_txt_cb = QCheckBox("Also export readable .txt")
        options_layout.addWidget(self.export_txt_cb)
        
        self.show_summary_cb = QCheckBox("Show summary before create")
        self.show_summary_cb.setChecked(True)
        options_layout.addWidget(self.show_summary_cb)
        
        options_layout.addStretch()
        
        # Average button
        self.average_btn = QPushButton("Average Curves...")
        self.average_btn.clicked.connect(self._show_averaging_dialog)
        options_layout.addWidget(self.average_btn)
        
        self.create_btn = QPushButton("Create Target File")
        self.create_btn.setMinimumWidth(150)
        self.create_btn.clicked.connect(self._create_target)
        options_layout.addWidget(self.create_btn)
        
        output_layout.addLayout(options_layout)
        
        layout.addWidget(output_group)
        
        # Status label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
    
    def _connect_signals(self):
        """Connect internal signals."""
        # Tree signals
        self.curve_tree.curve_selected.connect(self._on_curve_selected)
        self.curve_tree.curve_added.connect(self._on_curve_added)
        self.curve_tree.curve_removed.connect(self._on_curve_removed)
        
        # Properties panel signals
        self.properties_panel.data_changed.connect(self._on_data_changed)
        self.properties_panel.remove_requested.connect(self._on_remove_requested)
        self.properties_panel.preview_requested.connect(self._on_preview_requested)
        
        # ProjectManager signals
        pm = get_project_manager()
        pm.project_loaded.connect(self._on_project_changed)
        pm.project_closed.connect(self._on_project_closed)
        pm.active_run_changed.connect(self._on_active_run_changed)
        
        # Initialize with current project state
        self._update_project_state()
    
    def _on_curve_selected(self, uid: str):
        """Handle curve selection in tree."""
        self._current_curve_uid = uid
        data = self.curve_tree.get_curve(uid)
        if data:
            self.properties_panel.show_curve(uid, data)
            self._update_undo_redo_buttons()
    
    def _on_curve_added(self, uid: str):
        """Handle curve added."""
        self._current_curve_uid = uid
        data = self.curve_tree.get_curve(uid)
        if data:
            # Initialize history for the curve if it has a file
            if data.filepath:
                history = get_history_manager()
                working_path = history.initialize_curve(uid, data.filepath, "Original")
                data.working_filepath = working_path
                self.curve_tree.update_curve(uid, data)
            
            self.properties_panel.show_curve(uid, data)
            self._update_status(f"Added: {data.name}")
            self._update_undo_redo_buttons()
    
    def _on_curve_removed(self, uid: str):
        """Handle curve removed."""
        # Clean up history for removed curve
        history = get_history_manager()
        history.remove_curve(uid)
        
        self._current_curve_uid = None
        self.properties_panel.clear()
        self._update_status("Curve removed")
        self._update_undo_redo_buttons()
    
    def _on_data_changed(self, uid: str, data: CurveData):
        """Handle data change from properties panel."""
        self.curve_tree.update_curve(uid, data)
    
    def _on_remove_requested(self, uid: str):
        """Handle remove request from properties panel."""
        self.curve_tree.remove_curve(uid)
    
    def _on_preview_requested(self, uid: str):
        """Handle preview request - show canvas preview window."""
        curves = self.curve_tree.get_all_curves()
        if not curves:
            self._update_status("No curves to preview")
            return
        
        # Create or show preview window
        if self._preview_window is None:
            self._preview_window = CanvasPreviewWindow(self)
        
        self._preview_window.set_curves(curves)
        self._preview_window.show()
        self._preview_window.raise_()
        self._update_status("Preview window opened")
    
    def _browse_output(self):
        """Browse for output file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Target File", "",
            "Target files (*.target);;All files (*.*)"
        )
        if filepath:
            if not filepath.endswith('.target'):
                filepath += '.target'
            self.output_edit.setText(filepath)
    
    def _update_status(self, message: str):
        """Update status label."""
        self.status_label.setText(message)
    
    def _update_project_state(self):
        """Update UI based on current project state."""
        pm = get_project_manager()
        
        if pm.has_project and pm.active_run:
            self.active_run_label.setText(f"{pm.site_name} / {pm.active_run.name}")
            self.active_run_label.setStyleSheet("font-weight: bold; color: #0078d4;")
            
            # Set default output path
            target_path = pm.get_target_path()
            if target_path:
                self.output_edit.setText(target_path)
        else:
            self.active_run_label.setText("No project")
            self.active_run_label.setStyleSheet("font-weight: bold; color: gray;")
    
    def _on_project_changed(self, project):
        """Handle project loaded."""
        self._update_project_state()
    
    def _on_project_closed(self):
        """Handle project closed."""
        self.active_run_label.setText("No project")
        self.active_run_label.setStyleSheet("font-weight: bold; color: gray;")
        self.output_edit.clear()
    
    def _on_active_run_changed(self, run):
        """Handle active run changed."""
        self._update_project_state()
        self._update_status(f"Active run: {run.name}" if run else "No active run")
    
    def _update_undo_redo_buttons(self):
        """Update undo/redo button states based on current curve."""
        if not self._current_curve_uid:
            self.undo_btn.setEnabled(False)
            self.redo_btn.setEnabled(False)
            return
        
        history = get_history_manager()
        self.undo_btn.setEnabled(history.can_undo(self._current_curve_uid))
        self.redo_btn.setEnabled(history.can_redo(self._current_curve_uid))
    
    def _on_undo(self):
        """Handle undo button click."""
        if not self._current_curve_uid:
            return
        
        history = get_history_manager()
        state = history.undo(self._current_curve_uid)
        if state:
            # Update curve data with previous state
            data = self.curve_tree.get_curve(self._current_curve_uid)
            if data:
                data.working_filepath = state.filepath
                # Reload metadata from working file
                self._reload_curve_metadata(data)
                self.curve_tree.update_curve(self._current_curve_uid, data)
                self.properties_panel.show_curve(self._current_curve_uid, data)
                self._update_status(f"Undo: {state.description}")
        
        self._update_undo_redo_buttons()
    
    def _on_redo(self):
        """Handle redo button click."""
        if not self._current_curve_uid:
            return
        
        history = get_history_manager()
        state = history.redo(self._current_curve_uid)
        if state:
            # Update curve data with next state
            data = self.curve_tree.get_curve(self._current_curve_uid)
            if data:
                data.working_filepath = state.filepath
                # Reload metadata from working file
                self._reload_curve_metadata(data)
                self.curve_tree.update_curve(self._current_curve_uid, data)
                self.properties_panel.show_curve(self._current_curve_uid, data)
                self._update_status(f"Redo: {state.description}")
        
        self._update_undo_redo_buttons()
    
    def _reload_curve_metadata(self, data: CurveData):
        """Reload curve metadata from working file."""
        if not data.working_filepath:
            return
        
        try:
            from sw_dcml.dinver.target.target_new.models import DispersionCurve
            curve = DispersionCurve.from_file(
                data.working_filepath,
                polarization=data.curve_type.value,
                mode=data.mode,
                stddev_type=data.stddev_type
            )
            data.n_points = curve.n_points
            data.freq_min = float(curve.frequency.min())
            data.freq_max = float(curve.frequency.max())
        except Exception as e:
            print(f"Error reloading curve metadata: {e}")
    
    def _show_averaging_dialog(self):
        """Show the averaging dialog."""
        curves = self.curve_tree.get_all_curves()
        if len([c for c in curves if c.curve_type in 
               (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED)]) < 2:
            QMessageBox.warning(
                self, "Error", 
                "Need at least 2 dispersion curves to average."
            )
            return
        
        dialog = AveragingDialog(curves, self)
        dialog.curves_averaged.connect(self._on_curves_averaged)
        dialog.exec()
    
    def _on_curves_averaged(self, averaged_data: CurveData):
        """Handle averaged curve result."""
        self.curve_tree.add_curve(averaged_data)
        self._update_status(f"Created averaged curve: {averaged_data.name}")
    
    def _create_target(self):
        """Create the target file."""
        # Validate
        output_path = self.output_edit.text()
        if not output_path:
            QMessageBox.warning(self, "Error", "Please specify an output file path.")
            return
        
        included_curves = self.curve_tree.get_included_curves()
        if not included_curves:
            QMessageBox.warning(self, "Error", "No curves selected for inclusion.")
            return
        
        # Show summary dialog if enabled
        if self.show_summary_cb.isChecked():
            weights = {
                'dispersion': self.weights_widget.get_settings().dispersion,
                'hv_curve': self.weights_widget.get_settings().hv_curve,
                'hv_peak': self.weights_widget.get_settings().hv_peak
            }
            dialog = SummaryDialog(included_curves, output_path, weights, self)
            if dialog.exec() != SummaryDialog.Accepted:
                return
        
        try:
            self._build_target(output_path, included_curves)
            
            # Export txt if requested
            if self.export_txt_cb.isChecked():
                txt_path = output_path.replace('.target', '.txt')
                from sw_dcml.dinver.target.target_new.reader import TargetReader
                reader = TargetReader(output_path)
                reader.read()
                reader.to_txt(txt_path)
                self._update_status(f"Created: {output_path} + {txt_path}")
            else:
                self._update_status(f"Created: {output_path}")
            
            QMessageBox.information(
                self, "Success", 
                f"Target file created successfully!\n\n{output_path}"
            )
            
            self.target_created.emit(output_path)
            
            # Update project run status
            pm = get_project_manager()
            if pm.has_project:
                pm.refresh_status()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create target file:\n\n{e}")
            self._update_status(f"Error: {e}")
    
    def _build_target(self, output_path: str, curves: List[CurveData]):
        """Build the target file from curve data."""
        from sw_dcml.dinver.target.target_new.models import (
            DispersionCurve, HVCurve, HVPeak, TargetConfig
        )
        from sw_dcml.dinver.target.target_new.writer import TargetWriter
        from sw_dcml.dinver.target.target_new.resample import resample_dispersion_curve
        
        # Get global processing settings
        global_stddev = self.global_processing.get_stddev_override()
        global_resample = self.global_processing.get_resample_override()
        dummy_settings = self.global_processing.get_dummy_settings()
        
        # Get weights
        weight_settings = self.weights_widget.get_settings()
        
        dispersion_curves = []
        hv_curve = None
        hv_peak = None
        
        for curve_data in curves:
            if curve_data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
                if not curve_data.filepath:
                    continue
                    
                # Determine polarization
                if curve_data.curve_type == CurveType.AVERAGED:
                    polarization = 'love' if 'love' in curve_data.name.lower() else 'rayleigh'
                else:
                    polarization = curve_data.curve_type.value
                
                dc = DispersionCurve.from_file(
                    curve_data.filepath,
                    polarization=polarization,
                    mode=curve_data.mode,
                    name=curve_data.name,
                    stddev_type=curve_data.stddev_type
                )
                
                # Apply per-curve stddev processing (or global override)
                if global_stddev:
                    dc = self._apply_stddev(dc, global_stddev)
                elif curve_data.stddev_mode != "file":
                    dc = self._apply_curve_stddev(dc, curve_data)
                
                # Apply per-curve resampling (or global override)
                if global_resample and global_resample.enabled:
                    dc = self._apply_resampling(dc, global_resample)
                elif curve_data.resample_enabled:
                    dc = self._apply_curve_resampling(dc, curve_data)
                
                # Apply dummy points
                if dummy_settings.enabled:
                    dc = self._apply_dummy_points(dc, dummy_settings)
                
                dispersion_curves.append(dc)
                
            elif curve_data.curve_type == CurveType.HV_CURVE:
                if curve_data.filepath:
                    hv_curve = HVCurve.from_file(curve_data.filepath)
                    
                    # Apply HV curve stddev processing
                    if curve_data.stddev_mode == "fixed_cov":
                        hv_curve = self._apply_hv_stddev(hv_curve, curve_data)
                    
            elif curve_data.curve_type == CurveType.HV_PEAK:
                if curve_data.peak_freq is not None:
                    hv_peak = HVPeak(
                        frequency=curve_data.peak_freq,
                        stddev=curve_data.peak_stddev
                    )
        
        # Create config with weights
        config = TargetConfig(
            dispersion_selected=len(dispersion_curves) > 0,
            dispersion_weight=weight_settings.dispersion,
            ellipticity_selected=hv_curve is not None,
            ellipticity_weight=weight_settings.hv_curve,
            hv_peak_selected=hv_peak is not None,
            hv_peak_weight=weight_settings.hv_peak
        )
        
        # Write target file
        writer = TargetWriter(config)
        writer.write(
            output_path,
            hv_curve=hv_curve,
            hv_peak=hv_peak,
            dispersion_curves=dispersion_curves if dispersion_curves else None
        )
    
    def _apply_stddev(self, curve, settings):
        """Apply stddev settings to a curve (from global override)."""
        if settings.mode == "fixed_logstd":
            curve.set_fixed_logstd(settings.fixed_logstd)
        elif settings.mode == "fixed_cov":
            curve.set_fixed_cov(settings.fixed_cov)
        
        if settings.use_min_cov:
            curve.set_min_cov(settings.min_cov)
        
        return curve
    
    def _apply_curve_stddev(self, curve, curve_data: CurveData):
        """Apply stddev settings from per-curve CurveData."""
        if curve_data.stddev_mode == "fixed_logstd":
            curve.set_fixed_logstd(curve_data.fixed_logstd)
        elif curve_data.stddev_mode == "fixed_cov":
            curve.set_fixed_cov(curve_data.fixed_cov)
        
        if curve_data.use_min_cov:
            curve.set_min_cov(curve_data.min_cov)
        
        return curve
    
    def _apply_curve_resampling(self, curve, curve_data: CurveData):
        """Apply resampling settings from per-curve CurveData."""
        from sw_dcml.dinver.target.target_new.resample import resample_dispersion_curve
        
        fmin = curve_data.resample_fmin if curve_data.resample_fmin else float(curve.frequency.min())
        fmax = curve_data.resample_fmax if curve_data.resample_fmax else float(curve.frequency.max())
        
        return resample_dispersion_curve(
            curve,
            pmin=fmin,
            pmax=fmax,
            pn=curve_data.resample_npoints,
            res_type=curve_data.resample_method
        )
    
    def _apply_resampling(self, curve, settings):
        """Apply resampling settings to a curve."""
        from sw_dcml.dinver.target.target_new.resample import resample_dispersion_curve
        
        fmin = settings.fmin if settings.fmin else float(curve.frequency.min())
        fmax = settings.fmax if settings.fmax else float(curve.frequency.max())
        
        return resample_dispersion_curve(
            curve,
            pmin=fmin,
            pmax=fmax,
            pn=settings.npoints,
            res_type=settings.method
        )
    
    def _apply_dummy_points(self, curve, settings):
        """Apply dummy points settings to a curve."""
        import numpy as np
        
        if settings.mode == "extend":
            dummy_freqs = []
            dummy_vels = []
            
            if settings.extend_low:
                low_vel = curve.velocity[np.argmin(curve.frequency)]
                for f in np.linspace(settings.extend_low, float(curve.frequency.min()) * 0.9, 3):
                    dummy_freqs.append(f)
                    dummy_vels.append(low_vel * 1.1)
            
            if settings.extend_high:
                high_vel = curve.velocity[np.argmax(curve.frequency)]
                for f in np.linspace(float(curve.frequency.max()) * 1.1, settings.extend_high, 3):
                    dummy_freqs.append(f)
                    dummy_vels.append(high_vel * 0.95)
            
            if dummy_freqs:
                curve.add_dummy_points(dummy_freqs, dummy_vels)
        
        elif settings.mode == "custom" and settings.custom_freqs and settings.custom_vels:
            try:
                freqs = [float(x.strip()) for x in settings.custom_freqs.split(',')]
                vels = [float(x.strip()) for x in settings.custom_vels.split(',')]
                if len(freqs) == len(vels):
                    curve.add_dummy_points(freqs, vels)
            except ValueError:
                pass
        
        return curve
    
    def _apply_hv_stddev(self, hv_curve, curve_data: CurveData):
        """Apply stddev settings to HV curve."""
        import numpy as np
        
        # Set fixed stddev
        if curve_data.stddev_mode == "fixed_cov":
            hv_curve.stddev = np.full_like(hv_curve.stddev, curve_data.fixed_cov)
        
        # Apply minimum stddev
        if curve_data.use_min_cov:
            hv_curve.stddev = np.maximum(hv_curve.stddev, curve_data.min_cov)
        
        return hv_curve
