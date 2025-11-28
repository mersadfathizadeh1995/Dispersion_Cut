"""Base PublicationFigureGenerator class.

This module provides the main PublicationFigureGenerator class that:
    - Initializes from data arrays or Controller
    - Manages configuration
    - Provides common utilities for all plot types
    - Delegates to specialized modules for specific plot types
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING
from pathlib import Path
import logging

from dc_cut.pub_figures.config import PlotConfig, COLORBLIND_PALETTES

if TYPE_CHECKING:
    from dc_cut.core.controller import Controller
    import matplotlib.figure
    import matplotlib.axes

logger = logging.getLogger(__name__)


class PublicationFigureGenerator:
    """Generate publication-quality dispersion curve figures.
    
    This class provides methods to create various types of publication-ready
    figures from dispersion curve data. It supports multiple visualization
    styles and is designed for accessibility with colorblind-friendly palettes.
    
    Attributes:
        velocities: Array of velocity values (m/s)
        wavelengths: Array of wavelength values (m)
        offsets: Array of offset distances (m)
        data_matrix: 3D array of shape (n_offsets, n_wavelengths, n_velocities)
        picks: Dictionary of picks per offset
        limits: Dictionary of velocity limits per offset
        config: PlotConfig instance for styling
    
    Example:
        >>> gen = PublicationFigureGenerator.from_controller(controller)
        >>> gen.generate_aggregated_plot(output_path='figure.pdf')
    """
    
    def __init__(
        self,
        velocities: np.ndarray,
        wavelengths: np.ndarray,
        offsets: np.ndarray,
        data_matrix: Optional[np.ndarray] = None,
        picks: Optional[Dict[float, List[Tuple[float, float]]]] = None,
        limits: Optional[Dict[float, Tuple[float, float]]] = None,
        config: Optional[PlotConfig] = None,
    ):
        """Initialize the generator with data arrays.
        
        Args:
            velocities: 1D array of velocity values
            wavelengths: 1D array of wavelength values  
            offsets: 1D array of offset distances
            data_matrix: 3D spectrum array (n_offsets, n_wavelengths, n_velocities)
            picks: Dict mapping offset -> list of (velocity, wavelength) picks
            limits: Dict mapping offset -> (v_min, v_max) limits
            config: PlotConfig instance (uses defaults if None)
        """
        self.velocities = np.asarray(velocities)
        self.wavelengths = np.asarray(wavelengths)
        self.offsets = np.asarray(offsets)
        self.data_matrix = data_matrix
        self.picks = picks or {}
        self.limits = limits or {}
        self.config = config or PlotConfig()
        
        # Validate data
        self._validate_data()
        
        logger.info(f"PublicationFigureGenerator initialized with "
                   f"{len(self.offsets)} offsets, "
                   f"{len(self.wavelengths)} wavelengths, "
                   f"{len(self.velocities)} velocities")
    
    def _validate_data(self):
        """Validate input data dimensions."""
        if self.data_matrix is not None:
            expected_shape = (len(self.offsets), len(self.wavelengths), len(self.velocities))
            if self.data_matrix.shape != expected_shape:
                raise ValueError(
                    f"data_matrix shape {self.data_matrix.shape} does not match "
                    f"expected shape {expected_shape}"
                )
    
    @classmethod
    def from_controller(cls, controller: 'Controller', 
                       config: Optional[PlotConfig] = None) -> 'PublicationFigureGenerator':
        """Create generator from a DC_Cut Controller.
        
        Args:
            controller: DC_Cut Controller instance
            config: Optional PlotConfig (uses defaults if None)
            
        Returns:
            PublicationFigureGenerator instance
        """
        model = controller.model
        
        # Extract basic arrays
        velocities = model.velocities
        wavelengths = model.wavelengths
        offsets = np.array(list(model.spectra.keys()))
        
        # Build data matrix if spectra available
        data_matrix = None
        if model.spectra:
            n_offsets = len(offsets)
            n_wl = len(wavelengths)
            n_vel = len(velocities)
            data_matrix = np.zeros((n_offsets, n_wl, n_vel))
            
            for i, off in enumerate(offsets):
                if off in model.spectra:
                    spec = model.spectra[off]
                    if spec.shape == (n_wl, n_vel):
                        data_matrix[i] = spec
        
        # Extract picks and limits
        picks = {}
        for off in offsets:
            if off in model.picks:
                picks[off] = [(v, w) for v, w in model.picks[off]]
        
        limits = {}
        for off in offsets:
            if off in model.limits:
                limits[off] = model.limits[off]
        
        return cls(
            velocities=velocities,
            wavelengths=wavelengths,
            offsets=offsets,
            data_matrix=data_matrix,
            picks=picks,
            limits=limits,
            config=config,
        )
    
    # ========================================================================
    # Common Computation Methods
    # ========================================================================
    
    def _compute_wavelength_aggregates(
        self,
        method: str = 'mean'
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        """Compute aggregated velocity values across offsets per wavelength.
        
        Args:
            method: Aggregation method ('mean', 'median', 'weighted_mean')
            
        Returns:
            Tuple of (wavelengths, velocities, optional_std)
        """
        if not self.picks:
            logger.warning("No picks available for aggregation")
            return np.array([]), np.array([]), None
        
        # Collect all picks
        all_picks = []
        for offset, pick_list in self.picks.items():
            for v, w in pick_list:
                all_picks.append((w, v, offset))
        
        if not all_picks:
            return np.array([]), np.array([]), None
        
        # Group by wavelength (with tolerance)
        wavelength_groups = {}
        tolerance = 0.1 * np.min(np.diff(np.unique([p[0] for p in all_picks]))) if len(all_picks) > 1 else 0.1
        
        for w, v, off in all_picks:
            # Find existing group
            found = False
            for existing_w in wavelength_groups:
                if abs(w - existing_w) < tolerance:
                    wavelength_groups[existing_w].append((v, off))
                    found = True
                    break
            if not found:
                wavelength_groups[w] = [(v, off)]
        
        # Compute aggregates
        wavelengths = []
        velocities = []
        stds = []
        
        for w in sorted(wavelength_groups.keys()):
            values = [v for v, off in wavelength_groups[w]]
            wavelengths.append(w)
            
            if method == 'median':
                velocities.append(np.median(values))
            else:  # mean or weighted_mean
                velocities.append(np.mean(values))
            
            stds.append(np.std(values) if len(values) > 1 else 0)
        
        return np.array(wavelengths), np.array(velocities), np.array(stds)
    
    def _get_offset_colors(self, offsets: np.ndarray = None) -> Dict[float, str]:
        """Get color mapping for offsets.
        
        Args:
            offsets: Array of offsets (uses self.offsets if None)
            
        Returns:
            Dictionary mapping offset -> hex color
        """
        if offsets is None:
            offsets = self.offsets
        
        colors = self.config.get_colors(len(offsets))
        return {off: colors[i] for i, off in enumerate(offsets)}
    
    # ========================================================================
    # Basic Plot Methods
    # ========================================================================
    
    def generate_aggregated_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        show_uncertainty: bool = True,
        show_limits: bool = True,
        aggregation_method: str = 'mean',
    ) -> 'matplotlib.figure.Figure':
        """Generate aggregated dispersion curve plot.
        
        Shows a single curve with velocity aggregated across all offsets
        for each wavelength.
        
        Args:
            output_path: Path to save figure (optional)
            config: Override default config
            show_uncertainty: Show standard deviation envelope
            show_limits: Show velocity limits
            aggregation_method: 'mean', 'median', or 'weighted_mean'
            
        Returns:
            Matplotlib Figure object
        """
        import matplotlib.pyplot as plt
        
        cfg = config or self.config
        fig, ax = cfg.create_figure()
        
        # Compute aggregates
        wl, vel, std = self._compute_wavelength_aggregates(aggregation_method)
        
        if len(wl) == 0:
            logger.warning("No data for aggregated plot")
            ax.text(0.5, 0.5, 'No data available', ha='center', va='center',
                   transform=ax.transAxes)
            return fig
        
        # Plot main curve
        colors = cfg.get_colors(3)
        ax.plot(vel, wl, color=colors[0], linewidth=cfg.line_width,
               label='Aggregated', zorder=10)
        
        # Show uncertainty envelope
        if show_uncertainty and std is not None and np.any(std > 0):
            ax.fill_betweenx(wl, vel - std, vel + std,
                           color=colors[0], alpha=0.2,
                           label='±1σ')
        
        # Show velocity limits
        if show_limits and self.limits:
            v_min_agg = []
            v_max_agg = []
            for off, (vmin, vmax) in self.limits.items():
                v_min_agg.append(vmin)
                v_max_agg.append(vmax)
            
            if v_min_agg:
                ax.axvline(np.mean(v_min_agg), color=colors[1], linestyle='--',
                          linewidth=1, alpha=0.7, label='V min (mean)')
                ax.axvline(np.mean(v_max_agg), color=colors[2], linestyle='--',
                          linewidth=1, alpha=0.7, label='V max (mean)')
        
        # Apply configuration
        cfg.apply_to_axes(ax)
        
        # Legend
        ax.legend(loc=cfg.legend_position, frameon=cfg.legend_frameon,
                 fontsize=cfg.font_sizes.get('legend', 10))
        
        # Save if requested
        if output_path:
            cfg.save_figure(fig, output_path)
            logger.info(f"Saved aggregated plot to {output_path}")
        
        return fig
    
    def generate_per_offset_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        offsets_to_show: Optional[List[float]] = None,
        show_colorbar: bool = True,
        show_limits: bool = False,
    ) -> 'matplotlib.figure.Figure':
        """Generate per-offset dispersion curves plot.
        
        Shows separate curves for each offset, color-coded.
        
        Args:
            output_path: Path to save figure (optional)
            config: Override default config
            offsets_to_show: Subset of offsets to display
            show_colorbar: Show offset colorbar
            show_limits: Show velocity limits per offset
            
        Returns:
            Matplotlib Figure object
        """
        import matplotlib.pyplot as plt
        from matplotlib.cm import ScalarMappable
        from matplotlib.colors import Normalize
        
        cfg = config or self.config
        fig, ax = cfg.create_figure()
        
        # Determine offsets to plot
        offsets = offsets_to_show if offsets_to_show else self.offsets
        offsets = np.sort(offsets)
        
        if len(offsets) == 0:
            logger.warning("No offsets to plot")
            return fig
        
        # Color mapping
        cmap = plt.cm.viridis
        norm = Normalize(vmin=offsets.min(), vmax=offsets.max())
        
        # Plot each offset
        for off in offsets:
            if off not in self.picks:
                continue
            
            picks = self.picks[off]
            if not picks:
                continue
            
            vel = np.array([p[0] for p in picks])
            wl = np.array([p[1] for p in picks])
            
            # Sort by wavelength
            sort_idx = np.argsort(wl)
            vel, wl = vel[sort_idx], wl[sort_idx]
            
            color = cmap(norm(off))
            ax.plot(vel, wl, color=color, linewidth=cfg.line_width,
                   marker=cfg.marker_style, markersize=cfg.marker_size * 0.5)
            
            # Show limits
            if show_limits and off in self.limits:
                vmin, vmax = self.limits[off]
                ax.axvline(vmin, color=color, linestyle=':', linewidth=0.5, alpha=0.5)
                ax.axvline(vmax, color=color, linestyle=':', linewidth=0.5, alpha=0.5)
        
        # Colorbar
        if show_colorbar:
            sm = ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax)
            cbar.set_label(cfg.colorbar_label, fontsize=cfg.font_sizes.get('axis_label', 12))
        
        # Apply configuration
        cfg.apply_to_axes(ax)
        
        # Save if requested
        if output_path:
            cfg.save_figure(fig, output_path)
            logger.info(f"Saved per-offset plot to {output_path}")
        
        return fig
    
    def generate_dual_domain_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        show_uncertainty: bool = True,
    ) -> 'matplotlib.figure.Figure':
        """Generate dual-domain plot (wavelength and frequency).
        
        Shows dispersion curves in both wavelength-velocity and
        frequency-velocity domains side by side.
        
        Args:
            output_path: Path to save figure (optional)
            config: Override default config
            show_uncertainty: Show uncertainty bands
            
        Returns:
            Matplotlib Figure object
        """
        import matplotlib.pyplot as plt
        
        cfg = config or self.config
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(cfg.figsize[0] * 1.8, cfg.figsize[1]),
                                        dpi=cfg.dpi)
        
        # Compute aggregates
        wl, vel, std = self._compute_wavelength_aggregates()
        
        if len(wl) == 0:
            logger.warning("No data for dual domain plot")
            return fig
        
        colors = cfg.get_colors(2)
        
        # Left: Wavelength domain
        ax1.plot(vel, wl, color=colors[0], linewidth=cfg.line_width)
        if show_uncertainty and std is not None:
            ax1.fill_betweenx(wl, vel - std, vel + std, color=colors[0], alpha=0.2)
        
        ax1.set_xlabel('Velocity (m/s)', fontsize=cfg.font_sizes.get('axis_label', 12))
        ax1.set_ylabel('Wavelength (m)', fontsize=cfg.font_sizes.get('axis_label', 12))
        ax1.set_title('Wavelength Domain', fontsize=cfg.font_sizes.get('title', 14))
        if cfg.invert_y:
            ax1.invert_yaxis()
        ax1.grid(True, alpha=cfg.grid_alpha)
        
        # Right: Frequency domain (f = V / λ)
        freq = vel / wl  # Hz
        ax2.plot(vel, freq, color=colors[1], linewidth=cfg.line_width)
        if show_uncertainty and std is not None:
            freq_std = (std / wl)  # Approximate frequency uncertainty
            ax2.fill_betweenx(freq, vel - std, vel + std, color=colors[1], alpha=0.2)
        
        ax2.set_xlabel('Velocity (m/s)', fontsize=cfg.font_sizes.get('axis_label', 12))
        ax2.set_ylabel('Frequency (Hz)', fontsize=cfg.font_sizes.get('axis_label', 12))
        ax2.set_title('Frequency Domain', fontsize=cfg.font_sizes.get('title', 14))
        ax2.grid(True, alpha=cfg.grid_alpha)
        
        fig.tight_layout()
        
        # Save if requested
        if output_path:
            cfg.save_figure(fig, output_path)
            logger.info(f"Saved dual domain plot to {output_path}")
        
        return fig
    
    # ========================================================================
    # Uncertainty/Statistics Plots
    # ========================================================================
    
    def generate_uncertainty_plot(
        self,
        output_path: Optional[str] = None,
        config: Optional[PlotConfig] = None,
        show_individual_picks: bool = True,
        confidence_intervals: List[float] = [0.68, 0.95],
    ) -> 'matplotlib.figure.Figure':
        """Generate uncertainty visualization plot.
        
        Shows the dispersion curve with multiple confidence intervals
        and optionally individual pick points.
        
        Args:
            output_path: Path to save figure (optional)
            config: Override default config  
            show_individual_picks: Show individual pick points
            confidence_intervals: List of confidence levels (e.g., [0.68, 0.95])
            
        Returns:
            Matplotlib Figure object
        """
        import matplotlib.pyplot as plt
        
        cfg = config or self.config
        fig, ax = cfg.create_figure()
        
        colors = cfg.get_colors(3)
        
        # Compute aggregates with full statistics
        wl, vel, std = self._compute_wavelength_aggregates()
        
        if len(wl) == 0:
            logger.warning("No data for uncertainty plot")
            return fig
        
        # Show confidence intervals (approximating as Gaussian)
        alphas = [0.3, 0.15, 0.08]
        for i, ci in enumerate(sorted(confidence_intervals, reverse=True)):
            # Convert CI to sigma multiplier
            from scipy.stats import norm
            z = norm.ppf((1 + ci) / 2)
            
            ax.fill_betweenx(wl, vel - z * std, vel + z * std,
                           color=colors[0], alpha=alphas[min(i, len(alphas)-1)],
                           label=f'{int(ci*100)}% CI')
        
        # Plot mean curve
        ax.plot(vel, wl, color=colors[0], linewidth=cfg.line_width * 1.5,
               label='Mean')
        
        # Show individual picks
        if show_individual_picks:
            offset_colors = self._get_offset_colors()
            for off, picks in self.picks.items():
                if picks:
                    v = [p[0] for p in picks]
                    w = [p[1] for p in picks]
                    ax.scatter(v, w, s=cfg.marker_size, c=offset_colors[off],
                              alpha=0.4, edgecolors='none')
        
        # Apply configuration
        cfg.apply_to_axes(ax)
        
        # Legend
        ax.legend(loc=cfg.legend_position, frameon=cfg.legend_frameon,
                 fontsize=cfg.font_sizes.get('legend', 10))
        
        # Save if requested
        if output_path:
            cfg.save_figure(fig, output_path)
            logger.info(f"Saved uncertainty plot to {output_path}")
        
        return fig
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def list_available_plots(self) -> List[str]:
        """List all available plot types.
        
        Returns:
            List of plot type names
        """
        return [
            'aggregated',
            'per_offset',
            'dual_domain',
            'uncertainty',
        ]
    
    def generate(
        self,
        plot_type: str,
        output_path: Optional[str] = None,
        **kwargs
    ) -> 'matplotlib.figure.Figure':
        """Generate a plot by type name.
        
        Args:
            plot_type: Type of plot to generate
            output_path: Path to save figure
            **kwargs: Additional arguments for the specific plot type
            
        Returns:
            Matplotlib Figure object
        """
        plot_methods = {
            'aggregated': self.generate_aggregated_plot,
            'per_offset': self.generate_per_offset_plot,
            'dual_domain': self.generate_dual_domain_plot,
            'uncertainty': self.generate_uncertainty_plot,
        }
        
        if plot_type not in plot_methods:
            raise ValueError(f"Unknown plot type: {plot_type}. "
                           f"Available: {list(plot_methods.keys())}")
        
        return plot_methods[plot_type](output_path=output_path, **kwargs)
