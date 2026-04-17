from __future__ import annotations

import csv
from typing import Sequence, Dict
import numpy as np


def write_geopsy_txt(stats: Dict[str, np.ndarray], out_filename: str) -> None:
    """Write Geopsy-compatible TXT from stats dict.

    Expects keys: 'FreqMean', 'SlowMean', 'DinverStd', 'NumPoints'.
    Format: freq slow DinverStd numPoints
    """
    freq = np.asarray(stats['FreqMean'])
    slow = np.asarray(stats['SlowMean'])
    dstd = np.asarray(stats['DinverStd'])
    npnts = np.asarray(stats['NumPoints'])

    with open(out_filename, "w", encoding="utf-8") as f:
        for i in range(len(freq)):
            if not np.isfinite(slow[i]):
                continue
            f.write(f"{float(freq[i]):16.6f} {float(slow[i]):12.10f} {float(dstd[i]):16.12f} {int(npnts[i]):16.0f}\n")


def write_passive_stats_csv(freq_mean: Sequence[float], slow_mean: Sequence[float], dinver_std: Sequence[float], num_points: Sequence[int], out_filename: str) -> None:
    """Write Passive Stats CSV with header.

    Columns: FreqMean, SlowMean, DinverStd, NumPoints
    """
    with open(out_filename, 'w', newline='', encoding='utf-8') as fw:
        w = csv.writer(fw)
        w.writerow(["FreqMean","SlowMean","DinverStd","NumPoints"])
        for i in range(len(freq_mean)):
            w.writerow([float(freq_mean[i]), float(slow_mean[i]), float(dinver_std[i]), int(num_points[i])])


def export_to_mat(
    velocity_arrays: Sequence[np.ndarray],
    frequency_arrays: Sequence[np.ndarray],
    wavelength_arrays: Sequence[np.ndarray],
    labels: Sequence[str],
    output_path: str,
    site_name: str = "Unknown",
    stage_name: str = "Export",
    wave_type: str = "Rayleigh_Vertical",
    **extra_metadata
) -> None:
    """Export dispersion curve data to MATLAB .mat file.

    Parameters
    ----------
    velocity_arrays : Sequence[np.ndarray]
        List of velocity arrays (m/s) per layer
    frequency_arrays : Sequence[np.ndarray]
        List of frequency arrays (Hz) per layer
    wavelength_arrays : Sequence[np.ndarray]
        List of wavelength arrays (m) per layer
    labels : Sequence[str]
        List of layer labels
    output_path : str
        Output file path
    site_name : str
        Site name for metadata
    stage_name : str
        Stage name for metadata
    wave_type : str
        Wave type (e.g., 'Rayleigh_Vertical')
    **extra_metadata
        Additional metadata to include
    """
    try:
        import scipy.io as sio
    except ImportError:
        raise ImportError("SciPy is required to write MAT files.")

    mat_dict = {
        'site_name': site_name,
        'stage': stage_name,
        'wave_type': wave_type,
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
        mat_dict[f'slowness_{idx}'] = np.where(vel_arr > 0, 1000.0 / vel_arr, np.nan)
        mat_dict[f'label_{idx}'] = label

    if velocity_arrays:
        all_vel = np.concatenate([np.asarray(v, dtype=np.float64) for v in velocity_arrays])
        all_freq = np.concatenate([np.asarray(f, dtype=np.float64) for f in frequency_arrays])
        all_wlen = np.concatenate([np.asarray(w, dtype=np.float64) for w in wavelength_arrays])
        
        mat_dict['velocity_all'] = all_vel
        mat_dict['frequency_all'] = all_freq
        mat_dict['wavelength_all'] = all_wlen
        mat_dict['slowness_all'] = np.where(all_vel > 0, 1000.0 / all_vel, np.nan)

    sio.savemat(str(output_path), mat_dict, do_compression=True)











