"""Publication figure generation operations.

Wraps the pub_figures generator with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Callable

import numpy as np

from dc_cut.api.validation import validate_output_path


def generate_publication_figure(
    *,
    figure_type: str,
    velocity_arrays: List[np.ndarray],
    frequency_arrays: List[np.ndarray],
    wavelength_arrays: List[np.ndarray],
    labels: List[str],
    output_path: str,
    plot_config: Optional[Dict[str, Any]] = None,
    array_positions: Optional[np.ndarray] = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Generate a publication-quality figure.

    figure_type: one of the supported plot types (e.g. "aggregated", "per_offset",
                 "wavelength", "nearfield_analysis", etc.)

    Returns {"success": bool, "errors": [...], "output_path": str}
    """
    path_validation = validate_output_path(output_path)
    if not path_validation["valid"]:
        return {"success": False, "errors": path_validation["errors"]}

    try:
        if progress_callback:
            progress_callback(10, f"Generating {figure_type} figure...")

        from dc_cut.visualization.pub_figures import PublicationFigureGenerator, PlotConfig

        config = PlotConfig(**(plot_config or {}))
        gen = PublicationFigureGenerator(
            velocity_arrays=velocity_arrays,
            frequency_arrays=frequency_arrays,
            wavelength_arrays=wavelength_arrays,
            labels=labels,
            array_positions=array_positions,
        )

        method_name = f"generate_{figure_type}"
        if not hasattr(gen, method_name):
            return {"success": False, "errors": [f"Unknown figure type: {figure_type}"]}

        method = getattr(gen, method_name)
        method(output_path=output_path, config=config)

        if progress_callback:
            progress_callback(100, "Figure saved.")

        return {"success": True, "errors": [], "output_path": output_path}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}
