"""Export operations: save data to various file formats.

Wraps core I/O export functions with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Sequence, Callable

import numpy as np

from dc_cut.api.config import ExportConfig
from dc_cut.api.validation import validate_output_path


def export_data(
    config: ExportConfig,
    *,
    stats: Optional[Dict[str, np.ndarray]] = None,
    freq_mean: Optional[Sequence[float]] = None,
    slow_mean: Optional[Sequence[float]] = None,
    dinver_std: Optional[Sequence[float]] = None,
    num_points: Optional[Sequence[int]] = None,
    velocity_arrays: Optional[List[np.ndarray]] = None,
    frequency_arrays: Optional[List[np.ndarray]] = None,
    wavelength_arrays: Optional[List[np.ndarray]] = None,
    labels: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Export data to the specified format.

    Returns {"success": bool, "errors": [...], "output_path": str}
    """
    path_validation = validate_output_path(config.output_path)
    if not path_validation["valid"]:
        return {"success": False, "errors": path_validation["errors"]}

    try:
        if progress_callback:
            progress_callback(10, f"Exporting as {config.format}...")

        if config.format == "geopsy_txt" and stats is not None:
            from dc_cut.core.io.export import write_geopsy_txt
            write_geopsy_txt(stats, config.output_path)

        elif config.format == "csv_stats" and freq_mean is not None:
            from dc_cut.core.io.export import write_passive_stats_csv
            write_passive_stats_csv(
                freq_mean, slow_mean or [], dinver_std or [], num_points or [],
                config.output_path,
            )

        elif config.format == "matlab":
            from dc_cut.core.io.export import export_to_mat
            export_to_mat(
                velocity_arrays=velocity_arrays or [],
                frequency_arrays=frequency_arrays or [],
                wavelength_arrays=wavelength_arrays or [],
                labels=labels or [],
                output_path=config.output_path,
            )

        else:
            return {"success": False, "errors": [f"Unsupported export format: {config.format}"]}

        if progress_callback:
            progress_callback(100, "Export complete.")

        return {"success": True, "errors": [], "output_path": config.output_path}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}
