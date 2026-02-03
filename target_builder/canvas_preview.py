"""
Canvas Preview Window
=====================

Matplotlib-based preview window for visualizing curve data.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QPushButton, QComboBox, QLabel, QToolBar,
    QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt
from typing import List, Dict, Optional
import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from .curve_tree import CurveData, CurveType


class CanvasPreviewWindow(QMainWindow):
    """Floating window with matplotlib canvas for data preview."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: Dict[str, CurveData] = {}
        self._curve_objects: Dict[str, any] = {}  # Loaded curve objects
        self._visible_curves: Dict[str, bool] = {}
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle("Data Preview")
        self.setMinimumSize(800, 600)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Curve visibility checkboxes container
        self.curves_group = QGroupBox("Show Curves")
        self.curves_layout = QVBoxLayout(self.curves_group)
        controls_layout.addWidget(self.curves_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.uncertainty_cb = QCheckBox("Show uncertainty bands")
        self.uncertainty_cb.setChecked(True)
        self.uncertainty_cb.toggled.connect(self._update_plot)
        options_layout.addWidget(self.uncertainty_cb)
        
        self.log_scale_cb = QCheckBox("Log frequency scale")
        self.log_scale_cb.setChecked(True)
        self.log_scale_cb.toggled.connect(self._update_plot)
        options_layout.addWidget(self.log_scale_cb)
        
        controls_layout.addWidget(options_group)
        controls_layout.addStretch()
        
        # Export button
        export_btn = QPushButton("Export Plot...")
        export_btn.clicked.connect(self._export_plot)
        controls_layout.addWidget(export_btn)
        
        layout.addLayout(controls_layout)
    
    def set_curves(self, curves: List[CurveData]):
        """Set the curves to display."""
        self._curves.clear()
        self._curve_objects.clear()
        self._visible_curves.clear()
        
        # Clear curve checkboxes
        while self.curves_layout.count():
            item = self.curves_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Load curves and create checkboxes
        for curve_data in curves:
            if not curve_data.filepath and curve_data.curve_type != CurveType.HV_PEAK:
                continue
            
            uid = curve_data.uid
            self._curves[uid] = curve_data
            self._visible_curves[uid] = True
            
            # Load curve object
            self._load_curve_object(curve_data)
            
            # Create checkbox
            cb = QCheckBox(self._get_curve_label(curve_data))
            cb.setChecked(True)
            cb.toggled.connect(lambda checked, u=uid: self._on_visibility_changed(u, checked))
            self.curves_layout.addWidget(cb)
        
        self._update_plot()
    
    def _get_curve_label(self, data: CurveData) -> str:
        """Get display label for curve."""
        if data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
            return f"{data.name} (M{data.mode})"
        elif data.curve_type == CurveType.HV_CURVE:
            return "HV Curve"
        elif data.curve_type == CurveType.HV_PEAK:
            return f"HV Peak ({data.peak_freq:.1f} Hz)"
        return data.name
    
    def _load_curve_object(self, data: CurveData):
        """Load the actual curve object from file (uses working file if available)."""
        # Use working file if available, otherwise original
        filepath = data.working_filepath or data.filepath
        if not filepath:
            return
        
        try:
            if data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
                from sw_dcml.dinver.target.target_new.models import DispersionCurve
                polarization = 'love' if data.curve_type == CurveType.LOVE else 'rayleigh'
                curve = DispersionCurve.from_file(
                    filepath,
                    polarization=polarization,
                    mode=data.mode,
                    stddev_type=data.stddev_type
                )
                
                # Apply processing settings from CurveData
                curve = self._apply_dispersion_processing(curve, data)
                self._curve_objects[data.uid] = curve
                
            elif data.curve_type == CurveType.HV_CURVE:
                from sw_dcml.dinver.target.target_new.models import HVCurve
                curve = HVCurve.from_file(data.filepath)
                
                # Apply HV processing settings
                curve = self._apply_hv_processing(curve, data)
                self._curve_objects[data.uid] = curve
                
        except Exception as e:
            print(f"Error loading curve {data.name}: {e}")
    
    def _apply_dispersion_processing(self, curve, data: CurveData):
        """Apply processing settings to dispersion curve."""
        # Apply global stddev settings first
        if data.stddev_mode == "fixed_logstd":
            curve.set_fixed_logstd(data.fixed_logstd)
        elif data.stddev_mode == "fixed_cov":
            curve.set_fixed_cov(data.fixed_cov)
        
        # Apply multiple custom frequency ranges (override global in those ranges)
        if data.stddev_freq_ranges:
            for fr in data.stddev_freq_ranges:
                self._apply_stddev_in_range(
                    curve, "cov", fr['value'],
                    fr['freq_min'], fr['freq_max']
                )
        
        if data.use_min_cov:
            curve.set_min_cov(data.min_cov)
        
        # Apply resampling if enabled
        if data.resample_enabled:
            from sw_dcml.dinver.target.target_new.resample import resample_dispersion_curve
            fmin = data.resample_fmin if data.resample_fmin else float(curve.frequency.min())
            fmax = data.resample_fmax if data.resample_fmax else float(curve.frequency.max())
            curve = resample_dispersion_curve(
                curve, pmin=fmin, pmax=fmax,
                pn=data.resample_npoints, res_type=data.resample_method
            )
        
        return curve
    
    def _apply_stddev_in_range(self, curve, mode: str, value: float, fmin: float, fmax: float):
        """Apply stddev only to points within frequency range."""
        mask = (curve.frequency >= fmin) & (curve.frequency <= fmax)
        
        if mode == "logstd":
            # Convert logstd to COV first
            cov = value - np.sqrt(value**2 - 2*value + 2)
            new_velstd = curve.velocity * cov
        else:  # cov
            new_velstd = curve.velocity * value
        
        # Apply only to masked points
        curve.velstd[mask] = new_velstd[mask]
    
    def _apply_hv_processing(self, curve, data: CurveData):
        """Apply processing settings to HV curve."""
        if data.stddev_mode == "fixed_cov":
            curve.stddev = np.full_like(curve.stddev, data.fixed_cov)
        
        if data.use_min_cov:
            curve.stddev = np.maximum(curve.stddev, data.min_cov)
        
        return curve
    
    def _on_visibility_changed(self, uid: str, visible: bool):
        """Handle curve visibility change."""
        self._visible_curves[uid] = visible
        self._update_plot()
    
    def _update_plot(self):
        """Update the plot with current curves."""
        self.ax.clear()
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        color_idx = 0
        
        has_dispersion = False
        has_hvsr = False
        
        for uid, visible in self._visible_curves.items():
            if not visible:
                continue
            
            data = self._curves.get(uid)
            curve = self._curve_objects.get(uid)
            
            if not data or not curve:
                continue
            
            color = colors[color_idx % len(colors)]
            color_idx += 1
            
            if data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
                has_dispersion = True
                self._plot_dispersion(curve, data, color)
                
            elif data.curve_type == CurveType.HV_CURVE:
                has_hvsr = True
                self._plot_hv_curve(curve, data, color)
        
        # Configure axes
        if has_dispersion and not has_hvsr:
            self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_ylabel("Velocity (m/s)")
            self.ax.set_title("Dispersion Curves")
        elif has_hvsr and not has_dispersion:
            self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_ylabel("H/V Ratio")
            self.ax.set_title("HVSR Curve")
        else:
            self.ax.set_xlabel("Frequency (Hz)")
            self.ax.set_ylabel("Value")
            self.ax.set_title("Data Preview")
        
        if self.log_scale_cb.isChecked():
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')
        
        self.ax.legend(loc='best')
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _plot_dispersion(self, curve, data: CurveData, color: str):
        """Plot a dispersion curve."""
        freq = curve.frequency
        vel = curve.velocity
        
        label = self._get_curve_label(data)
        self.ax.plot(freq, vel, '-', color=color, label=label, linewidth=1.5)
        
        if self.uncertainty_cb.isChecked():
            try:
                velstd = curve.velstd
                if velstd is not None and len(velstd) == len(freq):
                    self.ax.fill_between(
                        freq, vel - velstd, vel + velstd,
                        color=color, alpha=0.2
                    )
            except Exception:
                pass
    
    def _plot_hv_curve(self, curve, data: CurveData, color: str):
        """Plot an HV curve."""
        freq = curve.frequency
        hv = curve.hv_ratio
        
        label = "HV Curve"
        self.ax.plot(freq, hv, '-', color=color, label=label, linewidth=1.5)
        
        if self.uncertainty_cb.isChecked():
            try:
                stddev = curve.stddev
                if stddev is not None and len(stddev) == len(freq):
                    self.ax.fill_between(
                        freq, hv - stddev, hv + stddev,
                        color=color, alpha=0.2
                    )
            except Exception:
                pass
    
    def _export_plot(self):
        """Export the plot to a file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Plot", "",
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Image (*.svg)"
        )
        if filepath:
            self.figure.savefig(filepath, dpi=150, bbox_inches='tight')
