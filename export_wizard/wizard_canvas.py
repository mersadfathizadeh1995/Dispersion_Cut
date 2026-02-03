"""
Wizard Canvas
=============

Matplotlib canvas for curve visualization in the export wizard.
"""

from typing import Optional, Tuple
import numpy as np

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
Signal = QtCore.Signal

from .data_model import CurveDataModel


class WizardCanvas(QtWidgets.QWidget):
    """
    Matplotlib canvas for displaying dispersion curve.
    
    Features:
    - Curve with optional uncertainty bands
    - Log/linear frequency scale
    - Zoom and pan navigation
    - Click-to-select points
    """
    
    point_clicked = Signal(int)  # Emits index of clicked point
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model: Optional[CurveDataModel] = None
        self._line: Optional[Line2D] = None
        self._scatter = None
        self._uncertainty_fill = None
        self._selected_idx: Optional[int] = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Controls row
        controls = QtWidgets.QHBoxLayout()
        
        # X-axis mode
        controls.addWidget(QtWidgets.QLabel("X-axis:"))
        self.x_mode_combo = QtWidgets.QComboBox()
        self.x_mode_combo.addItems(["Frequency (Hz)", "Wavelength (m)"])
        controls.addWidget(self.x_mode_combo)
        
        # Scale
        self.log_scale_cb = QtWidgets.QCheckBox("Log Scale")
        self.log_scale_cb.setChecked(True)
        controls.addWidget(self.log_scale_cb)
        
        # Uncertainty
        self.show_uncertainty_cb = QtWidgets.QCheckBox("Show Uncertainty")
        self.show_uncertainty_cb.setChecked(True)
        controls.addWidget(self.show_uncertainty_cb)
        
        controls.addStretch()
        layout.addLayout(controls)
        
        # Matplotlib figure
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Navigation toolbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self._setup_plot()
    
    def _setup_plot(self):
        """Initialize plot styling."""
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Velocity (m/s)")
        self.ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
    
    def _connect_signals(self):
        self.x_mode_combo.currentIndexChanged.connect(self._on_display_changed)
        self.log_scale_cb.toggled.connect(self._on_display_changed)
        self.show_uncertainty_cb.toggled.connect(self._on_display_changed)
        self.canvas.mpl_connect('button_press_event', self._on_click)
    
    def set_model(self, model: CurveDataModel):
        """Set the curve data model."""
        self._model = model
        self.update_plot()
    
    def update_plot(self):
        """Redraw the plot with current data and settings."""
        self.ax.clear()
        
        if self._model is None or self._model.n_points == 0:
            self.ax.text(0.5, 0.5, "No data", ha='center', va='center',
                        transform=self.ax.transAxes, fontsize=14, color='gray')
            self.canvas.draw_idle()
            return
        
        # Get display settings
        use_wavelength = self.x_mode_combo.currentIndex() == 1
        use_log = self.log_scale_cb.isChecked()
        show_uncert = self.show_uncertainty_cb.isChecked()
        
        # Get data
        if use_wavelength:
            x = self._model.wavelength
            xlabel = "Wavelength (m)"
        else:
            x = self._model.frequency
            xlabel = "Frequency (Hz)"
        
        y = self._model.velocity
        
        # Plot uncertainty band
        if show_uncert and np.any(self._model.uncertainty_velocity > 0):
            y_low = y - self._model.uncertainty_velocity
            y_high = y + self._model.uncertainty_velocity
            self._uncertainty_fill = self.ax.fill_between(
                x, y_low, y_high, alpha=0.3, color='blue', label='Uncertainty'
            )
        
        # Plot curve
        self._line, = self.ax.plot(x, y, 'b-', linewidth=1.5, label='Curve')
        
        # Plot points
        self._scatter = self.ax.scatter(x, y, c='blue', s=30, zorder=5)
        
        # Highlight selected point
        if self._selected_idx is not None and 0 <= self._selected_idx < len(x):
            self.ax.scatter([x[self._selected_idx]], [y[self._selected_idx]], 
                           c='red', s=100, zorder=10, marker='o', edgecolors='black')
        
        # Set scale
        if use_log:
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')
        
        # Labels
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel("Velocity (m/s)")
        self.ax.grid(True, alpha=0.3)
        
        # Title with point count
        self.ax.set_title(f"{self._model.name} ({self._model.n_points} points)")
        
        self.figure.tight_layout()
        self.canvas.draw_idle()
    
    def _on_display_changed(self):
        """Handle display option changes."""
        self.update_plot()
    
    def _on_click(self, event):
        """Handle mouse click on canvas."""
        if event.inaxes != self.ax or self._model is None:
            return
        
        # Find nearest point
        use_wavelength = self.x_mode_combo.currentIndex() == 1
        if use_wavelength:
            x_data = self._model.wavelength
        else:
            x_data = self._model.frequency
        y_data = self._model.velocity
        
        if len(x_data) == 0:
            return
        
        # Transform to display coordinates
        x_click = event.xdata
        y_click = event.ydata
        
        if x_click is None or y_click is None:
            return
        
        # Calculate distances (normalized)
        x_range = x_data.max() - x_data.min()
        y_range = y_data.max() - y_data.min()
        
        if x_range == 0:
            x_range = 1
        if y_range == 0:
            y_range = 1
        
        dx = (x_data - x_click) / x_range
        dy = (y_data - y_click) / y_range
        distances = np.sqrt(dx**2 + dy**2)
        
        nearest_idx = np.argmin(distances)
        
        # Only select if close enough (within 5% of plot range)
        if distances[nearest_idx] < 0.1:
            self._selected_idx = nearest_idx
            self.point_clicked.emit(nearest_idx)
            self.update_plot()
    
    def select_point(self, index: int):
        """Select a point by index."""
        self._selected_idx = index
        self.update_plot()
    
    def clear_selection(self):
        """Clear point selection."""
        self._selected_idx = None
        self.update_plot()
    
    def get_click_position(self) -> Optional[Tuple[float, float]]:
        """Get the last click position in data coordinates."""
        # This would be used for add-point-on-click functionality
        pass
