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


def load_combined_spectrum_npz(npz_path: str) -> Dict[str, Dict[str, Any]]:
    """Load combined multi-offset spectrum from .npz file.

    Combined spectrum files contain multiple offsets in a single file with
    data keyed by offset suffix (e.g., 'p66' for +66m, 'm10' for -10m).

    Expected structure:
        - method: str (common method for all offsets)
        - offsets: array of offset names
        - num_offsets: int
        - For each offset suffix (e.g., 'p66'):
            - frequencies_{suffix}: 1D array
            - velocities_{suffix}: 1D array
            - power_{suffix}: 2D array
            - picked_velocities_{suffix}: 1D array
            - wavenumbers_{suffix}: optional 1D array
            - vibrosis_mode_{suffix}: bool

    Args:
        npz_path: Path to combined .npz spectrum file

    Returns:
        Dictionary mapping offset label -> spectrum data dict
        Example: {'+66m': {'frequencies': ..., 'velocities': ..., 'power': ...}, ...}

    Raises:
        FileNotFoundError: If npz_path doesn't exist
        ValueError: If file doesn't appear to be a combined spectrum
    """
    npz_path = Path(npz_path)
    if not npz_path.exists():
        raise FileNotFoundError(f"Spectrum file not found: {npz_path}")

    data = np.load(str(npz_path), allow_pickle=True)

    # Check if this is a combined spectrum file
    if 'offsets' not in data or 'num_offsets' not in data:
        raise ValueError(f"{npz_path.name} is not a combined spectrum file (missing 'offsets' or 'num_offsets')")

    method = str(data['method']) if 'method' in data else 'unknown'
    export_date = str(data['export_date']) if 'export_date' in data else ''
    version = str(data['version']) if 'version' in data else '1.0'
    offsets = data['offsets']

    result = {}

    for offset in offsets:
        # Convert offset to suffix format used in NPZ keys
        # e.g., '+66' or '+66m' -> 'p66', '-10' or '-10m' -> 'm10'
        offset_str = str(offset).strip()
        suffix = _offset_to_suffix(offset_str)

        # Try to load data for this offset
        try:
            freq_key = f'frequencies_{suffix}'
            vel_key = f'velocities_{suffix}'
            power_key = f'power_{suffix}'
            picked_key = f'picked_velocities_{suffix}'

            if freq_key not in data:
                continue

            spectrum_data = {
                'frequencies': data[freq_key],
                'velocities': data[vel_key],
                'power': data[power_key],
                'picked_velocities': data.get(picked_key, None),
                'method': method,
                'offset': offset_str,
                'export_date': export_date,
                'version': version,
                'wavenumbers': data.get(f'wavenumbers_{suffix}', None),
                'vibrosis_mode': bool(data.get(f'vibrosis_mode_{suffix}', False)),
            }

            # Normalize the offset label for consistent matching
            normalized_label = _normalize_offset_label(offset_str)
            result[normalized_label] = spectrum_data

        except Exception:
            continue

    return result


def _offset_to_suffix(offset: str) -> str:
    """Convert offset label to NPZ key suffix.

    Examples:
        '+66' -> 'p66'
        '+66m' -> 'p66'
        '-10' -> 'm10'
        '-10m' -> 'm10'
        'p66' -> 'p66' (already in suffix format)
    """
    offset = str(offset).strip().lower()

    # Remove 'm' suffix if present
    if offset.endswith('m'):
        offset = offset[:-1]

    # Convert sign to p/m prefix
    if offset.startswith('+'):
        return 'p' + offset[1:]
    elif offset.startswith('-'):
        return 'm' + offset[1:]
    elif offset.startswith('p') or offset.startswith('m'):
        return offset
    else:
        # Assume positive if no sign
        return 'p' + offset


def _normalize_offset_label(offset: str) -> str:
    """Normalize offset label for consistent matching.

    Examples:
        '+66' -> '+66m'
        '+66m' -> '+66m'
        '-10' -> '-10m'
        'p66' -> '+66m'
        'm10' -> '-10m'
    """
    offset = str(offset).strip()

    # Handle p/m prefix format
    if offset.startswith('p'):
        offset = '+' + offset[1:]
    elif offset.startswith('m'):
        offset = '-' + offset[1:]

    # Remove trailing 'm' for processing
    if offset.endswith('m'):
        offset = offset[:-1]

    # Add 'm' suffix back
    return offset + 'm'


def match_csv_labels_to_spectrum(csv_labels: list, spectrum_offsets: Dict[str, Any]) -> Dict[int, str]:
    """Match CSV layer labels to spectrum offsets.

    CSV labels are like 'fk_+66' or '+66m' and need to be matched to
    spectrum offset keys.

    Args:
        csv_labels: List of labels from CSV columns (e.g., ['fk_+66', 'fk_+56', ...])
        spectrum_offsets: Dict from load_combined_spectrum_npz()

    Returns:
        Dict mapping layer index -> spectrum offset key
        Example: {0: '+66m', 1: '+56m', ...}
    """
    matches = {}

    for i, label in enumerate(csv_labels):
        label_str = str(label).strip()

        # Extract offset from label (handle formats like 'fk_+66', 'fdbf_p66', '+66m', etc.)
        # Try different extraction patterns
        offset_part = None

        # Pattern 1: method_offset (e.g., 'fk_+66', 'fdbf_p66')
        if '_' in label_str:
            parts = label_str.split('_')
            offset_part = parts[-1]  # Take last part
        else:
            offset_part = label_str

        if offset_part is None:
            continue

        # Normalize the extracted offset
        normalized = _normalize_offset_label(offset_part)

        # Check if this matches any spectrum offset
        if normalized in spectrum_offsets:
            matches[i] = normalized
        else:
            # Try matching without normalization (case variations)
            for spec_key in spectrum_offsets.keys():
                if _normalize_offset_label(spec_key) == normalized:
                    matches[i] = spec_key
                    break

    return matches


def load_combined_spectrum_for_csv(csv_path: str, npz_path: str = None) -> Optional[Dict[int, Dict[str, Any]]]:
    """Load combined spectrum and match to CSV layers.

    This function:
    1. Loads the combined CSV to get layer labels
    2. Loads the combined spectrum NPZ
    3. Matches spectrum offsets to CSV layers

    Args:
        csv_path: Path to combined CSV file
        npz_path: Optional path to spectrum NPZ (auto-detected if None)

    Returns:
        Dict mapping layer index -> spectrum data, or None if no matches
    """
    csv_path = Path(csv_path)

    # Auto-detect spectrum file if not provided
    if npz_path is None:
        # Try same directory, similar name
        stem = csv_path.stem
        candidates = [
            csv_path.parent / f"{stem}_spectrum.npz",
            csv_path.parent / f"{stem.replace('_', '-')}_spectrum.npz",
        ]
        # Also check for 'combined' prefix
        for candidate in candidates:
            if candidate.exists():
                npz_path = str(candidate)
                break

    if npz_path is None:
        return None

    # Load combined spectrum
    try:
        spectrum_offsets = load_combined_spectrum_npz(npz_path)
    except Exception:
        return None

    if not spectrum_offsets:
        return None

    # Load CSV to get labels
    try:
        import pandas as pd
        df = pd.read_csv(csv_path, nrows=0)
        columns = list(df.columns)

        # Extract unique offset labels from column names
        # Columns are like: freq(fk_+66), vel(fk_+66), wav(fk_+66), ...
        labels = []
        seen = set()
        for col in columns:
            # Extract label from parentheses
            if '(' in col and ')' in col:
                label = col[col.index('(') + 1:col.index(')')]
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
    except Exception:
        return None

    # Match labels to spectrum offsets
    matches = match_csv_labels_to_spectrum(labels, spectrum_offsets)

    if not matches:
        return None

    # Build result dict
    result = {}
    for layer_idx, offset_key in matches.items():
        result[layer_idx] = spectrum_offsets[offset_key]

    return result
