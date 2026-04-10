"""Analysis operations: averages, near-field, statistics.

Wraps core processing functions with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Iterable

import numpy as np

from dc_cut.api.config import AverageConfig, NearFieldConfig


def compute_averages(
    velocity_arrays: List[np.ndarray],
    domain_arrays: List[np.ndarray],
    config: AverageConfig,
) -> Dict[str, Any]:
    """Compute binned averages across offsets.

    Returns {"success": bool, "errors": [...], "bin_centers": ..., "avg": ..., "std": ...}
    """
    try:
        v_all = np.concatenate(velocity_arrays)
        d_all = np.concatenate(domain_arrays)

        if v_all.size == 0:
            return {"success": False, "errors": ["No data points to average."]}

        if config.domain == "frequency":
            from dc_cut.core.processing.averages import compute_binned_avg_std
            centers, avg, std = compute_binned_avg_std(
                d_all, v_all,
                num_bins=config.num_bins,
                log_bias=config.log_bias,
            )
        else:
            from dc_cut.core.processing.averages import compute_binned_avg_std_wavelength
            centers, avg, std = compute_binned_avg_std_wavelength(
                d_all, v_all,
                num_bins=config.num_bins,
                log_bias=config.log_bias,
            )

        return {
            "success": True,
            "errors": [],
            "bin_centers": centers,
            "avg": avg,
            "std": std,
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def compute_nacd(
    velocity: np.ndarray,
    frequency: np.ndarray,
    array_positions: Iterable[float],
    config: NearFieldConfig,
) -> Dict[str, Any]:
    """Compute NACD values for a set of picks.

    Returns {"success": bool, "errors": [...], "nacd": ..., "nearfield_mask": ...}
    """
    try:
        from dc_cut.core.processing.nearfield import compute_nacd_array

        if not hasattr(array_positions, '__len__') or len(list(array_positions)) < 2:
            arr_pos = np.arange(0, config.receiver_dx * config.n_phones, config.receiver_dx)
        else:
            arr_pos = np.asarray(list(array_positions), float)

        nacd = compute_nacd_array(arr_pos, frequency, velocity)
        mask = nacd < config.threshold

        return {
            "success": True,
            "errors": [],
            "nacd": nacd,
            "nearfield_mask": mask,
            "nearfield_count": int(np.sum(mask)),
        }
    except Exception as e:
        return {"success": False, "errors": [str(e)]}
