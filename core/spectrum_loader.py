"""Utility functions for loading and managing power spectrum backgrounds.

This module provides functions to load .npz spectrum files exported from
SW_Transform and automatically match them with corresponding dispersion CSV files.
"""

from __future__ import annotations

import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any


def load_spectrum_npz(npz_path: str) -> Dict[str, Any]:
    """Load power spectrum from .npz file.

    Args:
        npz_path: Path to .npz spectrum file

    Returns:
        Dictionary containing:
            - frequencies: 1D array (Hz)
            - velocities: 1D array (m/s)
            - power: 2D array (N_vel, N_freq), normalized 0-1
            - picked_velocities: 1D array (m/s)
            - method: str ('fk', 'fdbf', 'ps', 'ss')
            - offset: str (e.g., '+0', '+66m')
            - export_date: str (ISO timestamp)
            - version: str (format version)
            - wavenumbers: Optional 1D array (FK/FDBF only)
            - vibrosis_mode: bool
            - vspace: Optional str (PS only: 'log' or 'linear')
            - weight_mode: Optional str (FDBF only)

    Raises:
        FileNotFoundError: If npz_path doesn't exist
        KeyError: If required fields are missing
    """
    npz_path = Path(npz_path)
    if not npz_path.exists():
        raise FileNotFoundError(f"Spectrum file not found: {npz_path}")

    data = np.load(str(npz_path))

    # Verify required fields
    required_fields = ['frequencies', 'velocities', 'power', 'picked_velocities',
                      'method', 'offset', 'export_date', 'version']
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise KeyError(f"Missing required fields in {npz_path.name}: {missing}")

    return {
        # Core data
        'frequencies': data['frequencies'],
        'velocities': data['velocities'],
        'power': data['power'],
        'picked_velocities': data['picked_velocities'],

        # Metadata
        'method': str(data['method']),
        'offset': str(data['offset']),
        'export_date': str(data['export_date']),
        'version': str(data['version']),

        # Optional metadata
        'wavenumbers': data.get('wavenumbers', None),
        'vibrosis_mode': bool(data.get('vibrosis_mode', False)),
        'vspace': data.get('vspace', None),
        'weight_mode': data.get('weight_mode', None),
    }


def find_matching_spectrum(csv_path: str) -> Optional[str]:
    """Auto-detect spectrum .npz file matching a dispersion CSV file.

    Tries multiple naming patterns:
    1. <base>_<method>_<offset>_spectrum.npz  (exact match)
    2. <base>_<method>_spectrum.npz           (fallback without offset)

    Example:
        CSV: "1_fdbf_p66.csv"
        → Try: "1_fdbf_p66_spectrum.npz"
        → Try: "1_fdbf_spectrum.npz"

    Args:
        csv_path: Path to dispersion CSV file

    Returns:
        Path to matching .npz file, or None if not found
    """
    csv_path = Path(csv_path)
    base_dir = csv_path.parent
    stem = csv_path.stem  # e.g., "1_fdbf_p66"

    # Pattern 1: Exact match (with offset)
    # e.g., "1_fdbf_p66.csv" -> "1_fdbf_p66_spectrum.npz"
    exact_match = base_dir / f"{stem}_spectrum.npz"
    if exact_match.exists():
        return str(exact_match)

    # Pattern 2: Without offset tag
    # e.g., "1_fdbf_p66.csv" -> "1_fdbf_spectrum.npz"
    parts = stem.split('_')
    if len(parts) >= 2:
        # Remove last part (assumed to be offset like "p66")
        base_name = '_'.join(parts[:-1])
        fallback = base_dir / f"{base_name}_spectrum.npz"
        if fallback.exists():
            return str(fallback)

    # No match found
    return None


def find_all_spectra(directory: str, base_name: str = None, method: str = None) -> Dict[str, str]:
    """Find all spectrum files in a directory.

    Args:
        directory: Directory to search
        base_name: Optional base name filter (e.g., "1")
        method: Optional method filter (e.g., "fdbf")

    Returns:
        Dictionary mapping offset -> spectrum file path
        Example: {'+0': '/path/1_fdbf_spectrum.npz', '+66m': '/path/1_fdbf_p66_spectrum.npz'}
    """
    directory = Path(directory)
    if not directory.exists():
        return {}

    # Build search pattern
    if base_name and method:
        pattern = f"{base_name}_{method}*_spectrum.npz"
    elif base_name:
        pattern = f"{base_name}_*_spectrum.npz"
    elif method:
        pattern = f"*_{method}*_spectrum.npz"
    else:
        pattern = "*_spectrum.npz"

    # Find matching files
    offset_map = {}
    for npz_file in directory.glob(pattern):
        try:
            # Load to extract offset metadata
            data = np.load(str(npz_file))
            offset = str(data['offset'])
            offset_map[offset] = str(npz_file)
        except Exception:
            # Skip files that can't be loaded or don't have offset field
            continue

    return offset_map


def get_spectrum_bounds(spectrum_data: Dict[str, Any]) -> tuple:
    """Get data bounds from spectrum data.

    Args:
        spectrum_data: Dictionary from load_spectrum_npz()

    Returns:
        Tuple of (freq_min, freq_max, vel_min, vel_max)
    """
    freq_min = float(spectrum_data['frequencies'][0])
    freq_max = float(spectrum_data['frequencies'][-1])
    vel_min = float(spectrum_data['velocities'][0])
    vel_max = float(spectrum_data['velocities'][-1])

    return freq_min, freq_max, vel_min, vel_max


def validate_spectrum_alignment(spectrum_data: Dict[str, Any],
                                csv_frequencies: np.ndarray,
                                csv_velocities: np.ndarray) -> bool:
    """Verify that CSV dispersion points align with spectrum bounds.

    Args:
        spectrum_data: Dictionary from load_spectrum_npz()
        csv_frequencies: Frequency array from CSV
        csv_velocities: Velocity array from CSV

    Returns:
        True if CSV points are within spectrum bounds
    """
    freq_min, freq_max, vel_min, vel_max = get_spectrum_bounds(spectrum_data)

    csv_freq_min = np.min(csv_frequencies)
    csv_freq_max = np.max(csv_frequencies)
    csv_vel_min = np.min(csv_velocities)
    csv_vel_max = np.max(csv_velocities)

    # Check if CSV is within spectrum bounds (with small tolerance)
    freq_ok = (csv_freq_min >= freq_min - 1.0) and (csv_freq_max <= freq_max + 1.0)
    vel_ok = (csv_vel_min >= vel_min - 10.0) and (csv_vel_max <= vel_max + 10.0)

    return freq_ok and vel_ok
