from __future__ import annotations

import numpy as np
from typing import Dict, Tuple


def biased_edges(min_p: float, max_p: float, n: int, bias: float = 1.0) -> np.ndarray:
    """Return n+1 log‑spaced edges, biased toward min_p by a power parameter."""
    log_min, log_max = np.log10(min_p), np.log10(max_p)
    t = np.linspace(0.0, 1.0, n + 1) ** bias
    return 10 ** (log_min + (log_max - log_min) * t)


def bin_freqvel(vel: np.ndarray,
                freq_or_wave: np.ndarray,
                *,
                min_p: float,
                max_p: float,
                n: int,
                bias: float) -> Dict[str, np.ndarray]:
    """Bin velocity by frequency or wavelength; return means and std per bin."""
    edges = biased_edges(min_p, max_p, n, bias)
    idx = np.digitize(freq_or_wave, edges, right=False)
    vel_mean = np.full(n, np.nan)
    vel_std = np.full(n, np.nan)
    p_mean = np.full(n, np.nan)
    for b in range(1, n + 1):
        m = idx == b
        if np.any(m):
            vel_mean[b - 1] = np.mean(vel[m])
            vel_std[b - 1] = np.std(vel[m])
            p_mean[b - 1] = np.mean(freq_or_wave[m])
    return {"FreqMean": p_mean, "VelMean": vel_mean, "VelStd": vel_std}


def compute_avg_by_frequency(vel_all: np.ndarray,
                             freq_all: np.ndarray,
                             *,
                             min_freq: float,
                             max_freq: float,
                             bins: int,
                             bias: float) -> Dict[str, np.ndarray]:
    return bin_freqvel(vel_all, freq_all,
                       min_p=min_freq, max_p=max_freq, n=bins, bias=bias)


def compute_avg_by_wavelength(vel_all: np.ndarray,
                              wave_all: np.ndarray,
                              *,
                              min_wave: float,
                              max_wave: float,
                              bins: int,
                              bias: float) -> Dict[str, np.ndarray]:
    return bin_freqvel(vel_all, wave_all,
                       min_p=min_wave, max_p=max_wave, n=bins, bias=bias)


def compute_binned_avg_std(freq_all: np.ndarray,
                           vel_all: np.ndarray,
                           *,
                           num_bins: int = 50,
                           log_bias: float = 0.7) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute binned averages and standard deviations for publication figures.

    Args:
        freq_all: Array of frequency values
        vel_all: Array of velocity values
        num_bins: Number of bins (default: 50)
        log_bias: Logarithmic bias for bin spacing (default: 0.7)

    Returns:
        Tuple of (bin_centers, avg_velocities, std_velocities)
    """
    # Handle edge cases
    if len(freq_all) == 0 or len(vel_all) == 0:
        return np.array([]), np.array([]), np.array([])

    # Compute min/max from data
    freq_valid = freq_all[np.isfinite(freq_all) & (freq_all > 0)]
    if len(freq_valid) == 0:
        return np.array([]), np.array([]), np.array([])

    min_freq = float(np.min(freq_valid))
    max_freq = float(np.max(freq_valid))

    # Compute binned statistics
    result = compute_avg_by_frequency(
        vel_all, freq_all,
        min_freq=min_freq,
        max_freq=max_freq,
        bins=num_bins,
        bias=log_bias
    )

    # Extract results
    bin_centers = result['FreqMean']
    avg_vals = result['VelMean']
    std_vals = result['VelStd']

    # Filter out NaN values
    mask = np.isfinite(bin_centers) & np.isfinite(avg_vals) & np.isfinite(std_vals)

    return bin_centers[mask], avg_vals[mask], std_vals[mask]










