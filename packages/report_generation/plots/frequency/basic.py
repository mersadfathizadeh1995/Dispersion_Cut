"""Basic frequency domain plot methods."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...config import PlotConfig

from ...utils import ensure_parent_dir_for_file


class BasicFrequencyPlotsMixin:
    """Mixin for basic frequency domain plots."""

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
            ensure_parent_dir_for_file(output_path)
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
            ensure_parent_dir_for_file(output_path)
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
            ensure_parent_dir_for_file(output_path)
            fig.savefig(
                output_path,
                dpi=config.dpi,
                bbox_inches='tight',
                facecolor='white' if is_raster else 'none',
                transparent=transparent
            )

        return fig
