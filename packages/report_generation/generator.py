"""ReportGenerator -- orchestrator for report-quality figure generation."""

from __future__ import annotations

import numpy as np
from typing import List, Optional, Tuple, Dict
from pathlib import Path

from .config import PlotConfig
from . import utils
from .plots.frequency.basic import BasicFrequencyPlotsMixin
from .plots.wavelength.basic import BasicWavelengthPlotsMixin
from .plots.canvas.export import CanvasExportMixin
from .plots.offset.analysis import OffsetAnalysisMixin
from .plots.nearfield.analysis import NearFieldAnalysisMixin


class ReportGenerator(
    BasicFrequencyPlotsMixin,
    BasicWavelengthPlotsMixin,
    CanvasExportMixin,
    OffsetAnalysisMixin,
    NearFieldAnalysisMixin,
):
    """Generate publication-quality dispersion curve figures.
    
    This class provides methods to create various types of publication-ready
    figures from dispersion curve data. It supports multiple visualization
    styles and is designed for accessibility with colorblind-friendly palettes.
    """

    def __init__(
        self,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        layer_labels: List[str],
        active_flags: List[bool],
        array_positions: Optional[np.ndarray] = None,
        spectrum_data_list: Optional[List[Optional[Dict[str, np.ndarray]]]] = None,
        spectrum_visible_flags: Optional[List[bool]] = None,
    ):
        """Initialize the figure generator.

        Args:
            velocity_arrays: List of velocity arrays (one per layer/offset)
            frequency_arrays: List of frequency arrays (one per layer/offset)
            wavelength_arrays: List of wavelength arrays (one per layer/offset)
            layer_labels: List of labels for each layer/offset
            active_flags: List of boolean flags indicating if layer is active
            array_positions: Receiver positions for NACD computation (optional)
            spectrum_data_list: List of spectrum data dicts for each layer (optional)
            spectrum_visible_flags: List of booleans indicating if spectrum is visible (optional)
        """
        self.velocity_arrays = velocity_arrays
        self.frequency_arrays = frequency_arrays
        self.wavelength_arrays = wavelength_arrays
        self.layer_labels = layer_labels
        self.active_flags = active_flags
        self.array_positions = array_positions
        self.spectrum_data_list = spectrum_data_list or [None] * len(velocity_arrays)
        self.spectrum_visible_flags = spectrum_visible_flags or [False] * len(velocity_arrays)

        # Precompute aggregated data
        self._binned_avg = None
        self._binned_std = None
        self._bin_centers = None
        self._nacd_values = None

    @classmethod
    def from_controller(cls, controller) -> 'ReportGenerator':
        """Create generator from InteractiveRemovalWithLayers controller.

        Args:
            controller: Instance of InteractiveRemovalWithLayers

        Returns:
            PublicationFigureGenerator instance
        """
        # Extract layer labels (offset_labels in controller)
        # Note: offset_labels includes average labels appended at the end,
        # so we only take labels matching the number of data arrays
        n = len(controller.velocity_arrays)
        layer_labels = list(controller.offset_labels[:n])

        # Extract visibility flags from layers model if available
        active_flags = []
        if hasattr(controller, '_layers_model') and controller._layers_model is not None:
            try:
                for i in range(n):
                    if i < len(controller._layers_model.layers):
                        active_flags.append(controller._layers_model.layers[i].visible)
                    else:
                        active_flags.append(True)  # Default to visible
            except Exception:
                # Fallback if model access fails
                active_flags = [True] * n
        else:
            # No layers model, assume all visible
            active_flags = [True] * n

        # Extract spectrum data from layers if available
        spectrum_data_list = []
        spectrum_visible_flags = []
        if hasattr(controller, '_layers_model') and controller._layers_model is not None:
            try:
                for i in range(n):
                    if i < len(controller._layers_model.layers):
                        layer = controller._layers_model.layers[i]
                        # Check for spectrum_data attribute
                        spec_data = getattr(layer, 'spectrum_data', None)
                        spectrum_data_list.append(spec_data)
                        # Check for spectrum_visible flag
                        spec_visible = getattr(layer, 'spectrum_visible', False)
                        spectrum_visible_flags.append(spec_visible)
                    else:
                        spectrum_data_list.append(None)
                        spectrum_visible_flags.append(False)
            except Exception:
                spectrum_data_list = [None] * n
                spectrum_visible_flags = [False] * n
        else:
            spectrum_data_list = [None] * n
            spectrum_visible_flags = [False] * n

        generator = cls(
            velocity_arrays=controller.velocity_arrays,
            frequency_arrays=controller.frequency_arrays,
            wavelength_arrays=controller.wavelength_arrays,
            layer_labels=layer_labels,
            active_flags=active_flags,
            array_positions=getattr(controller, 'array_positions', None),
            spectrum_data_list=spectrum_data_list,
            spectrum_visible_flags=spectrum_visible_flags,
        )
        
        return generator

    @classmethod
    def from_arrays(
        cls,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        layer_labels: Optional[List[str]] = None,
        array_positions: Optional[np.ndarray] = None,
    ) -> 'ReportGenerator':
        """Create generator from raw data arrays.

        Args:
            velocity_arrays: List of velocity arrays
            frequency_arrays: List of frequency arrays
            wavelength_arrays: List of wavelength arrays
            layer_labels: Optional labels (auto-generated if None)
            array_positions: Optional receiver positions

        Returns:
            PublicationFigureGenerator instance
        """
        n = len(velocity_arrays)
        if layer_labels is None:
            layer_labels = [f"Layer {i+1}" for i in range(n)]
        active_flags = [True] * n

        return cls(
            velocity_arrays=velocity_arrays,
            frequency_arrays=frequency_arrays,
            wavelength_arrays=wavelength_arrays,
            layer_labels=layer_labels,
            active_flags=active_flags,
            array_positions=array_positions,
            spectrum_data_list=None,  # No spectrum data for raw arrays
        )

    def _compute_binned_aggregates(self, config: PlotConfig) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute binned averages and standard deviations.

        Returns:
            (bin_centers, avg_velocities, std_velocities)
        """
        if self._bin_centers is not None:
            return self._bin_centers, self._binned_avg, self._binned_std

        # Import averaging function
        from dc_cut.core.processing.averages import compute_binned_avg_std

        # Gather all active data
        all_freqs = []
        all_vels = []
        for i, active in enumerate(self.active_flags):
            if active:
                all_freqs.append(self.frequency_arrays[i])
                all_vels.append(self.velocity_arrays[i])

        if not all_freqs:
            # No active data
            return np.array([]), np.array([]), np.array([])

        # Concatenate
        freqs_concat = np.concatenate(all_freqs)
        vels_concat = np.concatenate(all_vels)

        # Compute binned statistics
        bin_centers, avg_vals, std_vals = compute_binned_avg_std(
            freqs_concat, vels_concat,
            num_bins=50,
            log_bias=0.7
        )

        # Cache results
        self._bin_centers = bin_centers
        self._binned_avg = avg_vals
        self._binned_std = std_vals

        return bin_centers, avg_vals, std_vals

    def _compute_nacd(self, config: PlotConfig) -> Optional[np.ndarray]:
        """Compute NACD values for aggregated data.

        Returns:
            Array of NACD values matching bin_centers, or None if not possible
        """
        if self._nacd_values is not None:
            return self._nacd_values

        if self.array_positions is None:
            return None

        # Import NACD computation
        try:
            from dc_cut.core.processing.nearfield import compute_nacd_for_all_data
        except ImportError:
            return None

        # Get binned data
        bin_centers, _, _ = self._compute_binned_aggregates(config)
        if len(bin_centers) == 0:
            return None

        # Gather all active wavelengths
        all_wavelengths = []
        for i, active in enumerate(self.active_flags):
            if active:
                all_wavelengths.append(self.wavelength_arrays[i])

        if not all_wavelengths:
            return None

        wavelengths_concat = np.concatenate(all_wavelengths)

        # Compute NACD for wavelengths, then map to bin centers via frequency
        # For simplicity, compute average NACD per bin
        all_freqs = []
        for i, active in enumerate(self.active_flags):
            if active:
                all_freqs.append(self.frequency_arrays[i])
        freqs_concat = np.concatenate(all_freqs)

        # Compute NACD for all points
        aperture = np.max(self.array_positions) - np.min(self.array_positions)
        nacd_all = aperture / wavelengths_concat

        # Bin NACD values by frequency
        nacd_binned = []
        for bc in bin_centers:
            # Find points near this bin center (within half bin width)
            if len(bin_centers) > 1:
                half_width = (bin_centers[1] - bin_centers[0]) / 2
            else:
                half_width = bc * 0.1

            mask = np.abs(freqs_concat - bc) < half_width
            if np.any(mask):
                nacd_binned.append(np.mean(nacd_all[mask]))
            else:
                nacd_binned.append(np.nan)

        self._nacd_values = np.array(nacd_binned)
        return self._nacd_values

    def _compute_grid_smart_limits(
        self,
        config: PlotConfig,
        active_indices: List[int],
        x_margin_left: float = 1.0,
        x_margin_right: float = 5.0,
        y_margin: float = 100.0,
        y_floor: float = 0.0,
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Compute consistent axis limits across all active offsets.

        Args:
            config: PlotConfig with xlim/ylim overrides
            active_indices: List of active offset indices
            x_margin_left: Left margin for frequency axis (Hz)
            x_margin_right: Right margin for frequency axis (Hz)
            y_margin: Margin for velocity axis (m/s)
            y_floor: Minimum Y value (0 to hide negatives)

        Returns:
            Tuple of (xlim, ylim) tuples for consistent grid axes
        """
        # Use explicit config limits if set
        if config.xlim is not None and config.ylim is not None:
            return config.xlim, config.ylim

        # Gather all data from active offsets
        all_freqs = []
        all_vels = []
        for i in active_indices:
            if len(self.frequency_arrays[i]) > 0:
                all_freqs.extend(self.frequency_arrays[i])
                all_vels.extend(self.velocity_arrays[i])

        xlim = config.xlim
        ylim = config.ylim

        if xlim is None and len(all_freqs) > 0:
            freq_min = float(np.nanmin(all_freqs))
            freq_max = float(np.nanmax(all_freqs))
            xlim = (max(0.0, freq_min - x_margin_left), freq_max + x_margin_right)

        if ylim is None and len(all_vels) > 0:
            vel_min = float(np.nanmin(all_vels))
            vel_max = float(np.nanmax(all_vels))
            ylim_low = max(y_floor, vel_min - y_margin)
            ylim = (ylim_low, vel_max + y_margin)

        return xlim, ylim

    # Utility methods (delegated to utils module)
    def _apply_style(self, config: PlotConfig):
        """Apply publication styling to matplotlib."""
        utils.apply_style(config)

    def _get_colors(self, config: PlotConfig, n: int) -> List[str]:
        """Get n colors from the configured palette."""
        return utils.get_colors(config, n)

    def _compute_smart_axis_limits(
        self,
        freq_data: np.ndarray,
        vel_data: np.ndarray,
        config: PlotConfig,
        x_margin_left: float = 1.0,
        x_margin_right: float = 5.0,
        y_margin: float = 100.0,
        y_floor: float = 0.0,
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Compute smart axis limits based on dispersion curve data."""
        return utils.compute_smart_axis_limits(
            freq_data, vel_data, config, x_margin_left, x_margin_right, y_margin, y_floor
        )

    def _apply_legend(self, ax, fig, config: PlotConfig):
        """Apply legend with support for outside positions."""
        utils.apply_legend(ax, fig, config)

    def _add_colorbar(self, fig, ax, mappable, config: PlotConfig, label: str = 'Power'):
        """Add colorbar by appending axes."""
        utils.add_colorbar(fig, ax, mappable, config, label)

    def _save_figure(self, fig, output_path: str, config: PlotConfig):
        """Helper method to save figure with proper settings."""
        utils.save_figure(fig, output_path, config)
