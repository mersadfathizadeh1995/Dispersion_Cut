"""I/O functions for circular array workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, List, Optional
import numpy as np

try:
    import scipy.io as sio
except ImportError:
    sio = None


def load_multi_array_klimits(
    path: Path,
    *,
    mat_key: Optional[str] = None
) -> Dict[int, Tuple[float, float]]:
    """Load k-limits for multiple arrays from .mat or .csv file.

    Expected format (3 rows):
        diameter, kmin, kmax
        500, 0.002, 0.02
        200, 0.005, 0.05
        50, 0.02, 0.2

    Parameters
    ----------
    path : Path
        Path to klimits file (.mat or .csv)
    mat_key : str, optional
        Key name in MAT file. If None, tries common names.

    Returns
    -------
    Dict[int, Tuple[float, float]]
        Mapping of diameter (int) to (kmin, kmax) tuple
    """
    path = Path(path)

    if path.suffix.lower() == '.mat':
        return _load_klimits_mat(path, mat_key)
    elif path.suffix.lower() == '.csv':
        return _load_klimits_csv(path)
    else:
        raise ValueError(f"Unsupported klimits file format: {path.suffix}")


def _load_klimits_mat(path: Path, mat_key: Optional[str] = None) -> Dict[int, Tuple[float, float]]:
    """Load k-limits from MAT file."""
    if sio is None:
        raise ImportError("SciPy is required to read MAT files.")

    data = sio.loadmat(str(path))

    arr = None
    if mat_key and mat_key in data:
        arr = data[mat_key]
    else:
        for key in ['klimits', 'klimit', 'k_limits', 'Klimits']:
            if key in data:
                arr = data[key]
                break

    if arr is None:
        non_meta = [k for k in data.keys() if not k.startswith('_')]
        if non_meta:
            arr = data[non_meta[0]]
        else:
            raise ValueError(f"MAT file {path} does not contain klimits data")

    arr = np.asarray(arr)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    result: Dict[int, Tuple[float, float]] = {}
    
    if arr.shape[1] >= 3:
        for row in arr:
            diameter = int(row[0])
            kmin, kmax = float(row[1]), float(row[2])
            result[diameter] = (kmin, kmax)
    elif arr.shape[1] == 2:
        for idx, row in enumerate(arr):
            kmin, kmax = float(row[0]), float(row[1])
            result[idx] = (kmin, kmax)

    if not result:
        raise ValueError(f"No valid klimits rows found in {path}")

    return result


def _load_klimits_csv(path: Path) -> Dict[int, Tuple[float, float]]:
    """Load k-limits from CSV file."""
    result: Dict[int, Tuple[float, float]] = {}

    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = [p.strip() for p in line.replace(',', ' ').split() if p.strip()]
            if len(parts) >= 3:
                try:
                    diameter = int(float(parts[0]))
                    kmin = float(parts[1])
                    kmax = float(parts[2])
                    result[diameter] = (kmin, kmax)
                except ValueError:
                    continue

    if not result:
        raise ValueError(f"No valid klimits rows found in {path}")

    return result


def export_stage_to_mat(
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    wavelength_arrays: List[np.ndarray],
    labels: List[str],
    output_path: Path,
    site_name: str,
    stage_name: str,
    **extra_metadata
) -> None:
    """Export current stage data to MATLAB .mat file.

    Parameters
    ----------
    velocity_arrays : List[np.ndarray]
        List of velocity arrays (m/s) per layer
    frequency_arrays : List[np.ndarray]
        List of frequency arrays (Hz) per layer
    wavelength_arrays : List[np.ndarray]
        List of wavelength arrays (m) per layer
    labels : List[str]
        List of layer labels
    output_path : Path
        Output file path
    site_name : str
        Site name for metadata
    stage_name : str
        Stage name for metadata
    **extra_metadata
        Additional metadata to include
    """
    if sio is None:
        raise ImportError("SciPy is required to write MAT files.")

    mat_dict = {
        'site_name': site_name,
        'stage': stage_name,
        'num_layers': len(velocity_arrays),
        **extra_metadata,
    }

    for i, (vel, freq, wlen, label) in enumerate(zip(
        velocity_arrays, frequency_arrays, wavelength_arrays, labels
    )):
        idx = i + 1
        vel_arr = np.asarray(vel, dtype=np.float64)
        freq_arr = np.asarray(freq, dtype=np.float64)
        wlen_arr = np.asarray(wlen, dtype=np.float64)

        mat_dict[f'velocity_{idx}'] = vel_arr
        mat_dict[f'frequency_{idx}'] = freq_arr
        mat_dict[f'wavelength_{idx}'] = wlen_arr
        mat_dict[f'slowness_{idx}'] = 1000.0 / vel_arr
        mat_dict[f'label_{idx}'] = label

    if velocity_arrays:
        mat_dict['velocity_all'] = np.concatenate(
            [np.asarray(v, dtype=np.float64) for v in velocity_arrays]
        )
        mat_dict['frequency_all'] = np.concatenate(
            [np.asarray(f, dtype=np.float64) for f in frequency_arrays]
        )
        mat_dict['wavelength_all'] = np.concatenate(
            [np.asarray(w, dtype=np.float64) for w in wavelength_arrays]
        )
        mat_dict['slowness_all'] = 1000.0 / mat_dict['velocity_all']

    sio.savemat(str(output_path), mat_dict, do_compression=True)


def export_dinver_txt(
    frequency: np.ndarray,
    slowness_mean: np.ndarray,
    slowness_std: np.ndarray,
    num_points: np.ndarray,
    output_path: Path,
) -> None:
    """Export binned statistics in dinver-compatible format.

    Parameters
    ----------
    frequency : np.ndarray
        Frequency values (Hz)
    slowness_mean : np.ndarray
        Mean slowness values (s/km)
    slowness_std : np.ndarray
        Standard deviation of slowness (s/km)
    num_points : np.ndarray
        Number of points per bin
    output_path : Path
        Output file path

    Notes
    -----
    Format: FreqMean SlowMean SlowStd NumPoints
    """
    output_path = Path(output_path)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Dinver dispersion curve input\n")
        f.write("# FreqMean SlowMean SlowStd NumPoints\n")
        for freq, slow, std, n in zip(frequency, slowness_mean, slowness_std, num_points):
            if np.isfinite(slow) and np.isfinite(freq):
                f.write(f"{freq:.6f} {slow:.6f} {std:.6f} {int(n)}\n")
