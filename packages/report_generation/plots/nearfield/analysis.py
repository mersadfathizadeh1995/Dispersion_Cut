"""Near-field analysis plot mixins for publication figures."""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ...config import PlotConfig


class NearFieldAnalysisMixin:
    """Mixin providing near-field NACD analysis visualization methods.
    
    Creates dispersion curve figures with points colored by NACD status:
    - Blue (far-field): NACD >= threshold (good data)
    - Red (near-field): NACD < threshold (contaminated data)
    """

    def generate_nacd_curve(
        self,
        output_path: Optional[str] = None,
        config: Optional['PlotConfig'] = None,
        offset_index: Optional[int] = None,
    ) -> Figure:
        """Generate single dispersion curve with NACD-based coloring.

        Points are colored based on NACD threshold:
        - Blue (or config color): NACD >= threshold (far-field, good data)
        - Red (or config color): NACD < threshold (near-field, contaminated)

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)
            offset_index: Index of offset to plot (uses first active if None)

        Returns:
            matplotlib Figure object
        """
        from ...config import PlotConfig
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Get colors from config
        far_field_color = getattr(config, 'nf_farfield_color', 'blue')
        near_field_color = getattr(config, 'nf_nearfield_color', 'red')

        # Determine which offset to plot
        if offset_index is not None:
            layer_idx = offset_index
        else:
            # Use first active offset
            active_indices = [i for i, active in enumerate(self.active_flags) if active]
            if not active_indices:
                fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)
                ax.text(0.5, 0.5, 'No active offsets', ha='center', va='center', transform=ax.transAxes)
                return fig
            layer_idx = active_indices[0]

        freqs = self.frequency_arrays[layer_idx]
        vels = self.velocity_arrays[layer_idx]
        label = self.layer_labels[layer_idx]

        if len(freqs) == 0:
            fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)
            ax.text(0.5, 0.5, f'{label}\n(no data)', ha='center', va='center', transform=ax.transAxes)
            return fig

        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Check if spectrum background should be shown
        show_spectrum = getattr(config, 'nf_show_spectrum', False)

        # Plot spectrum background if enabled
        if show_spectrum and hasattr(self, 'spectrum_data_list') and self.spectrum_data_list:
            if layer_idx < len(self.spectrum_data_list) and self.spectrum_data_list[layer_idx] is not None:
                spectrum_data = self.spectrum_data_list[layer_idx]
                try:
                    spec_freqs = spectrum_data.get('frequencies', spectrum_data.get('freq'))
                    spec_vels = spectrum_data.get('velocities', spectrum_data.get('vel'))
                    spec_power = spectrum_data.get('power', spectrum_data.get('spectrum'))
                    
                    if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                        ax.contourf(
                            spec_freqs, spec_vels, spec_power,
                            levels=config.spectrum_levels,
                            cmap=config.spectrum_colormap,
                            alpha=config.spectrum_alpha * 0.8
                        )
                        ax.set_xscale('log')
                        # Adjust colors for visibility on spectrum
                        far_field_color = '#00FFFF' if far_field_color == 'blue' else far_field_color
                        near_field_color = '#FF6600' if near_field_color == 'red' else near_field_color
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to plot spectrum for layer {layer_idx}: {e}")
            else:
                import logging
                logging.info(f"NACD curve: No spectrum data for layer {layer_idx} (spectrum_data_list has {len(self.spectrum_data_list)} items, item is None: {self.spectrum_data_list[layer_idx] is None if layer_idx < len(self.spectrum_data_list) else 'index out of range'})")

        # Compute NACD for this offset
        nacd_values = self._compute_nacd_for_offset(layer_idx, config)

        if nacd_values is not None:
            near_field_mask = nacd_values < config.nacd_threshold
            far_field_mask = ~near_field_mask
        else:
            # If NACD computation fails, show all as far-field
            near_field_mask = np.zeros(len(freqs), dtype=bool)
            far_field_mask = np.ones(len(freqs), dtype=bool)

        # Plot far-field points (blue) - plot first so they appear in legend with label
        if np.any(far_field_mask):
            ax.semilogx(
                freqs[far_field_mask],
                vels[far_field_mask],
                marker='o',
                linestyle='',
                markerfacecolor='none',
                markeredgecolor=far_field_color,
                markeredgewidth=1.5,
                markersize=config.marker_size + 2,
                label=label,
            )

        # Plot near-field points (red) - no label to avoid duplicate legend
        if np.any(near_field_mask):
            ax.semilogx(
                freqs[near_field_mask],
                vels[near_field_mask],
                marker='o',
                linestyle='',
                markerfacecolor='none',
                markeredgecolor=near_field_color,
                markeredgewidth=1.5,
                markersize=config.marker_size + 2,
            )

        # Configure axes
        ax.set_xlabel(config.xlabel, fontsize=config.font_size)
        ax.set_ylabel(config.ylabel, fontsize=config.font_size)

        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        # Add legend
        ax.legend(loc='upper right', fontsize=config.font_size)

        if config.show_grid and not show_spectrum:
            ax.grid(True, alpha=config.grid_alpha, linestyle='-', which='both')

        # Set limits - use auto limits based on curve data when spectrum is shown
        if config.xlim:
            ax.set_xlim(config.xlim)
        elif show_spectrum and len(freqs) > 0:
            # Auto limit based on curve data with padding
            freq_min, freq_max = np.min(freqs), np.max(freqs)
            freq_pad = 0.1 * (freq_max - freq_min) if freq_max > freq_min else 1.0
            ax.set_xlim(max(freq_min - freq_pad, freq_min * 0.8), freq_max + freq_pad)
        
        if config.ylim:
            ax.set_ylim(config.ylim)
        elif show_spectrum and len(vels) > 0:
            # Auto limit based on curve data with padding
            vel_min, vel_max = np.min(vels), np.max(vels)
            vel_pad = 0.1 * (vel_max - vel_min) if vel_max > vel_min else 50.0
            ax.set_ylim(max(0, vel_min - vel_pad), vel_max + vel_pad)

        if config.tight_layout:
            fig.tight_layout()

        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_nacd_grid(
        self,
        output_path: Optional[str] = None,
        config: Optional['PlotConfig'] = None,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
    ) -> Figure:
        """Generate multi-panel grid showing NACD-colored curves for each offset.

        Each panel shows a dispersion curve with points colored by NACD:
        - Blue (or config color): far-field (NACD >= threshold)
        - Red (or config color): near-field (NACD < threshold)

        Supports display modes from config.nf_grid_display_mode:
        - 'curves': Show only dispersion curves with NACD coloring
        - 'spectrum': Show spectrum background with NACD-colored curve overlay
        - 'both': Show both spectrum and colored curves

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)
            rows: Number of rows in grid (auto if None or 0)
            cols: Number of columns in grid (auto if None or 0)

        Returns:
            matplotlib Figure object
        """
        from ...config import PlotConfig
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Get colors from config
        far_field_color = getattr(config, 'nf_farfield_color', 'blue')
        near_field_color = getattr(config, 'nf_nearfield_color', 'red')
        show_spectrum = getattr(config, 'nf_show_spectrum', False)

        # Get active indices based on config.nf_grid_offset_indices or all active offsets
        active_set = set(i for i, active in enumerate(self.active_flags) if active)

        nf_offset_indices = getattr(config, 'nf_grid_offset_indices', None)
        if nf_offset_indices:
            active_indices = [i for i in nf_offset_indices if i in active_set]
        else:
            active_indices = sorted(list(active_set))

        n_offsets = len(active_indices)

        if n_offsets == 0:
            fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)
            ax.text(0.5, 0.5, 'No active offsets', ha='center', va='center', transform=ax.transAxes)
            return fig

        # Determine grid layout
        if rows is None or cols is None or rows == 0 or cols == 0:
            cols = int(np.ceil(np.sqrt(n_offsets)))
            rows = int(np.ceil(n_offsets / cols))

        # Figure size
        base_width = config.figsize[0] * cols * 0.55
        base_height = config.figsize[1] * rows * 0.55

        fig, axes = plt.subplots(
            rows, cols,
            figsize=(base_width, base_height),
            dpi=config.dpi,
            squeeze=False
        )

        # Plot each offset
        plot_idx = 0
        for r in range(rows):
            for c in range(cols):
                ax = axes[r, c]

                if plot_idx >= n_offsets:
                    ax.axis('off')
                    plot_idx += 1
                    continue

                layer_idx = active_indices[plot_idx]
                freqs = self.frequency_arrays[layer_idx]
                vels = self.velocity_arrays[layer_idx]
                label = self.layer_labels[layer_idx]

                if len(freqs) == 0:
                    ax.text(0.5, 0.5, f'{label}\n(no data)', ha='center', va='center',
                            transform=ax.transAxes, fontsize=config.font_size - 2)
                    ax.axis('off')
                    plot_idx += 1
                    continue

                # Get spectrum data if available and show_spectrum is enabled
                spectrum_data = None
                if show_spectrum:
                    if hasattr(self, 'spectrum_data_list') and self.spectrum_data_list:
                        if layer_idx < len(self.spectrum_data_list):
                            spectrum_data = self.spectrum_data_list[layer_idx]
                    if spectrum_data is None:
                        import logging
                        logging.info(f"NACD grid: No spectrum data for layer {layer_idx}")

                # Plot spectrum background if enabled
                if spectrum_data is not None and show_spectrum:
                    try:
                        spec_freqs = spectrum_data.get('frequencies', spectrum_data.get('freq'))
                        spec_vels = spectrum_data.get('velocities', spectrum_data.get('vel'))
                        spec_power = spectrum_data.get('power', spectrum_data.get('spectrum'))
                        
                        if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                            # Use contourf for spectrum
                            ax.contourf(
                                spec_freqs, spec_vels, spec_power,
                                levels=config.spectrum_levels,
                                cmap=config.spectrum_colormap,
                                alpha=config.spectrum_alpha * 0.7
                            )
                            ax.set_xscale('log')
                    except Exception as e:
                        import logging
                        logging.warning(f"Failed to plot spectrum for layer {layer_idx}: {e}")

                # Compute NACD for this offset
                nacd_values = self._compute_nacd_for_offset(layer_idx, config)

                if nacd_values is not None:
                    near_field_mask = nacd_values < config.nacd_threshold
                    far_field_mask = ~near_field_mask
                else:
                    near_field_mask = np.zeros(len(freqs), dtype=bool)
                    far_field_mask = np.ones(len(freqs), dtype=bool)

                # Adjust colors if on spectrum background
                if spectrum_data is not None and show_spectrum:
                    # Use brighter colors for visibility on spectrum
                    ff_color = '#00FFFF' if far_field_color == 'blue' else far_field_color
                    nf_color = '#FF6600' if near_field_color == 'red' else near_field_color
                else:
                    ff_color = far_field_color
                    nf_color = near_field_color

                # Plot far-field points
                if np.any(far_field_mask):
                    ax.semilogx(
                        freqs[far_field_mask],
                        vels[far_field_mask],
                        marker='o',
                        linestyle='',
                        markerfacecolor='none',
                        markeredgecolor=ff_color,
                        markeredgewidth=1.0,
                        markersize=max(3, config.marker_size * 0.6),
                    )

                # Plot near-field points
                if np.any(near_field_mask):
                    ax.semilogx(
                        freqs[near_field_mask],
                        vels[near_field_mask],
                        marker='o',
                        linestyle='',
                        markerfacecolor='none',
                        markeredgecolor=nf_color,
                        markeredgewidth=1.0,
                        markersize=max(3, config.marker_size * 0.6),
                    )

                # Set axis limits based on curve data when spectrum is shown
                if show_spectrum and len(freqs) > 0:
                    # Auto limit based on curve data with padding
                    freq_min, freq_max = np.min(freqs), np.max(freqs)
                    freq_pad = 0.1 * (freq_max - freq_min) if freq_max > freq_min else 1.0
                    ax.set_xlim(max(freq_min - freq_pad, freq_min * 0.8), freq_max + freq_pad)
                    
                    vel_min, vel_max = np.min(vels), np.max(vels)
                    vel_pad = 0.1 * (vel_max - vel_min) if vel_max > vel_min else 50.0
                    ax.set_ylim(max(0, vel_min - vel_pad), vel_max + vel_pad)

                # Calculate near-field percentage for title
                nf_pct = 100 * np.sum(near_field_mask) / len(freqs) if len(freqs) > 0 else 0

                ax.set_title(f'{label}\n(NF: {nf_pct:.1f}%)', fontsize=config.font_size - 1)

                if config.show_grid and not show_spectrum:
                    ax.grid(True, alpha=config.grid_alpha * 0.5, linestyle='-', which='both')

                # Only add axis labels for edge panels
                if r == rows - 1:
                    ax.set_xlabel('Freq (Hz)', fontsize=config.font_size - 2)
                if c == 0:
                    ax.set_ylabel('V (m/s)', fontsize=config.font_size - 2)

                plot_idx += 1

        # Suptitle
        if config.title:
            fig.suptitle(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            fig.suptitle(f'Near-Field Analysis (NACD threshold = {config.nacd_threshold})',
                        fontsize=config.title_fontsize or config.font_size + 2)

        if config.tight_layout:
            fig.tight_layout()

        if output_path:
            self._save_figure(fig, output_path, config)

        return fig


    def generate_nacd_combined(
        self,
        output_path: Optional[str] = None,
        config: Optional['PlotConfig'] = None,
    ) -> Figure:
        """Generate combined overlay plot with all curves and NACD marking.

        All dispersion curves are shown overlaid on a single plot:
        - Far-field points use original curve colors (from color palette)
        - Near-field points from ALL offsets are shown in red

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)

        Returns:
            matplotlib Figure object
        """
        from ...config import PlotConfig
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        # Get near-field color from config
        near_field_color = getattr(config, 'nf_nearfield_color', 'red')
        show_spectrum = getattr(config, 'nf_show_spectrum', False)

        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Get active indices
        nf_offset_indices = getattr(config, 'nf_grid_offset_indices', None)
        if nf_offset_indices:
            active_indices = [i for i in nf_offset_indices if i < len(self.active_flags) and self.active_flags[i]]
        else:
            active_indices = [i for i, active in enumerate(self.active_flags) if active]

        if not active_indices:
            ax.text(0.5, 0.5, 'No active offsets', ha='center', va='center', transform=ax.transAxes)
            return fig

        colors = self._get_colors(config, len(active_indices))

        # Collect all frequency/velocity data for auto-limits
        all_freqs = []
        all_vels = []

        # First pass: plot spectrum background if enabled (use first offset's spectrum)
        if show_spectrum and hasattr(self, 'spectrum_data_list') and self.spectrum_data_list:
            # Find first available spectrum
            for layer_idx in active_indices:
                if layer_idx < len(self.spectrum_data_list) and self.spectrum_data_list[layer_idx] is not None:
                    spectrum_data = self.spectrum_data_list[layer_idx]
                    try:
                        spec_freqs = spectrum_data.get('frequencies', spectrum_data.get('freq'))
                        spec_vels = spectrum_data.get('velocities', spectrum_data.get('vel'))
                        spec_power = spectrum_data.get('power', spectrum_data.get('spectrum'))
                        
                        if spec_freqs is not None and spec_vels is not None and spec_power is not None:
                            ax.contourf(
                                spec_freqs, spec_vels, spec_power,
                                levels=config.spectrum_levels,
                                cmap=config.spectrum_colormap,
                                alpha=config.spectrum_alpha * 0.6
                            )
                            ax.set_xscale('log')
                            break  # Only use first spectrum
                    except Exception:
                        pass

        # Second pass: plot far-field points with original colors
        for idx, layer_idx in enumerate(active_indices):
            freqs = self.frequency_arrays[layer_idx]
            vels = self.velocity_arrays[layer_idx]
            label = self.layer_labels[layer_idx]

            if len(freqs) == 0:
                continue

            all_freqs.extend(freqs)
            all_vels.extend(vels)

            # Compute NACD for this offset
            nacd_values = self._compute_nacd_for_offset(layer_idx, config)

            if nacd_values is not None:
                far_field_mask = nacd_values >= config.nacd_threshold
            else:
                far_field_mask = np.ones(len(freqs), dtype=bool)

            # Adjust color if on spectrum background
            curve_color = colors[idx % len(colors)]
            if show_spectrum:
                # Brighten colors for visibility on spectrum
                pass  # Keep original colors for now

            # Plot far-field points with curve color
            if np.any(far_field_mask):
                ax.semilogx(
                    freqs[far_field_mask],
                    vels[far_field_mask],
                    marker='o',
                    linestyle='',
                    markerfacecolor='none',
                    markeredgecolor=curve_color,
                    markeredgewidth=1.2,
                    markersize=config.marker_size,
                    label=label,
                )

        # Third pass: plot ALL near-field points in red (on top)
        nf_freqs_all = []
        nf_vels_all = []
        
        for layer_idx in active_indices:
            freqs = self.frequency_arrays[layer_idx]
            vels = self.velocity_arrays[layer_idx]

            if len(freqs) == 0:
                continue

            nacd_values = self._compute_nacd_for_offset(layer_idx, config)

            if nacd_values is not None:
                near_field_mask = nacd_values < config.nacd_threshold
                if np.any(near_field_mask):
                    nf_freqs_all.extend(freqs[near_field_mask])
                    nf_vels_all.extend(vels[near_field_mask])

        # Plot all near-field points in red
        if nf_freqs_all:
            ax.semilogx(
                nf_freqs_all,
                nf_vels_all,
                marker='o',
                linestyle='',
                markerfacecolor='none',
                markeredgecolor=near_field_color,
                markeredgewidth=1.2,
                markersize=config.marker_size,
                label=f'Near-field (NACD<{config.nacd_threshold})',
            )

        # Configure axes
        ax.set_xlabel(config.xlabel, fontsize=config.font_size)
        ax.set_ylabel(config.ylabel, fontsize=config.font_size)

        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            # Calculate total NF percentage
            total_points = len(all_freqs)
            nf_points = len(nf_freqs_all)
            nf_pct = 100 * nf_points / total_points if total_points > 0 else 0
            ax.set_title(f'Combined NACD Analysis (threshold={config.nacd_threshold}, NF: {nf_pct:.1f}%)',
                        fontsize=config.title_fontsize or config.font_size + 2)

        # Add legend
        ax.legend(loc='upper right', fontsize=config.font_size - 1, ncol=2)

        if config.show_grid and not show_spectrum:
            ax.grid(True, alpha=config.grid_alpha, linestyle='-', which='both')

        # Set limits - auto based on curve data when spectrum is shown
        if config.xlim:
            ax.set_xlim(config.xlim)
        elif show_spectrum and all_freqs:
            freq_min, freq_max = np.min(all_freqs), np.max(all_freqs)
            freq_pad = 0.1 * (freq_max - freq_min) if freq_max > freq_min else 1.0
            ax.set_xlim(max(freq_min - freq_pad, freq_min * 0.8), freq_max + freq_pad)

        if config.ylim:
            ax.set_ylim(config.ylim)
        elif show_spectrum and all_vels:
            vel_min, vel_max = np.min(all_vels), np.max(all_vels)
            vel_pad = 0.1 * (vel_max - vel_min) if vel_max > vel_min else 50.0
            ax.set_ylim(max(0, vel_min - vel_pad), vel_max + vel_pad)

        if config.tight_layout:
            fig.tight_layout()

        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_nacd_comparison(
        self,
        output_path: Optional[str] = None,
        config: Optional['PlotConfig'] = None,
    ) -> Figure:
        """Generate overlaid NACD curves for all offsets on single plot.

        Shows NACD value vs frequency for each offset, with threshold line.

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)

        Returns:
            matplotlib Figure object
        """
        from ...config import PlotConfig
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        fig, ax = plt.subplots(figsize=config.figsize, dpi=config.dpi)

        # Get active indices
        active_indices = [i for i, active in enumerate(self.active_flags) if active]

        if not active_indices:
            ax.text(0.5, 0.5, 'No active offsets', ha='center', va='center', transform=ax.transAxes)
            return fig

        colors = self._get_colors(config, len(active_indices))

        # Plot NACD vs frequency for each offset
        for idx, layer_idx in enumerate(active_indices):
            freqs = self.frequency_arrays[layer_idx]
            label = self.layer_labels[layer_idx]

            if len(freqs) == 0:
                continue

            nacd_values = self._compute_nacd_for_offset(layer_idx, config)

            if nacd_values is not None:
                # Sort by frequency for line plot
                sort_idx = np.argsort(freqs)
                ax.semilogx(
                    freqs[sort_idx],
                    nacd_values[sort_idx],
                    marker='o',
                    markersize=config.marker_size * 0.5,
                    linewidth=config.line_width * 0.7,
                    color=colors[idx % len(colors)],
                    label=label,
                    alpha=0.8
                )

        # Draw threshold line
        ax.axhline(
            y=config.nacd_threshold,
            color='red',
            linestyle='--',
            linewidth=2,
            label=f'Threshold = {config.nacd_threshold}'
        )

        # Fill near-field region
        xlims = ax.get_xlim()
        ax.fill_between(
            [xlims[0], xlims[1]],
            0,
            config.nacd_threshold,
            alpha=0.15,
            color='red',
            label='Near-field region'
        )
        ax.set_xlim(xlims)

        ax.set_xlabel('Frequency (Hz)', fontsize=config.font_size)
        ax.set_ylabel('NACD', fontsize=config.font_size)

        if config.title:
            ax.set_title(config.title, fontsize=config.title_fontsize or config.font_size + 2)
        else:
            ax.set_title('NACD vs Frequency', fontsize=config.title_fontsize or config.font_size + 2)

        ax.legend(loc='upper right', fontsize=config.font_size - 2, ncol=2)

        if config.show_grid:
            ax.grid(True, alpha=config.grid_alpha, linestyle='--')

        ax.set_ylim(bottom=0)

        if config.tight_layout:
            fig.tight_layout()

        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def generate_nacd_summary(
        self,
        output_path: Optional[str] = None,
        config: Optional['PlotConfig'] = None,
    ) -> Figure:
        """Generate summary statistics of near-field contamination.

        Shows bar chart of percentage of data in near-field per offset.

        Args:
            output_path: Path to save figure (optional)
            config: Plot configuration (optional)

        Returns:
            matplotlib Figure object
        """
        from ...config import PlotConfig
        if config is None:
            config = PlotConfig()

        self._apply_style(config)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(config.figsize[0] * 1.5, config.figsize[1]), dpi=config.dpi)

        # Get active indices
        active_indices = [i for i, active in enumerate(self.active_flags) if active]

        if not active_indices:
            ax1.text(0.5, 0.5, 'No active offsets', ha='center', va='center', transform=ax1.transAxes)
            ax2.axis('off')
            return fig

        colors = self._get_colors(config, len(active_indices))

        # Compute statistics per offset
        labels = []
        nf_percentages = []
        total_points = []
        nf_points = []

        for layer_idx in active_indices:
            freqs = self.frequency_arrays[layer_idx]
            label = self.layer_labels[layer_idx]
            labels.append(label)

            if len(freqs) == 0:
                nf_percentages.append(0)
                total_points.append(0)
                nf_points.append(0)
                continue

            nacd_values = self._compute_nacd_for_offset(layer_idx, config)

            if nacd_values is not None:
                near_field_mask = nacd_values < config.nacd_threshold
                nf_count = int(np.sum(near_field_mask))
                total = len(freqs)
                nf_pct = 100 * nf_count / total
            else:
                nf_count = 0
                total = len(freqs)
                nf_pct = 0

            nf_percentages.append(nf_pct)
            total_points.append(total)
            nf_points.append(nf_count)

        # Left plot: Bar chart of NF percentage
        x = np.arange(len(labels))
        bars = ax1.bar(x, nf_percentages, color=colors[:len(labels)], alpha=0.8)

        ax1.set_xlabel('Offset', fontsize=config.font_size)
        ax1.set_ylabel('Near-Field %', fontsize=config.font_size)
        ax1.set_title('Near-Field Contamination by Offset', fontsize=config.font_size)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha='right', fontsize=config.font_size - 2)
        ax1.axhline(y=50, color='orange', linestyle='--', alpha=0.7, label='50% line')
        ax1.set_ylim(0, 100)

        # Add value labels on bars
        for bar, pct in zip(bars, nf_percentages):
            height = bar.get_height()
            ax1.annotate(f'{pct:.1f}%',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        fontsize=config.font_size - 3)

        if config.show_grid:
            ax1.grid(True, alpha=config.grid_alpha, axis='y', linestyle='--')

        # Right plot: Stacked bar showing total vs NF points
        ff_points = [t - n for t, n in zip(total_points, nf_points)]

        ax2.bar(x, ff_points, color='blue', alpha=0.7, label='Far-field')
        ax2.bar(x, nf_points, bottom=ff_points, color='red', alpha=0.7, label='Near-field')

        ax2.set_xlabel('Offset', fontsize=config.font_size)
        ax2.set_ylabel('Number of Points', fontsize=config.font_size)
        ax2.set_title('Data Point Distribution', fontsize=config.font_size)
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45, ha='right', fontsize=config.font_size - 2)
        ax2.legend(loc='upper right', fontsize=config.font_size - 2)

        if config.show_grid:
            ax2.grid(True, alpha=config.grid_alpha, axis='y', linestyle='--')

        if config.title:
            fig.suptitle(config.title, fontsize=config.title_fontsize or config.font_size + 2)

        if config.tight_layout:
            fig.tight_layout()

        if output_path:
            self._save_figure(fig, output_path, config)

        return fig

    def _compute_nacd_for_offset(
        self,
        layer_idx: int,
        config: 'PlotConfig',
    ) -> Optional[np.ndarray]:
        """Compute NACD values for a specific offset/layer.

        NACD = aperture / wavelength
        Where aperture depends on source position relative to receiver array.

        Args:
            layer_idx: Index of the layer/offset
            config: PlotConfig instance

        Returns:
            Array of NACD values, or None if computation not possible
        """
        from dc_cut.core.processing.nearfield import compute_nacd_array

        freqs = self.frequency_arrays[layer_idx]
        vels = self.velocity_arrays[layer_idx]

        if len(freqs) == 0:
            return None

        # Get array positions
        if self.array_positions is None:
            # Try to get default from preferences
            try:
                from dc_cut.services.prefs import load_prefs
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
                dx = float(P.get('default_receiver_dx', 2.0))
                array_pos = np.arange(0, dx * n_phones, dx)
            except Exception:
                array_pos = np.arange(0, 48, 2.0)  # Default: 24 geophones at 2m spacing
        else:
            array_pos = self.array_positions

        # Try to parse source offset from label to adjust aperture calculation
        label = self.layer_labels[layer_idx]
        source_offset = self._parse_source_offset_from_label(label)

        if source_offset is not None:
            # Calculate effective aperture based on source position
            arr_min = np.min(array_pos)
            arr_max = np.max(array_pos)

            # Source position determines the effective aperture for NACD
            # NACD typically uses distance from source to array center or farthest receiver
            if source_offset < arr_min:
                # Source is before the array - use distance to farthest receiver
                effective_aperture = arr_max - source_offset
            elif source_offset > arr_max:
                # Source is after the array
                effective_aperture = source_offset - arr_min
            else:
                # Source is within the array - use full array aperture
                effective_aperture = arr_max - arr_min

            # Compute NACD = aperture / wavelength
            wavelengths = vels / np.maximum(freqs, 1e-12)
            nacd_values = effective_aperture / np.maximum(wavelengths, 1e-12)
        else:
            # Fall back to standard NACD computation using array aperture
            nacd_values = compute_nacd_array(array_pos, freqs, vels)

        return nacd_values

    def _parse_source_offset_from_label(self, label: str) -> Optional[float]:
        """Parse source offset distance from layer label.

        Attempts to extract numeric offset from common label formats:
        - "fdbf_+66" or "fk -12" 
        - "Offset 12m" or "Offset -24m"
        - "+66" or "-12"

        Args:
            label: Layer label string

        Returns:
            Parsed offset value in meters, or None if parsing fails
        """
        import re

        if not label:
            return None

        # Look for patterns like +66, -12, _+66, _-12
        # Match signed or unsigned numbers, possibly preceded by _ or space
        pattern = r'[_\s]?([+-]?\d+\.?\d*)'
        matches = re.findall(pattern, label)
        
        if matches:
            try:
                # Take the last numeric match (usually the offset value)
                return float(matches[-1])
            except ValueError:
                pass

        return None

