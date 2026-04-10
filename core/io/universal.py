"""Universal file parser for dispersion data.

Supports MAT, CSV, TXT files with flexible column mapping.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd


def parse_any_file(
    path: str,
    mapping: Optional[Dict[str, int]] = None,
    *,
    delimiter: str = 'auto',
    data_start_line: int = 0,
    cols_per_offset: int = 0
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Parse any supported file type and return dispersion arrays.
    
    Parameters
    ----------
    path : str
        Path to data file (MAT, CSV, or TXT)
    mapping : dict, optional
        Column mapping {type_str: col_idx} where type_str is one of:
        'Frequency (Hz)', 'Velocity (m/s)', 'Slowness (s/km)', 'Wavelength (m)'
        If None for MAT files, attempts auto-detection of standard MASW format.
    delimiter : str
        Delimiter for text files: 'auto', 'comma', 'tab', 'space', 'pipe'
    data_start_line : int
        Number of data lines to skip from beginning
    cols_per_offset : int
        Columns per offset for multi-offset data (0 = single offset)
    
    Returns
    -------
    velocity_arrays : list of ndarray
    frequency_arrays : list of ndarray
    wavelength_arrays : list of ndarray
    labels : list of str
    """
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.mat':
        # Try auto-detection for standard MASW MAT files if no mapping
        if not mapping:
            result = _parse_masw_mat_file(path)
            if result is not None:
                return result
            raise ValueError("MAT file doesn't match standard MASW format. Please use column mapping.")
        return _parse_mat_file(path, mapping, cols_per_offset)
    else:
        if not mapping:
            raise ValueError("Column mapping required for text files")
        return _parse_text_file(path, mapping, delimiter, data_start_line, cols_per_offset)


def _parse_mat_file(
    path: str,
    mapping: Dict[str, int],
    cols_per_offset: int
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Parse MATLAB .mat file."""
    try:
        from scipy.io import loadmat
    except ImportError:
        raise ImportError("scipy required for .mat files")
    
    mat = loadmat(path, squeeze_me=True)
    
    # Get all numeric arrays and flatten into columns
    all_cols = []
    col_names = []
    
    for key in sorted(mat.keys()):
        if key.startswith('__'):
            continue
        arr = mat[key]
        if isinstance(arr, np.ndarray) and arr.dtype.kind in 'iuf':
            if arr.ndim == 2:
                for i in range(arr.shape[1]):
                    all_cols.append(arr[:, i])
                    col_names.append(f"{key}[:,{i}]")
            elif arr.ndim == 1:
                all_cols.append(arr)
                col_names.append(key)
    
    if not all_cols:
        raise ValueError("No numeric arrays found in MAT file")
    
    # Apply mapping
    return _extract_dispersion_data(all_cols, col_names, mapping, cols_per_offset)


def _parse_masw_mat_file(
    path: str
) -> Optional[Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]]:
    """Auto-detect and parse standard MASW MAT file format.
    
    Standard format has:
    - FrequencyRaw or Frequency: (N, M) array with M offsets
    - VelocityRaw or Velocity: (N, M) array
    - WavelengthRaw or Wavelength: (N, M) array (optional, calculated if missing)
    - setLeg: (M,) array of offset labels (optional)
    
    Returns None if file doesn't match standard format.
    """
    try:
        from scipy.io import loadmat
    except ImportError:
        return None
    
    mat = loadmat(path, squeeze_me=True)
    keys = [k for k in mat.keys() if not k.startswith('__')]
    keys_lower = {k.lower(): k for k in keys}
    
    # Find frequency array
    freq_key = None
    for candidate in ['frequencyraw', 'frequency', 'freq', 'f']:
        if candidate in keys_lower:
            freq_key = keys_lower[candidate]
            break
    
    # Find velocity array
    vel_key = None
    for candidate in ['velocityraw', 'velocity', 'vel', 'v']:
        if candidate in keys_lower:
            vel_key = keys_lower[candidate]
            break
    
    # Find wavelength array (optional)
    wave_key = None
    for candidate in ['wavelengthraw', 'wavelength', 'wave', 'w', 'lambda']:
        if candidate in keys_lower:
            wave_key = keys_lower[candidate]
            break
    
    # Find labels (optional)
    label_key = None
    for candidate in ['setleg', 'labels', 'legend', 'offsetlabels']:
        if candidate in keys_lower:
            label_key = keys_lower[candidate]
            break
    
    if not freq_key or not vel_key:
        return None
    
    freq_arr = mat[freq_key]
    vel_arr = mat[vel_key]
    
    if not isinstance(freq_arr, np.ndarray) or not isinstance(vel_arr, np.ndarray):
        return None
    
    # Handle 1D vs 2D arrays
    if freq_arr.ndim == 1:
        freq_arr = freq_arr.reshape(-1, 1)
    if vel_arr.ndim == 1:
        vel_arr = vel_arr.reshape(-1, 1)
    
    if freq_arr.shape != vel_arr.shape:
        return None
    
    n_rows, n_offsets = freq_arr.shape
    
    # Get wavelength or calculate
    if wave_key and wave_key in mat:
        wave_arr = mat[wave_key]
        if isinstance(wave_arr, np.ndarray):
            if wave_arr.ndim == 1:
                wave_arr = wave_arr.reshape(-1, 1)
        else:
            wave_arr = None
    else:
        wave_arr = None
    
    if wave_arr is None or wave_arr.shape != freq_arr.shape:
        with np.errstate(divide='ignore', invalid='ignore'):
            wave_arr = np.where(freq_arr > 0, vel_arr / freq_arr, np.nan)
    
    # Get labels
    labels = []
    if label_key and label_key in mat:
        label_arr = mat[label_key]
        if isinstance(label_arr, np.ndarray):
            labels = [str(l) for l in label_arr.flatten()]
        elif isinstance(label_arr, str):
            labels = [label_arr]
    
    if len(labels) != n_offsets:
        labels = [f"Offset {i+1}" for i in range(n_offsets)]
    
    # Build output arrays
    velocity_arrays = []
    frequency_arrays = []
    wavelength_arrays = []
    
    for i in range(n_offsets):
        freq = freq_arr[:, i].astype(float)
        vel = vel_arr[:, i].astype(float)
        wave = wave_arr[:, i].astype(float)
        
        # Filter valid data
        mask = np.isfinite(freq) & np.isfinite(vel) & np.isfinite(wave) & (freq > 0) & (vel > 0)
        
        frequency_arrays.append(freq[mask])
        velocity_arrays.append(vel[mask])
        wavelength_arrays.append(wave[mask])
    
    return velocity_arrays, frequency_arrays, wavelength_arrays, labels


def _parse_text_file(
    path: str,
    mapping: Dict[str, int],
    delimiter: str,
    data_start_line: int,
    cols_per_offset: int
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Parse CSV/TXT file with flexible delimiter."""
    # ANSI escape code pattern
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[\d*m')
    
    # Read and clean lines
    raw_lines = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            clean = ansi_escape.sub('', line).strip()
            if clean and not clean.startswith('#'):
                raw_lines.append(clean)
    
    if not raw_lines:
        raise ValueError("File contains no data")
    
    # Detect delimiter
    delimiters = {
        'comma': ',',
        'tab': '\t',
        'space': r'\s+',
        'pipe': r'\|',
        'auto': None
    }
    
    if delimiter.lower() == 'auto':
        first_line = raw_lines[0]
        counts = {
            'comma': first_line.count(','),
            'tab': first_line.count('\t'),
            'pipe': first_line.count('|'),
            'space': len(re.split(r'\s+', first_line)) - 1
        }
        best = max(counts, key=counts.get)
        delim_pattern = delimiters[best]
    else:
        delim_pattern = delimiters.get(delimiter.lower(), r'[\s\|,]+')
    
    # Parse rows
    rows = []
    for line in raw_lines[data_start_line:]:
        if delim_pattern and delim_pattern not in [r'\s+', r'\|']:
            parts = [p.strip() for p in line.split(delim_pattern)]
        else:
            parts = re.split(delim_pattern or r'[\s\|,]+', line)
        parts = [p for p in parts if p]
        if parts:
            rows.append(parts)
    
    if not rows:
        raise ValueError("No valid data rows found")
    
    # Build column arrays
    n_cols = max(len(row) for row in rows)
    all_cols = []
    col_names = []
    
    for col_idx in range(n_cols):
        col_values = []
        for row in rows:
            if col_idx < len(row):
                try:
                    col_values.append(float(row[col_idx]))
                except ValueError:
                    col_values.append(np.nan)
            else:
                col_values.append(np.nan)
        all_cols.append(np.array(col_values))
        col_names.append(f"Col {col_idx + 1}")
    
    return _extract_dispersion_data(all_cols, col_names, mapping, cols_per_offset)


def _extract_dispersion_data(
    all_cols: List[np.ndarray],
    col_names: List[str],
    mapping: Dict[str, int],
    cols_per_offset: int
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Extract dispersion arrays from columns using mapping."""
    velocity_arrays = []
    frequency_arrays = []
    wavelength_arrays = []
    labels = []
    
    # Get column indices from mapping
    freq_idx = mapping.get('Frequency (Hz)')
    vel_idx = mapping.get('Velocity (m/s)')
    slow_idx = mapping.get('Slowness (s/km)')
    wave_idx = mapping.get('Wavelength (m)')
    
    if freq_idx is None:
        raise ValueError("Frequency column not mapped")
    if vel_idx is None and slow_idx is None:
        raise ValueError("Velocity or Slowness column not mapped")
    
    if cols_per_offset > 0 and len(all_cols) > cols_per_offset:
        # Multi-offset data - extract groups
        n_offsets = len(all_cols) // cols_per_offset
        for i in range(n_offsets):
            base = i * cols_per_offset
            
            # Map relative indices within offset group
            freq = all_cols[base + (freq_idx % cols_per_offset)]
            
            if vel_idx is not None:
                vel = all_cols[base + (vel_idx % cols_per_offset)]
            elif slow_idx is not None:
                slow = all_cols[base + (slow_idx % cols_per_offset)]
                vel = 1000.0 / slow  # s/km to m/s
            
            if wave_idx is not None:
                wave = all_cols[base + (wave_idx % cols_per_offset)]
            else:
                with np.errstate(divide='ignore', invalid='ignore'):
                    wave = np.where(freq > 0, vel / freq, np.nan)
            
            # Filter valid data
            mask = np.isfinite(freq) & np.isfinite(vel) & np.isfinite(wave) & (freq > 0) & (vel > 0)
            
            frequency_arrays.append(freq[mask])
            velocity_arrays.append(vel[mask])
            wavelength_arrays.append(wave[mask])
            labels.append(f"Offset {i + 1}")
    else:
        # Single offset
        freq = all_cols[freq_idx]
        
        if vel_idx is not None:
            vel = all_cols[vel_idx]
        elif slow_idx is not None:
            slow = all_cols[slow_idx]
            vel = 1000.0 / slow
        
        if wave_idx is not None:
            wave = all_cols[wave_idx]
        else:
            with np.errstate(divide='ignore', invalid='ignore'):
                wave = np.where(freq > 0, vel / freq, np.nan)
        
        # Filter valid data
        mask = np.isfinite(freq) & np.isfinite(vel) & np.isfinite(wave) & (freq > 0) & (vel > 0)
        
        frequency_arrays.append(freq[mask])
        velocity_arrays.append(vel[mask])
        wavelength_arrays.append(wave[mask])
        labels.append("Layer 1")
    
    return velocity_arrays, frequency_arrays, wavelength_arrays, labels


def parse_combined_csv(
    path: str,
    mapping: Optional[Dict[str, int]] = None
) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
    """Parse combined CSV with multiple offsets (freq, vel, wave columns per offset).
    
    Auto-detects offset structure from headers like 'freq(offset_name)'.
    """
    with open(path, 'r') as f:
        header_line = f.readline().strip()
        headers = [h.strip() for h in header_line.split(',') if h.strip()]
    
    total_cols = len(headers)
    headers_lower = [h.lower() for h in headers]
    
    # Detect columns per offset
    has_wave = any("wav" in h or "wave" in h or "wavelength" in h for h in headers_lower)
    cols_per_offset = 3 if has_wave else 2
    n_offsets = total_cols // cols_per_offset
    
    # Extract labels from headers
    labels = []
    for i in range(n_offsets):
        freq_header = headers[i * cols_per_offset]
        # Extract label from parentheses
        match = re.search(r'\(([^)]+)\)', freq_header)
        if match:
            label = match.group(1).strip()
            # Skip unit labels
            if label.lower() not in ('hz', 'khz', 'm/s', 'm'):
                labels.append(label)
            else:
                labels.append(f"Offset {i + 1}")
        else:
            labels.append(f"Offset {i + 1}")
    
    # Read data
    df = pd.read_csv(path)
    mat = df.values
    
    velocity_arrays = []
    frequency_arrays = []
    wavelength_arrays = []
    
    for i in range(n_offsets):
        start = i * cols_per_offset
        freq = mat[:, start].astype(float)
        vel = mat[:, start + 1].astype(float)
        
        if cols_per_offset == 3:
            wave = mat[:, start + 2].astype(float)
        else:
            with np.errstate(divide='ignore', invalid='ignore'):
                wave = vel / freq
        
        # Filter valid
        mask = np.isfinite(freq) & np.isfinite(vel) & np.isfinite(wave) & (freq > 0) & (vel > 0)
        
        frequency_arrays.append(freq[mask])
        velocity_arrays.append(vel[mask])
        wavelength_arrays.append(wave[mask])
    
    return velocity_arrays, frequency_arrays, wavelength_arrays, labels
