"""
Average-with-uncertainty figure type plugin.

Computes binned mean ± σ across all source offsets from a PKL file.
Returns an AggregatedCurve (the computed result) plus optional shadow
curves (the individual offsets styled as faded background).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ..figure_types import FigureTypePlugin, registry
from .. import subplot_types as ST


class AverageCurvePlugin:
    """Figure type: average dispersion curve with uncertainty envelope."""

    @property
    def type_id(self) -> str:
        return "average_curve"

    @property
    def display_name(self) -> str:
        return "Average with Uncertainty"

    @property
    def accepted_subplot_types(self) -> Sequence[str]:
        return (ST.COMBINED, ST.DISPERSION)

    def load_data(
        self,
        pkl_path: str = "",
        npz_path: str = "",
        selected_offsets: Optional[List[str]] = None,
        num_bins: int = 50,
        log_bias: float = 0.7,
        x_domain: str = "frequency",
        **kwargs,
    ) -> Dict[str, Any]:
        """Load curves, compute binned average ± std.

        Returns
        -------
        dict
            ``{'aggregated': AggregatedCurve,
               'shadow_curves': [OffsetCurve, ...],
               'spectra': []}``
        """
        from ...io.pkl_reader import read_pkl
        from ..models import AggregatedCurve

        curves = read_pkl(pkl_path) if pkl_path else []

        if selected_offsets is not None:
            curves = [c for c in curves if c.name in selected_offsets]

        if not curves:
            return {"aggregated": None, "shadow_curves": [], "spectra": []}

        # Compute binned average
        bin_centers, avg_vals, std_vals = self._compute_aggregates(
            curves, num_bins, log_bias, x_domain,
        )

        agg = AggregatedCurve(
            name="Average",
            bin_centers=bin_centers,
            avg_vals=avg_vals,
            std_vals=std_vals,
            num_bins=num_bins,
            log_bias=log_bias,
            x_domain=x_domain,
        )

        # Style shadow curves as faded
        for c in curves:
            c.line_width = 1.0
            c.marker_size = 0.0
            c.marker_visible = False

        return {"aggregated": agg, "shadow_curves": curves, "spectra": []}

    def settings_fields(self) -> List[Dict[str, Any]]:
        return [
            {"key": "x_domain", "label": "X Axis", "type": "combo",
             "default": "frequency", "options": ["frequency", "wavelength"]},
            {"key": "num_bins", "label": "Bins", "type": "int",
             "default": 50, "min": 10, "max": 200},
            {"key": "log_bias", "label": "Log Bias", "type": "float",
             "default": 0.7, "min": 0.1, "max": 2.0},
        ]

    @staticmethod
    def _compute_aggregates(
        curves, num_bins: int, log_bias: float, x_domain: str,
    ):
        """Concatenate curve data and compute binned mean ± std."""
        from dc_cut.core.processing.averages import (
            compute_binned_avg_std,
            compute_binned_avg_std_wavelength,
        )

        all_x, all_y = [], []
        for c in curves:
            if not c.has_data:
                continue
            if x_domain == "wavelength" and c.wavelength.size > 0:
                all_x.append(c.wavelength)
            else:
                all_x.append(c.frequency)
            all_y.append(c.velocity)

        if not all_x:
            return np.array([]), np.array([]), np.array([])

        x_cat = np.concatenate(all_x)
        y_cat = np.concatenate(all_y)

        if x_domain == "wavelength":
            return compute_binned_avg_std_wavelength(
                x_cat, y_cat, num_bins=num_bins, log_bias=log_bias,
            )
        return compute_binned_avg_std(
            x_cat, y_cat, num_bins=num_bins, log_bias=log_bias,
        )


# Auto-register when this module is imported
_plugin = AverageCurvePlugin()
registry.register(_plugin)
