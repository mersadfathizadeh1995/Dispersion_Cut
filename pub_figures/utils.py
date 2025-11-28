"""Utility functions for publication figures.

This module provides shared utilities:
    - Data validation
    - Array operations
    - File format detection
    - Color utilities
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


def validate_arrays(*arrays: np.ndarray, 
                    names: Optional[List[str]] = None) -> bool:
    """Validate that arrays are non-empty and finite.
    
    Args:
        *arrays: Arrays to validate
        names: Optional names for error messages
        
    Returns:
        True if all valid
        
    Raises:
        ValueError: If validation fails
    """
    names = names or [f'array_{i}' for i in range(len(arrays))]
    
    for arr, name in zip(arrays, names):
        if arr is None:
            raise ValueError(f"{name} is None")
        if len(arr) == 0:
            raise ValueError(f"{name} is empty")
        if not np.all(np.isfinite(arr)):
            n_invalid = np.sum(~np.isfinite(arr))
            logger.warning(f"{name} contains {n_invalid} non-finite values")
    
    return True


def interpolate_curve(
    wavelengths: np.ndarray,
    velocities: np.ndarray,
    target_wavelengths: np.ndarray,
    method: str = 'linear'
) -> np.ndarray:
    """Interpolate dispersion curve to target wavelengths.
    
    Args:
        wavelengths: Original wavelength values
        velocities: Original velocity values
        target_wavelengths: Target wavelength values
        method: Interpolation method ('linear', 'cubic', 'nearest')
        
    Returns:
        Interpolated velocity values
    """
    from scipy.interpolate import interp1d
    
    # Sort by wavelength
    sort_idx = np.argsort(wavelengths)
    wl_sorted = wavelengths[sort_idx]
    vel_sorted = velocities[sort_idx]
    
    # Create interpolator
    if method == 'cubic':
        kind = 'cubic'
    elif method == 'nearest':
        kind = 'nearest'
    else:
        kind = 'linear'
    
    interp_func = interp1d(wl_sorted, vel_sorted, kind=kind,
                          bounds_error=False, fill_value=np.nan)
    
    return interp_func(target_wavelengths)


def compute_residuals(
    reference_wl: np.ndarray,
    reference_vel: np.ndarray,
    comparison_wl: np.ndarray,
    comparison_vel: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute velocity residuals between two dispersion curves.
    
    Args:
        reference_wl: Reference wavelengths
        reference_vel: Reference velocities
        comparison_wl: Comparison wavelengths
        comparison_vel: Comparison velocities
        
    Returns:
        Tuple of (common_wavelengths, residuals)
    """
    # Interpolate comparison to reference wavelengths
    interp_vel = interpolate_curve(comparison_wl, comparison_vel, reference_wl)
    
    # Compute residuals where both are valid
    valid = np.isfinite(interp_vel)
    
    return reference_wl[valid], reference_vel[valid] - interp_vel[valid]


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Convert hex color to RGB tuple (0-1 range).
    
    Args:
        hex_color: Hex color string (e.g., '#FF5733')
        
    Returns:
        Tuple of (R, G, B) values in 0-1 range
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def rgb_to_hex(r: float, g: float, b: float) -> str:
    """Convert RGB tuple (0-1 range) to hex color.
    
    Args:
        r, g, b: RGB values in 0-1 range
        
    Returns:
        Hex color string
    """
    return '#{:02x}{:02x}{:02x}'.format(
        int(r * 255), int(g * 255), int(b * 255)
    )


def lighten_color(hex_color: str, factor: float = 0.3) -> str:
    """Lighten a color by a factor.
    
    Args:
        hex_color: Original hex color
        factor: Lightening factor (0-1)
        
    Returns:
        Lightened hex color
    """
    r, g, b = hex_to_rgb(hex_color)
    r = r + (1 - r) * factor
    g = g + (1 - g) * factor
    b = b + (1 - b) * factor
    return rgb_to_hex(r, g, b)


def darken_color(hex_color: str, factor: float = 0.3) -> str:
    """Darken a color by a factor.
    
    Args:
        hex_color: Original hex color
        factor: Darkening factor (0-1)
        
    Returns:
        Darkened hex color
    """
    r, g, b = hex_to_rgb(hex_color)
    r = r * (1 - factor)
    g = g * (1 - factor)
    b = b * (1 - factor)
    return rgb_to_hex(r, g, b)


def detect_output_format(path: str) -> str:
    """Detect output format from file extension.
    
    Args:
        path: File path
        
    Returns:
        Format string ('pdf', 'png', 'svg', 'eps')
    """
    from pathlib import Path
    
    suffix = Path(path).suffix.lower()
    format_map = {
        '.pdf': 'pdf',
        '.png': 'png',
        '.svg': 'svg',
        '.eps': 'eps',
        '.jpg': 'jpg',
        '.jpeg': 'jpg',
        '.tiff': 'tiff',
        '.tif': 'tiff',
    }
    
    return format_map.get(suffix, 'png')


def format_wavelength(value: float) -> str:
    """Format wavelength value for display.
    
    Args:
        value: Wavelength in meters
        
    Returns:
        Formatted string
    """
    if value < 1:
        return f'{value*100:.1f} cm'
    elif value < 100:
        return f'{value:.1f} m'
    else:
        return f'{value:.0f} m'


def format_velocity(value: float) -> str:
    """Format velocity value for display.
    
    Args:
        value: Velocity in m/s
        
    Returns:
        Formatted string
    """
    if value < 1000:
        return f'{value:.0f} m/s'
    else:
        return f'{value/1000:.2f} km/s'


def format_frequency(value: float) -> str:
    """Format frequency value for display.
    
    Args:
        value: Frequency in Hz
        
    Returns:
        Formatted string
    """
    if value < 1:
        return f'{value*1000:.1f} mHz'
    elif value < 1000:
        return f'{value:.1f} Hz'
    else:
        return f'{value/1000:.2f} kHz'


def compute_statistics(values: np.ndarray) -> Dict[str, float]:
    """Compute comprehensive statistics for an array.
    
    Args:
        values: Input array
        
    Returns:
        Dictionary with statistics
    """
    valid = values[np.isfinite(values)]
    
    if len(valid) == 0:
        return {
            'mean': np.nan,
            'median': np.nan,
            'std': np.nan,
            'min': np.nan,
            'max': np.nan,
            'n': 0,
        }
    
    return {
        'mean': np.mean(valid),
        'median': np.median(valid),
        'std': np.std(valid),
        'min': np.min(valid),
        'max': np.max(valid),
        'n': len(valid),
        'q25': np.percentile(valid, 25),
        'q75': np.percentile(valid, 75),
    }
