"""
Data Model for Export Wizard
============================

Core data structures for curve representation and manipulation.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import numpy as np
from pathlib import Path


@dataclass
class ColumnConfig:
    """Configuration for a data column."""
    name: str
    display_name: str
    editable: bool = True
    visible: bool = True
    format_str: str = "{:.4f}"
    unit: str = ""
    
    def format_value(self, value: float) -> str:
        """Format a value for display."""
        try:
            return self.format_str.format(value)
        except (ValueError, TypeError):
            return str(value)


@dataclass
class CurveDataModel:
    """
    Data model for a dispersion curve.
    
    Stores frequency, velocity, wavelength, and uncertainty data.
    Supports dynamic columns and various uncertainty formats.
    """
    frequency: np.ndarray = field(default_factory=lambda: np.array([]))
    velocity: np.ndarray = field(default_factory=lambda: np.array([]))
    wavelength: np.ndarray = field(default_factory=lambda: np.array([]))
    uncertainty_velocity: np.ndarray = field(default_factory=lambda: np.array([]))
    uncertainty_cov: np.ndarray = field(default_factory=lambda: np.array([]))
    uncertainty_logstd: np.ndarray = field(default_factory=lambda: np.array([]))
    
    # Column configuration
    columns: List[ColumnConfig] = field(default_factory=list)
    
    # Metadata
    source_file: Optional[str] = None
    name: str = "Curve"
    
    def __post_init__(self):
        """Initialize default columns if not set."""
        if not self.columns:
            self.columns = self._default_columns()
        self._ensure_arrays()
    
    def _default_columns(self) -> List[ColumnConfig]:
        """Return default column configuration."""
        return [
            ColumnConfig("frequency", "Frequency", True, True, "{:.4f}", "Hz"),
            ColumnConfig("velocity", "Velocity", True, True, "{:.2f}", "m/s"),
            ColumnConfig("wavelength", "Wavelength", True, True, "{:.2f}", "m"),
            ColumnConfig("slowness", "Slowness", False, False, "{:.6f}", "s/km"),
            ColumnConfig("uncertainty_velocity", "Uncert. (m/s)", True, True, "{:.2f}", "m/s"),
            ColumnConfig("uncertainty_cov", "COV", True, True, "{:.4f}", ""),
            ColumnConfig("uncertainty_logstd", "LogStd", True, False, "{:.4f}", ""),
        ]
    
    def _ensure_arrays(self):
        """Ensure all arrays have consistent length."""
        n = len(self.frequency)
        if len(self.velocity) != n:
            self.velocity = np.zeros(n)
        if len(self.wavelength) != n:
            self.wavelength = self.velocity / np.maximum(self.frequency, 1e-10)
        if len(self.uncertainty_velocity) != n:
            self.uncertainty_velocity = np.zeros(n)
        if len(self.uncertainty_cov) != n:
            self.uncertainty_cov = np.zeros(n)
        if len(self.uncertainty_logstd) != n:
            self.uncertainty_logstd = np.ones(n) * 1.1
    
    @property
    def n_points(self) -> int:
        """Number of data points."""
        return len(self.frequency)
    
    @property
    def slowness(self) -> np.ndarray:
        """Slowness in s/km (derived from velocity)."""
        return 1000.0 / np.maximum(self.velocity, 1e-10)
    
    def get_column_data(self, column_name: str) -> np.ndarray:
        """Get data for a specific column."""
        if column_name == "frequency":
            return self.frequency
        elif column_name == "velocity":
            return self.velocity
        elif column_name == "wavelength":
            return self.wavelength
        elif column_name == "slowness":
            return self.slowness
        elif column_name == "uncertainty_velocity":
            return self.uncertainty_velocity
        elif column_name == "uncertainty_cov":
            return self.uncertainty_cov
        elif column_name == "uncertainty_logstd":
            return self.uncertainty_logstd
        else:
            raise ValueError(f"Unknown column: {column_name}")
    
    def set_value(self, row: int, column_name: str, value: float):
        """Set a single value and update derived columns."""
        if column_name == "frequency":
            self.frequency[row] = value
            # Recalculate wavelength
            if self.velocity[row] > 0:
                self.wavelength[row] = self.velocity[row] / max(value, 1e-10)
        elif column_name == "velocity":
            self.velocity[row] = value
            # Recalculate wavelength and update COV
            if self.frequency[row] > 0:
                self.wavelength[row] = value / self.frequency[row]
            if self.uncertainty_velocity[row] > 0:
                self.uncertainty_cov[row] = self.uncertainty_velocity[row] / max(value, 1e-10)
        elif column_name == "wavelength":
            self.wavelength[row] = value
            # Recalculate velocity
            self.velocity[row] = value * self.frequency[row]
        elif column_name == "uncertainty_velocity":
            self.uncertainty_velocity[row] = value
            self.uncertainty_cov[row] = value / max(self.velocity[row], 1e-10)
            self.uncertainty_logstd[row] = 1.0 + self.uncertainty_cov[row]
        elif column_name == "uncertainty_cov":
            self.uncertainty_cov[row] = value
            self.uncertainty_velocity[row] = value * self.velocity[row]
            self.uncertainty_logstd[row] = 1.0 + value
        elif column_name == "uncertainty_logstd":
            self.uncertainty_logstd[row] = value
            self.uncertainty_cov[row] = value - 1.0
            self.uncertainty_velocity[row] = self.uncertainty_cov[row] * self.velocity[row]
    
    def add_point(self, f: float, v: float, uncert_v: float = 0.0):
        """Add a new point to the curve."""
        w = v / max(f, 1e-10)
        cov = uncert_v / max(v, 1e-10) if v > 0 else 0.0
        logstd = 1.0 + cov
        
        self.frequency = np.append(self.frequency, f)
        self.velocity = np.append(self.velocity, v)
        self.wavelength = np.append(self.wavelength, w)
        self.uncertainty_velocity = np.append(self.uncertainty_velocity, uncert_v)
        self.uncertainty_cov = np.append(self.uncertainty_cov, cov)
        self.uncertainty_logstd = np.append(self.uncertainty_logstd, logstd)
        
        # Sort by frequency
        self.sort_by_frequency()
    
    def remove_point(self, index: int):
        """Remove a point by index."""
        if 0 <= index < self.n_points:
            self.frequency = np.delete(self.frequency, index)
            self.velocity = np.delete(self.velocity, index)
            self.wavelength = np.delete(self.wavelength, index)
            self.uncertainty_velocity = np.delete(self.uncertainty_velocity, index)
            self.uncertainty_cov = np.delete(self.uncertainty_cov, index)
            self.uncertainty_logstd = np.delete(self.uncertainty_logstd, index)
    
    def sort_by_frequency(self):
        """Sort all arrays by frequency (ascending)."""
        if self.n_points == 0:
            return
        order = np.argsort(self.frequency)
        self.frequency = self.frequency[order]
        self.velocity = self.velocity[order]
        self.wavelength = self.wavelength[order]
        self.uncertainty_velocity = self.uncertainty_velocity[order]
        self.uncertainty_cov = self.uncertainty_cov[order]
        self.uncertainty_logstd = self.uncertainty_logstd[order]
    
    def resample(self, n_points: int, method: str = "log", 
                 fmin: Optional[float] = None, fmax: Optional[float] = None):
        """
        Resample the curve to a new number of points.
        
        Args:
            n_points: Target number of points
            method: 'log' for logarithmic spacing, 'linear' for linear
            fmin: Minimum frequency (defaults to data min)
            fmax: Maximum frequency (defaults to data max)
        """
        if self.n_points < 2:
            return
        
        fmin = fmin or self.frequency.min()
        fmax = fmax or self.frequency.max()
        
        if method == "log":
            new_freq = np.logspace(np.log10(fmin), np.log10(fmax), n_points)
        else:
            new_freq = np.linspace(fmin, fmax, n_points)
        
        # Interpolate velocity
        new_vel = np.interp(new_freq, self.frequency, self.velocity)
        
        # Interpolate uncertainty (use COV for interpolation, then convert)
        new_cov = np.interp(new_freq, self.frequency, self.uncertainty_cov)
        
        # Update arrays
        self.frequency = new_freq
        self.velocity = new_vel
        self.wavelength = new_vel / np.maximum(new_freq, 1e-10)
        self.uncertainty_cov = new_cov
        self.uncertainty_velocity = new_cov * new_vel
        self.uncertainty_logstd = 1.0 + new_cov
    
    def apply_fixed_cov(self, cov: float):
        """Apply a fixed coefficient of variation to all points."""
        self.uncertainty_cov = np.full(self.n_points, cov)
        self.uncertainty_velocity = self.uncertainty_cov * self.velocity
        self.uncertainty_logstd = 1.0 + self.uncertainty_cov
    
    def apply_fixed_logstd(self, logstd: float):
        """Apply a fixed log standard deviation to all points."""
        self.uncertainty_logstd = np.full(self.n_points, logstd)
        self.uncertainty_cov = self.uncertainty_logstd - 1.0
        self.uncertainty_velocity = self.uncertainty_cov * self.velocity
    
    def trim_frequency_range(self, fmin: float, fmax: float):
        """Trim curve to frequency range."""
        mask = (self.frequency >= fmin) & (self.frequency <= fmax)
        self.frequency = self.frequency[mask]
        self.velocity = self.velocity[mask]
        self.wavelength = self.wavelength[mask]
        self.uncertainty_velocity = self.uncertainty_velocity[mask]
        self.uncertainty_cov = self.uncertainty_cov[mask]
        self.uncertainty_logstd = self.uncertainty_logstd[mask]
    
    @classmethod
    def from_arrays(cls, frequency: np.ndarray, velocity: np.ndarray,
                    wavelength: Optional[np.ndarray] = None,
                    uncertainty: Optional[np.ndarray] = None,
                    name: str = "Curve") -> "CurveDataModel":
        """Create from numpy arrays."""
        f = np.asarray(frequency).flatten()
        v = np.asarray(velocity).flatten()
        
        if wavelength is not None:
            w = np.asarray(wavelength).flatten()
        else:
            w = v / np.maximum(f, 1e-10)
        
        if uncertainty is not None:
            u = np.asarray(uncertainty).flatten()
        else:
            u = np.zeros_like(f)
        
        model = cls(
            frequency=f,
            velocity=v,
            wavelength=w,
            uncertainty_velocity=u,
            name=name
        )
        model._ensure_arrays()
        model.sort_by_frequency()
        return model
    
    @classmethod
    def from_file(cls, path: str) -> "CurveDataModel":
        """
        Load curve data from a file (TXT or CSV).
        
        Supports common formats:
        - 2 columns: frequency, velocity
        - 3 columns: frequency, velocity, uncertainty
        - 4 columns: frequency, slowness, logstd_low, logstd_high (Dinver)
        """
        path = Path(path)
        
        try:
            data = np.loadtxt(path, comments='#')
        except Exception:
            # Try with comma delimiter
            data = np.loadtxt(path, delimiter=',', comments='#')
        
        if data.ndim == 1:
            data = data.reshape(1, -1)
        
        n_cols = data.shape[1]
        
        if n_cols == 2:
            # frequency, velocity
            f, v = data[:, 0], data[:, 1]
            u = np.zeros_like(f)
        elif n_cols == 3:
            # frequency, velocity, uncertainty
            f, v, u = data[:, 0], data[:, 1], data[:, 2]
        elif n_cols >= 4:
            # Dinver format: frequency, slowness, logstd_low, logstd_high
            f = data[:, 0]
            slow = data[:, 1]  # s/km
            v = 1000.0 / np.maximum(slow, 1e-10)
            # Average of log std bounds
            logstd = (data[:, 2] + data[:, 3]) / 2.0
            u = (logstd - 1.0) * v  # Convert to velocity uncertainty
        else:
            raise ValueError(f"Unsupported file format with {n_cols} columns")
        
        model = cls.from_arrays(f, v, uncertainty=u, name=path.stem)
        model.source_file = str(path)
        return model
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'frequency': self.frequency.tolist(),
            'velocity': self.velocity.tolist(),
            'wavelength': self.wavelength.tolist(),
            'uncertainty_velocity': self.uncertainty_velocity.tolist(),
            'uncertainty_cov': self.uncertainty_cov.tolist(),
            'uncertainty_logstd': self.uncertainty_logstd.tolist(),
            'name': self.name,
            'source_file': self.source_file,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CurveDataModel":
        """Create from dictionary."""
        return cls(
            frequency=np.array(data.get('frequency', [])),
            velocity=np.array(data.get('velocity', [])),
            wavelength=np.array(data.get('wavelength', [])),
            uncertainty_velocity=np.array(data.get('uncertainty_velocity', [])),
            uncertainty_cov=np.array(data.get('uncertainty_cov', [])),
            uncertainty_logstd=np.array(data.get('uncertainty_logstd', [])),
            name=data.get('name', 'Curve'),
            source_file=data.get('source_file'),
        )
