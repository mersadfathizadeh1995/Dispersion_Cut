from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Tuple, Literal

try:
    import scipy.io  # optional
except Exception:
    scipy = None  # type: ignore


# Valid wave types for RTBF format filtering
WaveType = Literal['Rayleigh', 'Love', 'all']


def load_klimits(*, mat_path: Optional[str] = None, csv_path: Optional[str] = None) -> Tuple[float, float]:
    if mat_path:
        if scipy is None:
            raise ImportError("SciPy is required to read MAT files.")
        mat = scipy.io.loadmat(mat_path)
        if 'klimits' not in mat:
            raise ValueError(f"MAT-file {mat_path!r} does not contain 'klimits'")
        arr = np.array(mat['klimits']).squeeze()
        if arr.size != 2:
            raise ValueError("'klimits' must have two elements [kmin, kmax]")
        return float(arr[0]), float(arr[1])
    if csv_path:
        with open(csv_path, 'r') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                parts = [p for p in s.replace(',', ' ').split() if p]
                if len(parts) >= 2:
                    return float(parts[0]), float(parts[1])
        raise ValueError(f"CSV {csv_path!r} does not contain two numbers")
    raise ValueError("Provide mat_path or csv_path for klimits")


# Max file format types
MaxFormat = Literal['auto', 'fk', 'rtbf', 'lds']


def parse_max_file(
    path: str,
    *,
    wave_type: WaveType = 'all',
    data_start_line: int = 0,
    format_hint: MaxFormat = 'auto'
) -> pd.DataFrame:
    """Parse Geopsy FK .max with robustness to separators and header lines.
    
    Supports three formats:
    - Standard FK (7 columns): time, freq, slow, az, phi, semblance, beampow
    - RTBF (9 columns + text): time, freq, polarization, slow, az, ell, noise, power, valid
    - LDS/ARDS (9 columns numeric): time, freq, slow, az, ell, Rz/N, Rh/N, power, valid
    
    Parameters
    ----------
    path : str
        Path to the .max file
    wave_type : {'Rayleigh', 'Love', 'all'}, default 'all'
        For RTBF format files only: filter by wave polarization type.
        'all' keeps both Rayleigh and Love waves.
        For standard FK and LDS files, this parameter is ignored.
    data_start_line : int, default 0
        Number of data lines to skip after finding data section.
        Use this to manually skip header rows in the data section.
    format_hint : {'auto', 'fk', 'rtbf', 'lds'}, default 'auto'
        Force a specific format instead of auto-detection.
        'auto' detects format based on column count and content.
    
    Returns
    -------
    pd.DataFrame
        DataFrame with columns: time, freq, slow, az, [and additional columns if available]
        For RTBF files, also includes: ellipticity, noise, power, valid, polarization
    """
    import re
    
    # Read file and filter valid data lines
    data_lines = []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            stripped = line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                continue
            # Data lines start with a number (timestamp or time value)
            # Check if first character is a digit
            if stripped[0].isdigit():
                data_lines.append(stripped)
    
    if not data_lines:
        return pd.DataFrame(columns=['time', 'freq', 'slow', 'az'])
    
    # Apply data_start_line skip
    if data_start_line > 0:
        data_lines = data_lines[data_start_line:]
    
    if not data_lines:
        return pd.DataFrame(columns=['time', 'freq', 'slow', 'az'])
    
    # Parse the data lines
    rows = []
    for line in data_lines:
        parts = re.split(r'[\s\|]+', line)
        if len(parts) >= 4:  # Minimum: time, freq, slow, az
            rows.append(parts)
    
    if not rows:
        return pd.DataFrame(columns=['time', 'freq', 'slow', 'az'])
    
    # Determine format based on number of columns and content
    sample_row = rows[0]
    n_cols = len(sample_row)
    
    # Detect format
    detected_format = 'fk'  # default
    if format_hint != 'auto':
        detected_format = format_hint
    elif n_cols >= 9:
        # Check if column 2 is non-numeric (contains 'Rayleigh' or 'Love') -> RTBF
        try:
            float(sample_row[2])
            # Column 2 is numeric -> LDS format (9 numeric cols)
            detected_format = 'lds'
        except ValueError:
            # Column 2 is not numeric -> RTBF format
            detected_format = 'rtbf'
    elif n_cols >= 7:
        detected_format = 'fk'
    
    # Create DataFrame
    raw = pd.DataFrame(rows)
    
    if detected_format == 'rtbf':
        # RTBF format: abs_time(0), freq(1), polarization(2), slow(3), az(4), 
        #              ellipticity(5), noise(6), power(7), valid(8)
        # Note: RTBF slowness is in s/m, we convert to s/km for consistency
        col_names = ['time', 'freq', 'polarization', 'slow', 'az', 
                     'ellipticity', 'noise', 'power', 'valid']
        # Only use as many column names as we have columns
        col_names = col_names[:raw.shape[1]]
        raw.columns = col_names
        
        df = raw.copy()
        
        # Filter by wave_type if specified
        if wave_type != 'all' and 'polarization' in df.columns:
            df = df[df['polarization'] == wave_type].copy()
        
        # Convert numeric columns
        numeric_cols = ['time', 'freq', 'slow', 'az', 'ellipticity', 'noise', 'power', 'valid']
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # Convert RTBF slowness from s/m to s/km for consistency with standard FK format
        # s/km = s/m * 1000
        if 'slow' in df.columns:
            df['slow'] = df['slow'] * 1000.0
        
        # Drop rows with invalid freq or slow
        df = df.dropna(subset=['freq', 'slow'])
        
        # Compute Rayleigh wave component information from ellipticity
        # Ellipticity angle ξ (radians) relates radial and vertical components:
        #   ξ = arctan(A_radial / A_vertical)
        #   tan(ξ) = A_radial / A_vertical
        # 
        # For normalized amplitudes (A_radial² + A_vertical² = 1):
        #   A_vertical = 1 / sqrt(1 + tan²(ξ)) = |cos(ξ)|
        #   A_radial = |tan(ξ)| / sqrt(1 + tan²(ξ)) = |sin(ξ)|
        #
        # Motion type:
        #   ξ > 0: Prograde (radial leads vertical, forward ellipse rotation)
        #   ξ < 0: Retrograde (radial lags vertical, backward ellipse rotation)
        #   ξ = 0: Purely vertical motion
        #   |ξ| = π/2: Purely horizontal (radial) motion
        if 'ellipticity' in df.columns:
            # Only compute for Rayleigh waves (Love waves have ellipticity=0, not meaningful)
            rayleigh_mask = df['polarization'] == 'Rayleigh' if 'polarization' in df.columns else True
            
            # Radial to vertical amplitude ratio: tan(ellipticity)
            df['radial_vertical_ratio'] = np.where(
                rayleigh_mask,
                np.tan(df['ellipticity']),
                np.nan
            )
            
            # Normalized relative amplitudes
            # A_vertical = |cos(ξ)|, A_radial = |sin(ξ)|
            df['vertical_amplitude'] = np.where(
                rayleigh_mask,
                np.abs(np.cos(df['ellipticity'])),
                np.nan
            )
            df['radial_amplitude'] = np.where(
                rayleigh_mask,
                np.abs(np.sin(df['ellipticity'])),
                np.nan
            )
            
            # Motion type classification
            df['motion_type'] = np.where(
                ~rayleigh_mask,
                'transverse',  # Love waves
                np.where(
                    df['ellipticity'] > 0,
                    'prograde',    # Forward ellipse rotation
                    np.where(
                        df['ellipticity'] < 0,
                        'retrograde',  # Backward ellipse rotation
                        'vertical'     # Purely vertical (ξ = 0)
                    )
                )
            )
        
    elif detected_format == 'lds':
        # LDS/ARDS format (9 numeric columns):
        # abs_time(0), freq(1), slow(2), az(3), ell(4), Rz/N(5), Rh/N(6), power(7), valid(8)
        # Note: LDS slowness is in s/m, we convert to s/km for consistency
        col_names = ['time', 'freq', 'slow', 'az', 'ellipticity', 
                     'rz_n', 'rh_n', 'power', 'valid']
        col_names = col_names[:raw.shape[1]]
        raw.columns = col_names
        
        df = raw.copy()
        
        # Convert all to numeric
        for c in col_names:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        # Convert LDS slowness from s/m to s/km
        if 'slow' in df.columns:
            df['slow'] = df['slow'] * 1000.0
        
        df = df.dropna(subset=['freq', 'slow'])
    
    else:
        # Standard FK format (7 columns)
        # Slowness is already in s/km
        col_names = ['time', 'freq', 'slow', 'az', 'phi', 'semblance', 'beampow']
        col_names = col_names[:raw.shape[1]]
        raw.columns = col_names
        
        df = raw.copy()
        
        # Convert all to numeric
        for c in col_names:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df = df.dropna(subset=['freq', 'slow'])
    
    return df










