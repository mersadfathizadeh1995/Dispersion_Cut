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
    marker_style: str = 'o'  # 'o', 's', '^', 'D', 'x', '+', '.'

    # Title (NEW)
    title: Optional[str] = None
    title_fontsize: Optional[int] = None

    # Legend (NEW)
    legend_position: str = 'best'
    legend_columns: int = 1
    legend_frameon: bool = False

    # Colors
    color_palette: str = 'vibrant'  # 'vibrant', 'muted', 'bright', 'high_contrast'
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

    # Spectrum options (for offset analysis with spectrum background)
    spectrum_colormap: str = 'viridis'
    spectrum_render_mode: str = 'imshow'  # 'imshow' or 'contour'
    spectrum_alpha: float = 0.8
    spectrum_levels: int = 30

    # Peak/curve overlay options (for curves on spectrum background)
    peak_color: str = '#FFFFFF'  # White default for visibility
    peak_outline: bool = True
    peak_outline_color: str = '#000000'
    peak_line_width: float = 2.5


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
        spectrum_data_list: Optional[List[Optional[Dict[str, np.ndarray]]]] = None,
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
        """
        self.velocity_arrays = velocity_arrays
        self.frequency_arrays = frequency_arrays
        self.wavelength_arrays = wavelength_arrays
        self.layer_labels = layer_labels
        self.active_flags = active_flags
        self.array_positions = array_positions
        self.spectrum_data_list = spectrum_data_list or [None] * len(velocity_arrays)

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
        if hasattr(controller, '_layers_model') and controller._layers_model is not None:
            try:
                for i in range(n):
                    if i < len(controller._layers_model.layers):
                        layer = controller._layers_model.layers[i]
                        # Check for spectrum_data attribute
                        spec_data = getattr(layer, 'spectrum_data', None)
                        spectrum_data_list.append(spec_data)
                    else:
                        spectrum_data_list.append(None)
            except Exception:
                spectrum_data_list = [None] * n
        else:
            spectrum_data_list = [None] * n

        generator = cls(
            velocity_arrays=controller.velocity_arrays,
            frequency_arrays=controller.frequency_arrays,
            wavelength_arrays=controller.wavelength_arrays,
            layer_labels=layer_labels,
            active_flags=active_flags,
            array_positions=getattr(controller, 'array_positions', None),
            spectrum_data_list=spectrum_data_list,
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
        # Determine if we're using a raster format (needs white background)
        is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']

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
            # Set backgrounds: white for raster, transparent for vector
            'figure.facecolor': 'white' if is_raster else 'none',
            'axes.facecolor': 'white',
            'savefig.facecolor': 'white' if is_raster else 'none',
            'savefig.edgecolor': 'none',
        })

    def _get_colors(self, config: PlotConfig, n: int) -> List[str]:
        """Get n colors from the configured palette with robust fallback."""
        try:
            # Get palette with fallback to vibrant
            palette_name = config.color_palette if config.color_palette in COLORBLIND_PALETTE else 'vibrant'
            palette = COLORBLIND_PALETTE.get(palette_name, COLORBLIND_PALETTE['vibrant'])

            # Ensure palette is a list
            if not isinstance(palette, (list, tuple)) or len(palette) == 0:
                palette = COLORBLIND_PALETTE['vibrant']

            # Repeat palette if needed
            colors = []
            while len(colors) < n:
                colors.extend(palette)
            return colors[:n]
        except Exception:
            # Ultimate fallback: return matplotlib default colors
            import matplotlib.pyplot as plt
            prop_cycle = plt.rcParams['axes.prop_cycle']
            default_colors = prop_cycle.by_key()['color']
            colors = []
            while len(colors) < n:
                colors.extend(default_colors)
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
            # Determine transparency based on format
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

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
            # Determine transparency based on format
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

        return fig

    # ==================== WAVELENGTH-DOMAIN PLOTS (STEP 1) ====================

    def _compute_wavelength_aggregates(self, num_bins: int = 50, log_bias: float = 0.7):
        """Compute binned wavelength-domain aggregates (cached)."""
        if self._binned_avg is not None and hasattr(self, '_binned_wave_centers'):
            return

        # Aggregate all visible data
        wave_all = np.concatenate([
            self.wavelength_arrays[i]
            for i in range(len(self.wavelength_arrays))
            if self.active_flags[i]
        ])
        vel_all = np.concatenate([
            self.velocity_arrays[i]
            for i in range(len(self.velocity_arrays))
            if self.active_flags[i]
        ])

        # Compute binned statistics
        from dc_cut.core.averages import compute_binned_avg_std_wavelength
        bin_centers, avg_vals, std_vals = compute_binned_avg_std_wavelength(
            wave_all, vel_all, num_bins=num_bins, log_bias=log_bias
        )

        self._binned_wave_centers = bin_centers
        self._binned_wave_avg = avg_vals
        self._binned_wave_std = std_vals

    def generate_aggregated_wavelength_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate aggregated dispersion curve in wavelength domain.

        Shows binned average with ±1σ envelope in wavelength domain.
        Useful for depth-related interpretations (λ/2 or λ/3 rules).

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        # Update xlabel for wavelength
        if config.xlabel == 'Frequency (Hz)':
            config.xlabel = 'Wavelength (m)'

        self._apply_style(config)

        # Create figure
        fig, ax = plt.subplots(figsize=config.figsize)

        # Compute binned aggregates
        self._compute_wavelength_aggregates()

        if len(self._binned_wave_centers) == 0:
            # No data available
            ax.text(0.5, 0.5, 'No data available',
                   ha='center', va='center', transform=ax.transAxes)
        else:
            # Plot mean curve
            ax.semilogx(
                self._binned_wave_centers,
                self._binned_wave_avg,
                'o-',
                color='#0173B2',
                linewidth=config.line_width,
                markersize=config.marker_size,
                label='Mean dispersion curve',
            )

            # Plot ±1σ envelope
            ax.fill_between(
                self._binned_wave_centers,
                self._binned_wave_avg - self._binned_wave_std,
                self._binned_wave_avg + self._binned_wave_std,
                alpha=config.uncertainty_alpha,
                color='#0173B2',
                label='±1σ uncertainty',
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
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

        return fig

    def generate_per_offset_wavelength_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        max_offsets: int = 10,
    ) -> Figure:
        """Generate per-offset dispersion curves in wavelength domain.

        Shows individual curves for each active offset/layer in wavelength domain.
        Useful for comparing multiple offsets or showing data diversity.

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)
            max_offsets: Maximum number of offsets to plot (default: 10)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        # Update xlabel for wavelength
        if config.xlabel == 'Frequency (Hz)':
            config.xlabel = 'Wavelength (m)'

        self._apply_style(config)

        # Create figure
        fig, ax = plt.subplots(figsize=config.figsize)

        # Get active layer indices
        active_indices = [i for i, flag in enumerate(self.active_flags) if flag][:max_offsets]

        if len(active_indices) == 0:
            ax.text(0.5, 0.5, 'No active layers',
                   ha='center', va='center', transform=ax.transAxes)
        else:
            # Get colors
            colors = self._get_colors(config, len(active_indices))

            # Plot each active offset
            for idx, layer_idx in enumerate(active_indices):
                wavelengths = self.wavelength_arrays[layer_idx]
                velocities = self.velocity_arrays[layer_idx]
                label = self.layer_labels[layer_idx]

                # Filter valid data
                mask = np.isfinite(wavelengths) & np.isfinite(velocities) & (wavelengths > 0)
                if np.any(mask):
                    ax.semilogx(
                        wavelengths[mask],
                        velocities[mask],
                        'o',
                        color=colors[idx],
                        markersize=config.marker_size,
                        alpha=0.7,
                        label=label,
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
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

        return fig

    def generate_dual_domain_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate side-by-side frequency and wavelength domain comparison.

        Creates a two-panel figure with frequency domain on the left and
        wavelength domain on the right. This is very common in MASW publications
        for comprehensive dispersion curve presentation.

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Create figure with two subplots
        fig, (ax_freq, ax_wave) = plt.subplots(1, 2, figsize=(config.figsize[0] * 1.8, config.figsize[1]))

        # Compute aggregates for both domains
        self._compute_binned_aggregates(config)
        self._compute_wavelength_aggregates()

        # LEFT PANEL: Frequency domain
        if len(self._bin_centers) > 0:
            ax_freq.semilogx(
                self._bin_centers,
                self._binned_avg,
                'o-',
                color='#0173B2',
                linewidth=config.line_width,
                markersize=config.marker_size,
                label='Mean curve',
            )
            ax_freq.fill_between(
                self._bin_centers,
                self._binned_avg - self._binned_std,
                self._binned_avg + self._binned_std,
                alpha=config.uncertainty_alpha,
                color='#0173B2',
                label='±1σ',
            )

        if config.show_grid:
            ax_freq.grid(True, alpha=config.grid_alpha, linestyle='--')
        ax_freq.set_xlabel('Frequency (Hz)')
        ax_freq.set_ylabel(config.ylabel)
        ax_freq.legend(loc='best')
        ax_freq.set_title('(a) Frequency Domain', fontsize=config.font_size)

        # RIGHT PANEL: Wavelength domain
        if len(self._binned_wave_centers) > 0:
            ax_wave.semilogx(
                self._binned_wave_centers,
                self._binned_wave_avg,
                'o-',
                color='#DE8F05',
                linewidth=config.line_width,
                markersize=config.marker_size,
                label='Mean curve',
            )
            ax_wave.fill_between(
                self._binned_wave_centers,
                self._binned_wave_avg - self._binned_wave_std,
                self._binned_wave_avg + self._binned_wave_std,
                alpha=config.uncertainty_alpha,
                color='#DE8F05',
                label='±1σ',
            )

        if config.show_grid:
            ax_wave.grid(True, alpha=config.grid_alpha, linestyle='--')
        ax_wave.set_xlabel('Wavelength (m)')
        ax_wave.set_ylabel(config.ylabel)
        ax_wave.legend(loc='best')
        ax_wave.set_title('(b) Wavelength Domain', fontsize=config.font_size)

        # Synchronize Y-axis limits
        if config.ylim:
            ax_freq.set_ylim(config.ylim)
            ax_wave.set_ylim(config.ylim)
        else:
            # Auto-sync Y limits
            ylim_freq = ax_freq.get_ylim()
            ylim_wave = ax_wave.get_ylim()
            ylim_combined = (min(ylim_freq[0], ylim_wave[0]), max(ylim_freq[1], ylim_wave[1]))
            ax_freq.set_ylim(ylim_combined)
            ax_wave.set_ylim(ylim_combined)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

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
            # Determine transparency based on format
            is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
            transparent = not is_raster
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

        return fig

    # =========================================================================
    # Canvas Export Methods (New)
    # =========================================================================

    def generate_canvas_frequency(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
    ) -> Figure:
        """Generate figure of current canvas view in frequency domain.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            xlim: Optional x-axis limits (uses current canvas limits if None)
            ylim: Optional y-axis limits (uses current canvas limits if None)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        colors = self._get_colors(config, len(self.velocity_arrays))

        # Plot each active layer
        for i, (freq, vel, label, active) in enumerate(zip(
            self.frequency_arrays, self.velocity_arrays,
            self.layer_labels, self.active_flags
        )):
            if active and len(freq) > 0:
                color = colors[i % len(colors)]
                ax.semilogx(
                    freq, vel,
                    marker=config.marker_style,
                    color=color,
                    markersize=config.marker_size,
                    linewidth=config.line_width,
                    label=label,
                )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Title
        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Limits
        if xlim:
            ax.set_xlim(xlim)
        elif config.xlim:
            ax.set_xlim(config.xlim)
        if ylim:
            ax.set_ylim(ylim)
        elif config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc=config.legend_position, ncol=config.legend_columns,
                  frameon=config.legend_frameon)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_canvas_wavelength(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
    ) -> Figure:
        """Generate figure of current canvas converted to wavelength domain.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            xlim: Optional x-axis limits (wavelength)
            ylim: Optional y-axis limits (velocity)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        colors = self._get_colors(config, len(self.velocity_arrays))

        # Plot each active layer in wavelength domain
        for i, (wl, vel, label, active) in enumerate(zip(
            self.wavelength_arrays, self.velocity_arrays,
            self.layer_labels, self.active_flags
        )):
            if active and len(wl) > 0:
                color = colors[i % len(colors)]
                ax.semilogx(
                    wl, vel,
                    marker=config.marker_style,
                    color=color,
                    markersize=config.marker_size,
                    linewidth=config.line_width,
                    label=label,
                )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels - override for wavelength domain
        ax.set_xlabel('Wavelength (m)')
        ax.set_ylabel(config.ylabel)

        # Title
        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Limits
        if xlim:
            ax.set_xlim(xlim)
        if ylim:
            ax.set_ylim(ylim)
        elif config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc=config.legend_position, ncol=config.legend_columns,
                  frameon=config.legend_frameon)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_canvas_dual(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate side-by-side frequency and wavelength views.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(
            1, 2,
            figsize=(config.figsize[0] * 2, config.figsize[1]),
            dpi=config.dpi
        )

        colors = self._get_colors(config, len(self.velocity_arrays))

        # Plot each active layer in both domains
        for i, (freq, wl, vel, label, active) in enumerate(zip(
            self.frequency_arrays, self.wavelength_arrays,
            self.velocity_arrays, self.layer_labels, self.active_flags
        )):
            if active and len(freq) > 0:
                color = colors[i % len(colors)]

                # Frequency domain (left)
                ax1.semilogx(
                    freq, vel,
                    marker=config.marker_style,
                    color=color,
                    markersize=config.marker_size,
                    linewidth=config.line_width,
                    label=label,
                )

                # Wavelength domain (right)
                ax2.semilogx(
                    wl, vel,
                    marker=config.marker_style,
                    color=color,
                    markersize=config.marker_size,
                    linewidth=config.line_width,
                    label=label,
                )

        # Configure axes
        for ax, xlabel in [(ax1, config.xlabel), (ax2, 'Wavelength (m)')]:
            if config.show_grid:
                ax.grid(True, alpha=config.grid_alpha, linestyle='--')
            ax.set_xlabel(xlabel)
            ax.set_ylabel(config.ylabel)
            if config.ylim:
                ax.set_ylim(config.ylim)

        # Add subplot titles
        ax1.set_title('Frequency Domain')
        ax2.set_title('Wavelength Domain')

        # Shared legend at bottom
        handles, labels = ax1.get_legend_handles_labels()
        fig.legend(handles, labels, loc='lower center',
                   ncol=min(len(labels), 4), frameon=config.legend_frameon,
                   bbox_to_anchor=(0.5, -0.02))

        # Main title
        if config.title:
            fig.suptitle(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Layout
        if config.tight_layout:
            fig.tight_layout()
            fig.subplots_adjust(bottom=0.15)  # Make room for legend

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    # =========================================================================
    # Source Offset Analysis Methods (New)
    # =========================================================================

    def generate_offset_curve_only(
        self,
        offset_index: int,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate dispersion curve for a single offset without spectrum.

        Args:
            offset_index: Index of the offset to plot
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        if offset_index < 0 or offset_index >= len(self.velocity_arrays):
            raise ValueError(f"Invalid offset_index {offset_index}. "
                           f"Must be 0-{len(self.velocity_arrays)-1}")

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        freq = self.frequency_arrays[offset_index]
        vel = self.velocity_arrays[offset_index]
        label = self.layer_labels[offset_index]

        colors = self._get_colors(config, 1)

        ax.semilogx(
            freq, vel,
            marker=config.marker_style,
            color=colors[0],
            markersize=config.marker_size,
            linewidth=config.line_width,
            label=label,
        )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Title
        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            ax.set_title(f'Dispersion Curve: {label}')

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        if config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc=config.legend_position, frameon=config.legend_frameon)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_with_spectrum(
        self,
        offset_index: int,
        spectrum_data: Optional[Dict[str, np.ndarray]] = None,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
    ) -> Figure:
        """Generate dispersion curve overlaid on spectrum background.

        Args:
            offset_index: Index of the offset to plot
            spectrum_data: Dictionary with 'frequencies', 'velocities', 'power' arrays
                          If None, will attempt to get from internal spectrum_data_list
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        if offset_index < 0 or offset_index >= len(self.velocity_arrays):
            raise ValueError(f"Invalid offset_index {offset_index}. "
                           f"Must be 0-{len(self.velocity_arrays)-1}")

        # Get spectrum data from internal list if not provided
        if spectrum_data is None:
            if self.spectrum_data_list and offset_index < len(self.spectrum_data_list):
                spectrum_data = self.spectrum_data_list[offset_index]
            if spectrum_data is None:
                raise ValueError("No spectrum data provided. Load spectrum .npz file first.")

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Extract spectrum data
        spec_freqs = spectrum_data.get('frequencies')
        spec_vels = spectrum_data.get('velocities')
        spec_power = spectrum_data.get('power')

        if spec_freqs is None or spec_vels is None or spec_power is None:
            raise ValueError("Spectrum data must contain 'frequencies', 'velocities', and 'power'")

        # Plot spectrum background
        if config.spectrum_render_mode == 'contour':
            cf = ax.contourf(
                spec_freqs, spec_vels, spec_power,
                levels=config.spectrum_levels,
                cmap=config.spectrum_colormap,
                alpha=config.spectrum_alpha
            )
            plt.colorbar(cf, ax=ax, label='Normalized Power')
        else:
            # imshow mode
            extent = [spec_freqs.min(), spec_freqs.max(),
                     spec_vels.min(), spec_vels.max()]
            im = ax.imshow(
                spec_power, aspect='auto', origin='lower',
                extent=extent,
                cmap=config.spectrum_colormap,
                alpha=config.spectrum_alpha
            )
            plt.colorbar(im, ax=ax, label='Normalized Power')

        # Overlay dispersion curve
        freq = self.frequency_arrays[offset_index]
        vel = self.velocity_arrays[offset_index]
        label = self.layer_labels[offset_index]

        # Plot with outline for visibility
        if config.peak_outline:
            ax.plot(
                freq, vel,
                color=config.peak_outline_color,
                linewidth=config.peak_line_width + 1,
                zorder=10,
            )

        ax.plot(
            freq, vel,
            color=config.peak_color,
            linewidth=config.peak_line_width,
            label=label,
            zorder=11,
        )

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--', color='white')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Title
        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            ax.set_title(f'Dispersion with Spectrum: {label}')

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        if config.ylim:
            ax.set_ylim(config.ylim)

        # Legend
        ax.legend(loc=config.legend_position, frameon=config.legend_frameon)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_spectrum_only(
        self,
        offset_index: Optional[int] = None,
        spectrum_data: Optional[Dict[str, np.ndarray]] = None,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        title: Optional[str] = None,
    ) -> Figure:
        """Generate spectrum visualization without dispersion curve.

        Args:
            offset_index: Index of the offset to get spectrum for (uses internal spectrum_data_list)
            spectrum_data: Dictionary with 'frequencies', 'velocities', 'power' arrays (overrides offset_index)
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            title: Optional title for the plot

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        # Get spectrum data from offset_index if not directly provided
        if spectrum_data is None:
            if offset_index is None:
                raise ValueError("Either offset_index or spectrum_data must be provided")
            if offset_index < 0 or offset_index >= len(self.spectrum_data_list):
                raise ValueError(f"Invalid offset_index {offset_index}")
            spectrum_data = self.spectrum_data_list[offset_index]
            if spectrum_data is None:
                raise ValueError(f"No spectrum data provided. Load spectrum .npz file first.")
            # Auto-generate title from layer label if not provided
            if title is None:
                title = f"Spectrum: {self.layer_labels[offset_index]}"

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Extract spectrum data
        spec_freqs = spectrum_data.get('frequencies')
        spec_vels = spectrum_data.get('velocities')
        spec_power = spectrum_data.get('power')

        if spec_freqs is None or spec_vels is None or spec_power is None:
            raise ValueError("Spectrum data must contain 'frequencies', 'velocities', and 'power'")

        # Plot spectrum
        if config.spectrum_render_mode == 'contour':
            cf = ax.contourf(
                spec_freqs, spec_vels, spec_power,
                levels=config.spectrum_levels,
                cmap=config.spectrum_colormap,
            )
            plt.colorbar(cf, ax=ax, label='Normalized Power')
        else:
            # imshow mode
            extent = [spec_freqs.min(), spec_freqs.max(),
                     spec_vels.min(), spec_vels.max()]
            im = ax.imshow(
                spec_power, aspect='auto', origin='lower',
                extent=extent,
                cmap=config.spectrum_colormap,
            )
            plt.colorbar(im, ax=ax, label='Normalized Power')

        # Grid
        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--', color='white')

        # Labels
        ax.set_xlabel(config.xlabel)
        ax.set_ylabel(config.ylabel)

        # Title
        if title:
            ax.set_title(title, fontsize=config.title_fontsize or config.font_size + 2)
        elif config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            ax.set_title('Frequency-Velocity Spectrum')

        # Limits
        if config.xlim:
            ax.set_xlim(config.xlim)
        if config.ylim:
            ax.set_ylim(config.ylim)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_grid(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
        include_spectrum: bool = False,
        spectrum_data_list: Optional[List[Dict[str, np.ndarray]]] = None,
        include_curves: bool = True,
    ) -> Figure:
        """Generate comparison grid of all offsets.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            rows: Number of rows (auto if None)
            cols: Number of columns (auto if None)
            include_spectrum: Whether to include spectrum background
            spectrum_data_list: List of spectrum data dicts for each offset
            include_curves: Whether to include dispersion curves (default True)

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()
        
        # Use internal spectrum data if not provided
        if include_spectrum and spectrum_data_list is None:
            spectrum_data_list = self.spectrum_data_list

        # Count active offsets
        active_indices = [i for i, active in enumerate(self.active_flags) if active]
        n_offsets = len(active_indices)

        if n_offsets == 0:
            # Create empty figure with message
            fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)
            ax.text(0.5, 0.5, 'No active offsets', ha='center', va='center',
                   transform=ax.transAxes, fontsize=14)
            ax.axis('off')
            return fig

        # Compute grid layout
        if rows is None or cols is None or rows == 0 or cols == 0:
            cols = int(np.ceil(np.sqrt(n_offsets)))
            rows = int(np.ceil(n_offsets / cols))

        self._apply_style(config)

        # Create figure
        fig, axes = plt.subplots(
            rows, cols,
            figsize=(config.figsize[0] * cols * 0.6, config.figsize[1] * rows * 0.6),
            dpi=config.dpi,
            squeeze=False
        )

        colors = self._get_colors(config, n_offsets)

        # Track global axis limits for consistency
        all_freqs = []
        all_vels = []
        for i in active_indices:
            if len(self.frequency_arrays[i]) > 0:
                all_freqs.extend(self.frequency_arrays[i])
                all_vels.extend(self.velocity_arrays[i])

        # Plot each offset
        plot_idx = 0
        for r in range(rows):
            for c in range(cols):
                ax = axes[r, c]

                if plot_idx < n_offsets:
                    offset_idx = active_indices[plot_idx]
                    freq = self.frequency_arrays[offset_idx]
                    vel = self.velocity_arrays[offset_idx]
                    label = self.layer_labels[offset_idx]

                    # Plot spectrum if requested
                    if include_spectrum and spectrum_data_list and offset_idx < len(spectrum_data_list):
                        spec_data = spectrum_data_list[offset_idx]
                        if spec_data:
                            spec_freqs = spec_data.get('frequencies')
                            spec_vels = spec_data.get('velocities')
                            spec_power = spec_data.get('power')

                            if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                                ax.contourf(
                                    spec_freqs, spec_vels, spec_power,
                                    levels=config.spectrum_levels,
                                    cmap=config.spectrum_colormap,
                                    alpha=config.spectrum_alpha * 0.7
                                )

                    # Plot dispersion curve if requested
                    if include_curves and len(freq) > 0:
                        ax.semilogx(
                            freq, vel,
                            marker=config.marker_style,
                            color=colors[plot_idx % len(colors)] if not include_spectrum else config.peak_color,
                            markersize=max(2, config.marker_size * 0.7),
                            linewidth=config.line_width * 0.8,
                        )

                    ax.set_title(label, fontsize=config.font_size - 1)

                    if config.show_grid:
                        ax.grid(True, alpha=config.grid_alpha * 0.5, linestyle='--')

                    # Only show labels on edge plots
                    if r == rows - 1:
                        ax.set_xlabel('Freq (Hz)', fontsize=config.font_size - 2)
                    if c == 0:
                        ax.set_ylabel('V (m/s)', fontsize=config.font_size - 2)

                    plot_idx += 1
                else:
                    # Hide unused subplots
                    ax.axis('off')

        # Main title
        if config.title:
            fig.suptitle(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def _save_figure(self, fig: Figure, output_path: str, config: PlotConfig):
        """Helper method to save figure with proper settings."""
        is_raster = config.output_format.lower() in ['png', 'jpg', 'jpeg']
        transparent = not is_raster
        fig.savefig(
            output_path,
            dpi=config.dpi,
            bbox_inches='tight',
            facecolor='white' if is_raster else 'none',
            transparent=transparent
        )