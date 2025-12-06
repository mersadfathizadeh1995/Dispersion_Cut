"""Basic wavelength domain plot methods."""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import PlotConfig


class BasicWavelengthPlotsMixin:
    """Mixin for basic wavelength domain plots."""

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


