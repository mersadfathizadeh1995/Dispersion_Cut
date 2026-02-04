"""Configuration and data models for theoretical dispersion curves."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List
import numpy as np


@dataclass
class TheoreticalCurveStyle:
    """Visual style settings for a theoretical curve."""
    
    median_color: str = "#E41A1C"
    median_linewidth: float = 2.0
    median_linestyle: str = "-"
    median_alpha: float = 1.0
    
    band_color: str = "#999999"
    band_alpha: float = 0.3


@dataclass
class TheoreticalCurve:
    """A single theoretical dispersion curve with statistics.
    
    Attributes
    ----------
    name : str
        Display name for the curve (e.g., "MySite_Rayleigh_mode0")
    source_file : str
        Path to the source CSV file
    wave_type : str
        Wave type: "Rayleigh" or "Love"
    mode : int
        Mode number (0 = fundamental, 1+ = higher modes)
    frequencies : np.ndarray
        Frequency values in Hz
    median : np.ndarray
        Median phase velocity (m/s)
    lower : np.ndarray
        Lower percentile velocity (m/s)
    upper : np.ndarray
        Upper percentile velocity (m/s)
    std : np.ndarray
        Standard deviation
    """
    
    name: str
    source_file: str
    wave_type: str
    mode: int
    frequencies: np.ndarray
    median: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    std: np.ndarray
    
    # Visibility state
    visible: bool = True
    median_visible: bool = True
    band_visible: bool = True
    
    # Style settings
    style: TheoreticalCurveStyle = field(default_factory=TheoreticalCurveStyle)
    
    # Matplotlib artists (for removal/update)
    _median_line_freq: Optional[object] = field(default=None, repr=False)
    _median_line_wave: Optional[object] = field(default=None, repr=False)
    _band_fill_freq: Optional[object] = field(default=None, repr=False)
    _band_fill_wave: Optional[object] = field(default=None, repr=False)
    
    @property
    def wavelengths(self) -> np.ndarray:
        """Calculate wavelengths from frequency and median velocity."""
        with np.errstate(divide='ignore', invalid='ignore'):
            wl = self.median / self.frequencies
            wl[~np.isfinite(wl)] = np.nan
        return wl
    
    @property
    def curve_id(self) -> str:
        """Unique identifier for this curve."""
        return f"{self.name}_mode{self.mode}"


@dataclass
class GenerationConfig:
    """Configuration for generating theoretical curves from Geopsy report.
    
    Attributes
    ----------
    report_file : str
        Path to Geopsy .report file
    output_dir : str
        Output directory for generated CSV files
    geopsy_bin : str
        Path to Geopsy bin directory
    git_bash : str
        Path to Git Bash executable (Windows only)
    selection_mode : str
        "best" or "misfit"
    n_best_profiles : int
        Number of best profiles (for "best" mode)
    misfit_max : float
        Maximum misfit threshold (for "misfit" mode)
    max_profiles : int
        Maximum profiles to extract (for "misfit" mode)
    curve_type : str
        "Rayleigh", "Love", or "Both"
    num_modes : int
        Number of modes to extract
    freq_min : float
        Minimum frequency (Hz)
    freq_max : float
        Maximum frequency (Hz)
    freq_points : int
        Number of frequency points
    site_name : str
        Site name for output files
    lower_percentile : float
        Lower percentile for uncertainty band
    upper_percentile : float
        Upper percentile for uncertainty band
    """
    
    report_file: str = ""
    output_dir: str = ""
    geopsy_bin: str = r"C:\Geopsy.org\bin"
    git_bash: str = r"C:\Users\mersadf\AppData\Local\Programs\Git\bin\bash.exe"
    
    selection_mode: str = "misfit"
    n_best_profiles: int = 1000
    misfit_max: float = 1.0
    max_profiles: int = 10000
    
    curve_type: str = "Rayleigh"
    num_modes: int = 1
    
    freq_min: float = 1.0
    freq_max: float = 50.0
    freq_points: int = 200
    
    site_name: str = "Site"
    lower_percentile: float = 16.0
    upper_percentile: float = 84.0
