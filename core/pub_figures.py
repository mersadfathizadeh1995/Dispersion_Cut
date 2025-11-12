"""Publication-quality dispersion curve figure generation.

This module provides standalone functionality to generate publication-ready
dispersion curve plots with uncertainty visualization and near-field marking.

Usage:
    from dc_cut.core.pub_figures import PublicationFigureGenerator

    # From interactive session
    gen = PublicationFigureGenerator.from_controller(controller)
    gen.generate_aggregated_plot(output_path='figure.pdf')

    # From saved data
    gen = PublicationFigureGenerator.from_arrays(
        velocity_arrays, frequency_arrays, wavelength_arrays,
        layer_labels, array_positions
    )
    gen.generate_per_offset_plot(output_path='offsets.pdf')
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Colorblind-friendly palettes
COLORBLIND_PALETTE = {
    'vibrant': ['#0173B2', '#DE8F05', '#029E73', '#CC78BC', '#CA9161', '#949494', '#ECE133'],
    'muted': ['#332288', '#88CCEE', '#44AA99', '#117733', '#999933', '#DDCC77', '#CC6677', '#882255', '#AA4499'],
    'bright': ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB']
}


@dataclass
class PlotConfig:
    """Configuration for publication-quality plots."""
    # Figure settings
    figsize: Tuple[float, float] = (8, 6)
    dpi: int = 300

    # Styling
    font_family: str = 'serif'
    font_size: int = 11
    line_width: float = 1.5
    marker_size: float = 4.0

    # Colors
    color_palette: str = 'vibrant'  # 'vibrant', 'muted', or 'bright'
    uncertainty_alpha: float = 0.3
    near_field_alpha: float = 0.4

    # Near-field marking
    mark_near_field: bool = True
    near_field_style: str = 'faded'  # 'faded', 'crossed', or 'none'
    nacd_threshold: float = 1.0

    # Axes
    show_grid: bool = True
    grid_alpha: float = 0.3

    # Labels
    xlabel: str = 'Frequency (Hz)'
    ylabel: str = 'Phase Velocity (m/s)'

    # Limits (None = auto)
    xlim: Optional[Tuple[float, float]] = None
    ylim: Optional[Tuple[float, float]] = None

    # Output
    output_format: str = 'pdf'  # 'pdf', 'png', 'svg', 'eps'
    tight_layout: bool = True


class PublicationFigureGenerator:
    """Generate publication-quality dispersion curve figures."""

    def __init__(
        self,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        layer_labels: List[str],
        active_flags: List[bool],
        array_positions: Optional[np.ndarray] = None,
    ):
        """Initialize the figure generator.

        Args:
            velocity_arrays: List of velocity arrays (one per layer/offset)
            frequency_arrays: List of frequency arrays (one per layer/offset)
            wavelength_arrays: List of wavelength arrays (one per layer/offset)
            layer_labels: List of labels for each layer/offset
            active_flags: List of boolean flags indicating if layer is active
            array_positions: Receiver positions for NACD computation (optional)
        """
        self.velocity_arrays = velocity_arrays
        self.frequency_arrays = frequency_arrays
        self.wavelength_arrays = wavelength_arrays
        self.layer_labels = layer_labels
        self.active_flags = active_flags
        self.array_positions = array_positions

        # Precompute aggregated data
        self._binned_avg = None
        self._binned_std = None
        self._bin_centers = None
        self._nacd_values = None

    @classmethod
    def from_controller(cls, controller) -> 'PublicationFigureGenerator':
        """Create generator from InteractiveRemovalWithLayers controller.

        Args:
            controller: Instance of InteractiveRemovalWithLayers

        Returns:
            PublicationFigureGenerator instance
        """
        return cls(
            velocity_arrays=controller.velocity_arrays,
            frequency_arrays=controller.frequency_arrays,
            wavelength_arrays=controller.wavelength_arrays,
            layer_labels=controller.layer_labels,
            active_flags=controller.active_flags,
            array_positions=getattr(controller, 'array_positions', None),
        )

    @classmethod
    def from_arrays(
        cls,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        layer_labels: Optional[List[str]] = None,
        array_positions: Optional[np.ndarray] = None,
    ) -> 'PublicationFigureGenerator':
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
        )

    def _compute_binned_aggregates(self, config: PlotConfig) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute binned averages and standard deviations.

        Returns:
            (bin_centers, avg_velocities, std_velocities)
        """
        if self._bin_centers is not None:
            return self._bin_centers, self._binned_avg, self._binned_std

        # Import averaging function
        from dc_cut.core.averages import compute_binned_avg_std

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
            from dc_cut.core.nearfield import compute_nacd_for_all_data
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

    def _apply_style(self, config: PlotConfig):
        """Apply publication styling to matplotlib."""
        plt.rcParams.update({
            'font.family': config.font_family,
            'font.size': config.font_size,
            'axes.linewidth': 1.0,
            'axes.labelsize': config.font_size,
            'xtick.labelsize': config.font_size - 1,
            'ytick.labelsize': config.font_size - 1,
            'legend.fontsize': config.font_size - 1,
            'lines.linewidth': config.line_width,
            'lines.markersize': config.marker_size,
            'figure.dpi': config.dpi,
        })

    def _get_colors(self, config: PlotConfig, n: int) -> List[str]:
        """Get n colors from the configured palette."""
        palette = COLORBLIND_PALETTE.get(config.color_palette, COLORBLIND_PALETTE['vibrant'])
        # Repeat palette if needed
        colors = []
        while len(colors) < n:
            colors.extend(palette)
        return colors[:n]

    def generate_aggregated_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate aggregated dispersion curve with uncertainty envelope.

        Shows binned average with ±1σ envelope, marks near-field if enabled.

        Args:
            output_path: Path to save figure (if None, returns Figure object)
            config: Plot configuration (uses defaults if None)

        Returns:
            Matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Create figure
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Compute aggregated data
        bin_centers, avg_vals, std_vals = self._compute_binned_aggregates(config)

        if len(bin_centers) == 0:
            ax.text(0.5, 0.5, 'No active data', ha='center', va='center', transform=ax.transAxes)
            return fig

        # Compute NACD if enabled
        nacd_vals = None
        if config.mark_near_field:
            nacd_vals = self._compute_nacd(config)

        # Separate near-field and far-field points
        if nacd_vals is not None and config.near_field_style != 'none':
            near_field_mask = nacd_vals < config.nacd_threshold
            far_field_mask = ~near_field_mask
        else:
            near_field_mask = np.zeros(len(bin_centers), dtype=bool)
            far_field_mask = np.ones(len(bin_centers), dtype=bool)

        colors = self._get_colors(config, 1)
        main_color = colors[0]

        # Plot far-field points (solid)
        if np.any(far_field_mask):
            ax.semilogx(
                bin_centers[far_field_mask],
                avg_vals[far_field_mask],
                'o-',
                color=main_color,
                label='Mean velocity',
                markersize=config.marker_size,
                linewidth=config.line_width,
            )

            # Uncertainty envelope (far-field)
            ax.fill_between(
                bin_centers[far_field_mask],
                avg_vals[far_field_mask] - std_vals[far_field_mask],
                avg_vals[far_field_mask] + std_vals[far_field_mask],
                alpha=config.uncertainty_alpha,
                color=main_color,
                label='±1σ envelope',
            )

        # Plot near-field points (faded or crossed)
        if np.any(near_field_mask):
            if config.near_field_style == 'faded':
                ax.semilogx(
                    bin_centers[near_field_mask],
                    avg_vals[near_field_mask],
                    'o-',
                    color=main_color,
                    alpha=config.near_field_alpha,
                    markersize=config.marker_size,
                    linewidth=config.line_width,
                    label='Near-field (faded)',
                )
                ax.fill_between(
                    bin_centers[near_field_mask],
                    avg_vals[near_field_mask] - std_vals[near_field_mask],
                    avg_vals[near_field_mask] + std_vals[near_field_mask],
                    alpha=config.uncertainty_alpha * config.near_field_alpha,
                    color=main_color,
                )
            elif config.near_field_style == 'crossed':
                ax.semilogx(
                    bin_centers[near_field_mask],
                    avg_vals[near_field_mask],
                    'x',
                    color=main_color,
                    alpha=config.near_field_alpha,
                    markersize=config.marker_size * 1.5,
                    label='Near-field (crossed)',
                )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        if config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc='best')

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')

        return fig

    def generate_per_offset_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        max_offsets: int = 10,
    ) -> Figure:
        """Generate per-offset dispersion curves.

        Shows individual curves for each active layer/offset.

        Args:
            output_path: Path to save figure (if None, returns Figure object)
            config: Plot configuration (uses defaults if None)
            max_offsets: Maximum number of offsets to plot (to avoid clutter)

        Returns:
            Matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Create figure
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Get active indices
        active_indices = [i for i, active in enumerate(self.active_flags) if active]

        if not active_indices:
            ax.text(0.5, 0.5, 'No active data', ha='center', va='center', transform=ax.transAxes)
            return fig

        # Limit number of offsets
        if len(active_indices) > max_offsets:
            step = len(active_indices) // max_offsets
            active_indices = active_indices[::step][:max_offsets]

        # Get colors
        colors = self._get_colors(config, len(active_indices))

        # Plot each offset
        for idx, i in enumerate(active_indices):
            freqs = self.frequency_arrays[i]
            vels = self.velocity_arrays[i]
            label = self.layer_labels[i]

            ax.semilogx(
                freqs,
                vels,
                'o-',
                color=colors[idx],
                label=label,
                markersize=config.marker_size * 0.7,
                linewidth=config.line_width * 0.8,
                alpha=0.7,
            )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        if config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc='best', ncol=2 if len(active_indices) > 6 else 1)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')

        return fig

    def generate_uncertainty_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate uncertainty visualization plot.

        Shows coefficient of variation (CV = σ/μ) as a function of frequency.

        Args:
            output_path: Path to save figure (if None, returns Figure object)
            config: Plot configuration (uses defaults if None)

        Returns:
            Matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Create figure
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Compute aggregated data
        bin_centers, avg_vals, std_vals = self._compute_binned_aggregates(config)

        if len(bin_centers) == 0:
            ax.text(0.5, 0.5, 'No active data', ha='center', va='center', transform=ax.transAxes)
            return fig

        # Compute coefficient of variation (CV)
        cv = np.zeros_like(std_vals)
        mask = avg_vals > 0
        cv[mask] = (std_vals[mask] / avg_vals[mask]) * 100  # as percentage

        # Compute NACD if enabled
        nacd_vals = None
        if config.mark_near_field:
            nacd_vals = self._compute_nacd(config)

        # Separate near-field and far-field
        if nacd_vals is not None and config.near_field_style != 'none':
            near_field_mask = nacd_vals < config.nacd_threshold
            far_field_mask = ~near_field_mask
        else:
            near_field_mask = np.zeros(len(bin_centers), dtype=bool)
            far_field_mask = np.ones(len(bin_centers), dtype=bool)

        colors = self._get_colors(config, 1)
        main_color = colors[0]

        # Plot far-field CV
        if np.any(far_field_mask):
            ax.semilogx(
                bin_centers[far_field_mask],
                cv[far_field_mask],
                'o-',
                color=main_color,
                label='Coefficient of variation',
                markersize=config.marker_size,
                linewidth=config.line_width,
            )

        # Plot near-field CV (faded)
        if np.any(near_field_mask) and config.near_field_style == 'faded':
            ax.semilogx(
                bin_centers[near_field_mask],
                cv[near_field_mask],
                'o-',
                color=main_color,
                alpha=config.near_field_alpha,
                markersize=config.marker_size,
                linewidth=config.line_width,
                label='Near-field (faded)',
            )
        elif np.any(near_field_mask) and config.near_field_style == 'crossed':
            ax.semilogx(
                bin_centers[near_field_mask],
                cv[near_field_mask],
                'x',
                color=main_color,
                alpha=config.near_field_alpha,
                markersize=config.marker_size * 1.5,
                label='Near-field (crossed)',
            )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel('Coefficient of Variation (%)')

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        ax.set_ylim(bottom=0)  # CV is always positive

        # Legend
        ax.legend(loc='best')

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            fig.savefig(output_path, dpi=config.dpi, bbox_inches='tight')

        return fig
