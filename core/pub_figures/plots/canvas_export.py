"""Canvas export plot methods."""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import PlotConfig


class CanvasExportMixin:
    """Mixin for canvas export plots."""

    def generate_canvas_frequency(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
        include_spectrum: bool = True,
    ) -> Figure:
        """Generate figure of current canvas view in frequency domain.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            xlim: Optional x-axis limits (uses current canvas limits if None)
            ylim: Optional y-axis limits (uses current canvas limits if None)
            include_spectrum: Whether to include visible spectrum backgrounds

        Returns:
            matplotlib Figure object
        """
        if config is None:
            config = PlotConfig()

        self._apply_style(config)
        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        colors = self._get_colors(config, len(self.velocity_arrays))

        # Track last contourf for colorbar
        last_contourf = None
        spectrum_rendered = False

        # Render visible spectrum backgrounds first (so curves are on top)
        if include_spectrum:
            for i, (active, spec_visible) in enumerate(zip(self.active_flags, self.spectrum_visible_flags)):
                if active and spec_visible and i < len(self.spectrum_data_list):
                    spec_data = self.spectrum_data_list[i]
                    if spec_data is not None:
                        spec_freqs = spec_data.get('frequencies')
                        spec_vels = spec_data.get('velocities')
                        spec_power = spec_data.get('power')
                        if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                            # Use reduced alpha for overlapping spectra
                            alpha = config.spectrum_alpha * 0.6
                            last_contourf = ax.contourf(
                                spec_freqs, spec_vels, spec_power,
                                levels=config.spectrum_levels,
                                cmap=config.spectrum_colormap,
                                alpha=alpha,
                                zorder=1,
                            )
                            spectrum_rendered = True

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
                    zorder=10,
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

        # Compute smart axis limits from curve data (not spectrum)
        all_freqs = []
        all_vels = []
        for i, (freq, vel, active) in enumerate(zip(
            self.frequency_arrays, self.velocity_arrays, self.active_flags
        )):
            if active and len(freq) > 0:
                all_freqs.extend(freq)
                all_vels.extend(vel)
        
        # Apply limits: explicit > config > smart auto
        if xlim:
            ax.set_xlim(xlim)
        elif config.xlim:
            ax.set_xlim(config.xlim)
        elif len(all_freqs) > 0:
            # Smart auto limits based on curve data
            freq_min = float(np.nanmin(all_freqs))
            freq_max = float(np.nanmax(all_freqs))
            ax.set_xlim(max(0.0, freq_min - 1.0), freq_max + 5.0)
            
        if ylim:
            ax.set_ylim(ylim)
        elif config.ylim:
            ax.set_ylim(config.ylim)
        elif len(all_vels) > 0:
            # Smart auto limits based on curve data
            vel_min = float(np.nanmin(all_vels))
            vel_max = float(np.nanmax(all_vels))
            ax.set_ylim(max(0.0, vel_min - 100), vel_max + 100)

        # Legend with outside position support
        self._apply_legend(ax, fig, config)

        # Add colorbar if spectrum was rendered and colorbar enabled
        if spectrum_rendered and last_contourf is not None:
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax, last_contourf, config)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)


    def generate_canvas_wavelength(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
        include_spectrum: bool = False,
    ) -> Figure:
        """Generate figure of current canvas converted to wavelength domain.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            xlim: Optional x-axis limits (wavelength)
            ylim: Optional y-axis limits (velocity)
            include_spectrum: Whether to include visible spectrum (not typically used for wavelength domain)

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
                    zorder=10,
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

        # Compute smart axis limits from curve data
        all_wls = []
        all_vels = []
        for i, (wl, vel, active) in enumerate(zip(
            self.wavelength_arrays, self.velocity_arrays, self.active_flags
        )):
            if active and len(wl) > 0:
                all_wls.extend(wl)
                all_vels.extend(vel)
        
        # Apply limits: explicit > config > smart auto
        if xlim:
            ax.set_xlim(xlim)
        elif config.xlim:
            ax.set_xlim(config.xlim)
        elif len(all_wls) > 0:
            # Smart auto limits for wavelength domain
            wl_min = float(np.nanmin(all_wls))
            wl_max = float(np.nanmax(all_wls))
            ax.set_xlim(max(0.1, wl_min * 0.8), wl_max * 1.2)
            
        if ylim:
            ax.set_ylim(ylim)
        elif config.ylim:
            ax.set_ylim(config.ylim)
        elif len(all_vels) > 0:
            # Smart auto limits based on curve data
            vel_min = float(np.nanmin(all_vels))
            vel_max = float(np.nanmax(all_vels))
            ax.set_ylim(max(0.0, vel_min - 100), vel_max + 100)

        # Legend with outside position support
        self._apply_legend(ax, fig, config)

        # Layout
        if config.tight_layout:
            fig.tight_layout()

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)


    def generate_canvas_dual(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        include_spectrum: bool = True,
    ) -> Figure:
        """Generate side-by-side frequency and wavelength views.

        Args:
            output_path: Optional path to save figure
            config: PlotConfig instance (uses defaults if None)
            include_spectrum: Whether to include visible spectrum backgrounds (frequency domain only)

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

        # Track spectrum for colorbar
        last_contourf = None
        spectrum_rendered = False

        # Render visible spectrum backgrounds on frequency domain (left plot) first
        if include_spectrum:
            for i, (active, spec_visible) in enumerate(zip(self.active_flags, self.spectrum_visible_flags)):
                if active and spec_visible and i < len(self.spectrum_data_list):
                    spec_data = self.spectrum_data_list[i]
                    if spec_data is not None:
                        spec_freqs = spec_data.get('frequencies')
                        spec_vels = spec_data.get('velocities')
                        spec_power = spec_data.get('power')
                        if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                            alpha = config.spectrum_alpha * 0.6
                            last_contourf = ax1.contourf(
                                spec_freqs, spec_vels, spec_power,
                                levels=config.spectrum_levels,
                                cmap=config.spectrum_colormap,
                                alpha=alpha,
                                zorder=1,
                            )
                            spectrum_rendered = True

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
                    zorder=10,
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

        # Compute smart axis limits from curve data
        all_freqs = []
        all_wls = []
        all_vels = []
        for i, (freq, wl, vel, active) in enumerate(zip(
            self.frequency_arrays, self.wavelength_arrays,
            self.velocity_arrays, self.active_flags
        )):
            if active and len(freq) > 0:
                all_freqs.extend(freq)
                all_wls.extend(wl)
                all_vels.extend(vel)
        
        # Apply smart limits for frequency domain (ax1)
        if config.xlim:
            ax1.set_xlim(config.xlim)
        elif len(all_freqs) > 0:
            freq_min = float(np.nanmin(all_freqs))
            freq_max = float(np.nanmax(all_freqs))
            ax1.set_xlim(max(0.0, freq_min - 1.0), freq_max + 5.0)
            
        # Apply smart limits for wavelength domain (ax2)
        if len(all_wls) > 0:
            wl_min = float(np.nanmin(all_wls))
            wl_max = float(np.nanmax(all_wls))
            ax2.set_xlim(max(0.1, wl_min * 0.8), wl_max * 1.2)
            
        # Apply velocity limits to both axes
        if config.ylim:
            ax1.set_ylim(config.ylim)
            ax2.set_ylim(config.ylim)
        elif len(all_vels) > 0:
            vel_min = float(np.nanmin(all_vels))
            vel_max = float(np.nanmax(all_vels))
            smart_ylim = (max(0.0, vel_min - 100), vel_max + 100)
            ax1.set_ylim(smart_ylim)
            ax2.set_ylim(smart_ylim)

        # Add subplot titles
        ax1.set_title('Frequency Domain')
        ax2.set_title('Wavelength Domain')

        # Shared legend at bottom with dynamic layout
        handles, labels = ax1.get_legend_handles_labels()
        n_labels = len(labels)
        
        # Dynamic column count: more columns for more items, but cap at reasonable max
        if n_labels <= 4:
            ncol = n_labels
        elif n_labels <= 8:
            ncol = 4
        else:
            ncol = min(6, (n_labels + 1) // 2)  # 2 rows max for many items
        
        # Compute legend rows for margin adjustment
        n_legend_rows = (n_labels + ncol - 1) // ncol if ncol > 0 else 1
        
        # Position legend inside figure at bottom
        fig.legend(handles, labels, loc='upper center',
                   ncol=ncol, frameon=config.legend_frameon,
                   bbox_to_anchor=(0.5, 0.02))

        # Main title
        if config.title:
            fig.suptitle(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Add colorbar to frequency domain if spectrum was rendered
        if spectrum_rendered and last_contourf is not None:
            if config.show_spectrum_colorbar and config.spectrum_colorbar_orientation != 'none':
                self._add_colorbar(fig, ax1, last_contourf, config)

        # Layout with dynamic bottom margin based on legend rows
        if config.tight_layout:
            fig.tight_layout()
            bottom_margin = 0.08 + 0.04 * n_legend_rows
            fig.subplots_adjust(bottom=bottom_margin)

        # Save if path provided
        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    # =========================================================================
    # Source Offset Analysis Methods (New)

