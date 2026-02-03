"""
Target Loader
=============

Load existing .target files and convert to CurveData objects for the curve tree.
"""

import tempfile
import os
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

from .curve_tree import CurveData, CurveType


def load_target_file(target_path: str) -> Tuple[List[CurveData], dict]:
    """
    Load a .target file and convert to list of CurveData objects.
    
    Args:
        target_path: Path to the .target file
        
    Returns:
        Tuple of (list of CurveData objects, summary dict)
    """
    from sw_dcml.dinver.target.reader import read_target
    
    config = read_target(target_path)
    
    curves = []
    summary = {
        'site_name': config.site_name,
        'rayleigh_count': 0,
        'love_count': 0,
        'hv_curve': False,
        'hv_peak': False,
        'dispersion_weight': config.dispersion_weight,
        'hv_curve_weight': config.hv_curve_weight,
        'hv_peak_weight': config.hv_peak_weight,
    }
    
    # Process dispersion curves
    for disp_curve in config.dispersion_curves:
        curve_data = _convert_dispersion_curve(disp_curve)
        if curve_data:
            curves.append(curve_data)
            if disp_curve.wave_type == 'Rayleigh':
                summary['rayleigh_count'] += 1
            elif disp_curve.wave_type == 'Love':
                summary['love_count'] += 1
    
    # Process HV curve
    if config.hv_curve is not None:
        hv_curve_data = _convert_hv_curve(config.hv_curve)
        if hv_curve_data:
            curves.append(hv_curve_data)
            summary['hv_curve'] = True
    
    # Process HV peak
    if config.hv_peak is not None:
        hv_peak_data = _convert_hv_peak(config.hv_peak)
        if hv_peak_data:
            curves.append(hv_peak_data)
            summary['hv_peak'] = True
    
    return curves, summary


def _convert_dispersion_curve(disp_curve) -> Optional[CurveData]:
    """
    Convert a DispersionCurve from reader to CurveData.
    
    Creates a temporary file with the curve data.
    """
    if not disp_curve.points:
        return None
    
    # Determine curve type
    if disp_curve.wave_type == 'Rayleigh':
        curve_type = CurveType.RAYLEIGH
    elif disp_curve.wave_type == 'Love':
        curve_type = CurveType.LOVE
    else:
        return None
    
    # Extract data arrays
    frequencies = np.array([pt.frequency for pt in disp_curve.points])
    slowness = np.array([pt.slowness for pt in disp_curve.points])
    stddev = np.array([pt.stddev for pt in disp_curve.points])
    
    # Calculate velocity from slowness (handle zero slowness)
    with np.errstate(divide='ignore', invalid='ignore'):
        velocities = np.where(slowness != 0, 1.0 / slowness, 0.0)
    
    # Create temporary file with dispersion data
    # Format: frequency, slowness, logstd (for compatibility with existing readers)
    temp_dir = tempfile.mkdtemp(prefix="target_loader_")
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in disp_curve.name)
    temp_file = os.path.join(temp_dir, f"{safe_name}.txt")
    
    with open(temp_file, 'w') as f:
        f.write(f"# Loaded from target file: {disp_curve.name}\n")
        f.write(f"# Wave type: {disp_curve.wave_type}, Mode: {disp_curve.mode}\n")
        f.write(f"# Points: {len(frequencies)}\n")
        f.write("# Frequency(Hz)  Slowness(s/m)  LogStd\n")
        for freq, slow, std in zip(frequencies, slowness, stddev):
            f.write(f"{freq:.6f}  {slow:.10f}  {std:.6f}\n")
    
    # Create CurveData
    curve_data = CurveData(
        curve_type=curve_type,
        filepath=temp_file,
        name=disp_curve.name,
        mode=disp_curve.mode,
        stddev_type="logstd",
        n_points=len(frequencies),
        freq_min=float(frequencies.min()),
        freq_max=float(frequencies.max()),
        included=disp_curve.enabled,
        # Default processing settings
        stddev_mode="file",  # Use stddev from file
    )
    
    return curve_data


def _convert_hv_curve(hv_curve) -> Optional[CurveData]:
    """
    Convert an HVCurve from reader to CurveData.
    
    Creates a temporary file with the curve data.
    """
    if not hv_curve.points:
        return None
    
    # Extract data arrays
    frequencies = np.array([pt.frequency for pt in hv_curve.points])
    hv_ratios = np.array([pt.hv_ratio for pt in hv_curve.points])
    stddev = np.array([pt.stddev for pt in hv_curve.points])
    
    # Create temporary file with HV data
    # Format: frequency, hv_ratio, stddev
    temp_dir = tempfile.mkdtemp(prefix="target_loader_hv_")
    temp_file = os.path.join(temp_dir, "hv_curve.txt")
    
    with open(temp_file, 'w') as f:
        f.write(f"# HV Curve loaded from target file\n")
        f.write(f"# Name: {hv_curve.name}\n")
        f.write(f"# Points: {len(frequencies)}\n")
        f.write("# Frequency(Hz)  HVSR  StdDev\n")
        for freq, hv, std in zip(frequencies, hv_ratios, stddev):
            f.write(f"{freq:.6f}  {hv:.6f}  {std:.6f}\n")
    
    # Create CurveData
    curve_data = CurveData(
        curve_type=CurveType.HV_CURVE,
        filepath=temp_file,
        name=hv_curve.name,
        n_points=len(frequencies),
        freq_min=float(frequencies.min()),
        freq_max=float(frequencies.max()),
        included=hv_curve.enabled,
    )
    
    return curve_data


def _convert_hv_peak(hv_peak) -> Optional[CurveData]:
    """
    Convert an HVPeak from reader to CurveData.
    """
    if hv_peak.f0 is None or hv_peak.f0 == 0:
        return None
    
    # Create CurveData for HV Peak (no file needed)
    curve_data = CurveData(
        curve_type=CurveType.HV_PEAK,
        filepath=None,
        name="HV Peak",
        peak_freq=hv_peak.f0,
        peak_stddev=hv_peak.f0_stddev,
        included=hv_peak.enabled,
    )
    
    return curve_data


def get_target_summary(target_path: str) -> dict:
    """
    Get a summary of what's in a target file without fully loading it.
    
    Args:
        target_path: Path to the .target file
        
    Returns:
        Dictionary with summary info
    """
    from sw_dcml.dinver.target.reader import get_target_summary as _get_summary
    return _get_summary(target_path)
