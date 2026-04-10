"""I/O functions for loading theoretical dispersion curve CSV files."""
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import pandas as pd

from dc_cut.packages.theoretical_curves.config import TheoreticalCurve, TheoreticalCurveStyle


def load_theoretical_csv(
    filepath: str,
    name: Optional[str] = None,
    wave_type: Optional[str] = None,
) -> List[TheoreticalCurve]:
    """Load theoretical dispersion curves from a statistics CSV file.
    
    The CSV should have columns: freq_Hz, mode, median, mean, lower, upper, std, min, max, count
    
    Parameters
    ----------
    filepath : str
        Path to the CSV file
    name : str, optional
        Base name for the curves. If None, derived from filename.
    wave_type : str, optional
        Wave type ("Rayleigh" or "Love"). If None, inferred from filename.
    
    Returns
    -------
    List[TheoreticalCurve]
        List of curves, one per mode found in the file.
    """
    path = Path(filepath)
    
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")
    
    df = pd.read_csv(filepath)
    
    required_cols = ['freq_Hz', 'median', 'lower', 'upper']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    if name is None:
        name = path.stem
    
    if wave_type is None:
        wave_type = _infer_wave_type(path.name)
    
    if 'std' not in df.columns:
        df['std'] = (df['upper'] - df['lower']) / 2
    
    if 'mode' not in df.columns:
        df['mode'] = 0
    
    curves = []
    for mode in sorted(df['mode'].unique()):
        mode_df = df[df['mode'] == mode].sort_values('freq_Hz')
        
        curve = TheoreticalCurve(
            name=f"{name}_mode{mode}" if df['mode'].nunique() > 1 else name,
            source_file=str(path),
            wave_type=wave_type,
            mode=int(mode),
            frequencies=mode_df['freq_Hz'].values.astype(float),
            median=mode_df['median'].values.astype(float),
            lower=mode_df['lower'].values.astype(float),
            upper=mode_df['upper'].values.astype(float),
            std=mode_df['std'].values.astype(float),
            style=TheoreticalCurveStyle(),
        )
        curves.append(curve)
    
    return curves


def _infer_wave_type(filename: str) -> str:
    """Infer wave type from filename."""
    fn_lower = filename.lower()
    if 'love' in fn_lower:
        return "Love"
    return "Rayleigh"


def load_multiple_csv(filepaths: List[str]) -> List[TheoreticalCurve]:
    """Load theoretical curves from multiple CSV files.
    
    Parameters
    ----------
    filepaths : List[str]
        List of paths to CSV files
    
    Returns
    -------
    List[TheoreticalCurve]
        Combined list of all curves from all files
    """
    all_curves = []
    for fp in filepaths:
        try:
            curves = load_theoretical_csv(fp)
            all_curves.extend(curves)
        except Exception as e:
            print(f"Warning: Failed to load {fp}: {e}")
    return all_curves
