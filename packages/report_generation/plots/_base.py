"""Base class providing shared state and helpers for all plot types."""
from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..config import ReportConfig


class BasePlotType:
    """Shared state and computation helpers available to every plot type.

    Each concrete plot class receives a reference to the ReportGenerator
    and copies the data arrays it needs.
    """

    def __init__(self, generator):
        self.velocity_arrays = generator.velocity_arrays
        self.frequency_arrays = generator.frequency_arrays
        self.wavelength_arrays = generator.wavelength_arrays
        self.layer_labels = generator.layer_labels
        self.active_flags = generator.active_flags
        self.array_positions = generator.array_positions
        self.spectrum_data_list = generator.spectrum_data_list
        self.spectrum_visible_flags = generator.spectrum_visible_flags
        self._generator = generator

    # -- shared helpers delegated to the generator's cached computations --

    def _apply_style(self, config):
        from ..styling import apply_matplotlib_defaults
        apply_matplotlib_defaults(config)

    def _get_colors(self, config, n: int):
        from ..styling import get_color_palette
        return get_color_palette(config, n)

    def _compute_smart_axis_limits(self, freq_data, vel_data, config, **kw):
        from ..styling import compute_smart_axis_limits
        return compute_smart_axis_limits(freq_data, vel_data, config, **kw)

    def _apply_legend(self, ax, fig, config):
        from ..styling import apply_legend
        apply_legend(ax, fig, config)

    def _add_colorbar(self, fig, ax, mappable, config, label='Power'):
        from ..styling import add_colorbar
        add_colorbar(fig, ax, mappable, config, label)

    def _save_figure(self, fig, output_path, config):
        from ..styling import save_figure
        save_figure(fig, output_path, config)

    def _compute_binned_aggregates(self, config):
        return self._generator._compute_binned_aggregates(config)

    def _compute_nacd(self, config):
        return self._generator._compute_nacd(config)

    def _compute_grid_smart_limits(self, config, active_indices, **kw):
        return self._generator._compute_grid_smart_limits(config, active_indices, **kw)
