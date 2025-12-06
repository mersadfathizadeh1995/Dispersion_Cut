"""Offset analysis plot methods."""
from matplotlib.figure import Figure

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import PlotConfig

class OffsetAnalysisMixin:
    """Mixin for offset analysis plots."""

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

        # Legend with outside position support
        self._apply_legend(ax, fig, config)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_with_spectrum(




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
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax, cf, config)
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
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax, im, config)

        # Overlay dispersion curve based on curve_overlay_style
        freq = self.frequency_arrays[offset_index]
        vel = self.velocity_arrays[offset_index]
        label = self.layer_labels[offset_index]

        # Determine overlay style
        overlay_style = config.curve_overlay_style

        # Plot with outline for visibility (only for line or line+markers styles)
        if config.peak_outline and overlay_style in ('line', 'line+markers'):
            if overlay_style == 'line+markers':
                ax.plot(
                    freq, vel,
                    color=config.peak_outline_color,
                    linewidth=config.peak_line_width + 1,
                    marker=config.marker_style,
                    markersize=config.marker_size + 2,
                    zorder=10,
                )
            else:
                ax.plot(
                    freq, vel,
                    color=config.peak_outline_color,
                    linewidth=config.peak_line_width + 1,
                    zorder=10,
                )

        # Main curve/markers
        if overlay_style == 'line':
            ax.plot(
                freq, vel,
                color=config.peak_color,
                linewidth=config.peak_line_width,
                label=label,
                zorder=11,
            )
        elif overlay_style == 'markers':
            # Outline for markers
            if config.peak_outline:
                ax.scatter(
                    freq, vel,
                    c=config.peak_outline_color,
                    s=(config.marker_size + 2)**2,
                    marker=config.marker_style,
                    zorder=10,
                )
            ax.scatter(
                freq, vel,
                c=config.peak_color,
                s=config.marker_size**2,
                marker=config.marker_style,
                label=label,
                zorder=11,
            )
        else:  # line+markers
            ax.plot(
                freq, vel,
                color=config.peak_color,
                linewidth=config.peak_line_width,
                marker=config.marker_style,
                markersize=config.marker_size,
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

        # Compute smart axis limits
        xlim, ylim = self._compute_smart_axis_limits(freq, vel, config)
        if xlim:
            ax.set_xlim(xlim)
        if ylim:
            ax.set_ylim(ylim)

        # Legend with outside position support
        self._apply_legend(ax, fig, config)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_spectrum_only(




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
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax, cf, config)
        else:
            # imshow mode
            extent = [spec_freqs.min(), spec_freqs.max(),
                     spec_vels.min(), spec_vels.max()]
            im = ax.imshow(
                spec_power, aspect='auto', origin='lower',
                extent=extent,
                cmap=config.spectrum_colormap,
            )
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax, im, config)

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

        # Compute smart axis limits (use spectrum bounds if dispersion curve not available)
        if offset_index is not None and len(self.frequency_arrays[offset_index]) > 0:
            # Use dispersion curve data for limits
            freq = self.frequency_arrays[offset_index]
            vel = self.velocity_arrays[offset_index]
            xlim, ylim = self._compute_smart_axis_limits(freq, vel, config)
        else:
            # Fallback to config limits or spectrum bounds
            xlim = config.xlim
            ylim = config.ylim

        if xlim:
            ax.set_xlim(xlim)
        if ylim:
            ax.set_ylim(ylim)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_offset_grid(




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
        """Generate comparison grid of selected offsets.

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

        # Use config.grid_offset_indices if specified, otherwise use all active offsets
        if config.grid_offset_indices:
            # Filter to only include indices that are also active
            active_set = set(i for i, active in enumerate(self.active_flags) if active)
            active_indices = [i for i in config.grid_offset_indices if i in active_set]
        else:
            # Default: all active offsets
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

        # Determine figure size accounting for shared colorbar
        base_width = config.figsize[0] * cols * 0.6
        base_height = config.figsize[1] * rows * 0.6
        
        # Add extra space for colorbar if enabled
        if include_spectrum and config.grid_shared_colorbar == 'vertical':
            base_width += 0.8  # Extra width for vertical colorbar
        elif include_spectrum and config.grid_shared_colorbar == 'horizontal':
            base_height += 0.6  # Extra height for horizontal colorbar

        # Create figure
        fig, axes = plt.subplots(
            rows, cols,
            figsize=(base_width, base_height),
            dpi=config.dpi,
            squeeze=False
        )

        colors = self._get_colors(config, n_offsets)

        # Compute smart consistent axis limits for the grid
        grid_xlim, grid_ylim = self._compute_grid_smart_limits(config, active_indices)

        # Track contourf mappable for shared colorbar
        last_contourf = None

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
                                contourf_result = ax.contourf(
                                    spec_freqs, spec_vels, spec_power,
                                    levels=config.spectrum_levels,
                                    cmap=config.spectrum_colormap,
                                    alpha=config.spectrum_alpha * 0.7
                                )
                                last_contourf = contourf_result

                    # Plot dispersion curve if requested
                    if include_curves and len(freq) > 0:
                        curve_color = config.peak_color if include_spectrum else colors[plot_idx % len(colors)]
                        overlay_style = config.curve_overlay_style

                        # Outline for visibility on spectrum
                        if include_spectrum and config.peak_outline and overlay_style in ('line', 'line+markers'):
                            if overlay_style == 'line+markers':
                                ax.plot(
                                    freq, vel,
                                    color=config.peak_outline_color,
                                    linewidth=config.peak_line_width * 0.8 + 1,
                                    marker=config.marker_style,
                                    markersize=max(2, config.marker_size * 0.7) + 1,
                                    zorder=10,
                                )
                            else:
                                ax.plot(
                                    freq, vel,
                                    color=config.peak_outline_color,
                                    linewidth=config.peak_line_width * 0.8 + 1,
                                    zorder=10,
                                )

                        # Main curve/markers based on overlay style
                        if overlay_style == 'line':
                            ax.plot(
                                freq, vel,
                                color=curve_color,
                                linewidth=config.line_width * 0.8,
                                zorder=11,
                            )
                        elif overlay_style == 'markers':
                            if include_spectrum and config.peak_outline:
                                ax.scatter(
                                    freq, vel,
                                    c=config.peak_outline_color,
                                    s=(max(2, config.marker_size * 0.7) + 1)**2,
                                    marker=config.marker_style,
                                    zorder=10,
                                )
                            ax.scatter(
                                freq, vel,
                                c=curve_color,
                                s=max(2, config.marker_size * 0.7)**2,
                                marker=config.marker_style,
                                zorder=11,
                            )
                        else:  # line+markers
                            ax.plot(
                                freq, vel,
                                color=curve_color,
                                marker=config.marker_style,
                                markersize=max(2, config.marker_size * 0.7),
                                linewidth=config.line_width * 0.8,
                                zorder=11,
                            )

                    ax.set_title(label, fontsize=config.font_size - 1)

                    if config.show_grid:
                        ax.grid(True, alpha=config.grid_alpha * 0.5, linestyle='--')

                    # Apply consistent axis limits
                    if grid_xlim:
                        ax.set_xlim(grid_xlim)
                    if grid_ylim:
                        ax.set_ylim(grid_ylim)

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

        # Add shared colorbar if enabled and spectrum is shown
        if include_spectrum and last_contourf is not None and config.show_spectrum_colorbar:
            if config.spectrum_colorbar_orientation == 'horizontal':
                # Horizontal colorbar at bottom
                fig.subplots_adjust(bottom=0.12)
                cbar_ax = fig.add_axes([0.15, 0.04, 0.7, 0.02])
                cbar = fig.colorbar(last_contourf, cax=cbar_ax, orientation='horizontal')
                cbar.set_label('Power', fontsize=config.font_size - 2)
            elif config.spectrum_colorbar_orientation == 'vertical':
                # Vertical colorbar on right
                fig.subplots_adjust(right=0.88)
                cbar_ax = fig.add_axes([0.91, 0.15, 0.02, 0.7])
                cbar = fig.colorbar(last_contourf, cax=cbar_ax, orientation='vertical')
                cbar.set_label('Power', fontsize=config.font_size - 2)
            # 'none' = no colorbar

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def _save_figure(self, fig: Figure, output_path: str, config: PlotConfig):




