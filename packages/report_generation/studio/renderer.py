"""Studio renderer -- bridges ReportStudioSettings to the existing ReportGenerator.

Translates the nested studio settings into a flat PlotConfig, then dispatches
to the appropriate ReportGenerator method. All rendering is done into a
provided matplotlib Figure (for live preview on the canvas).
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional, Dict, Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from ..config import PlotConfig
from ..generator import ReportGenerator
from .models import ReportStudioSettings


class StudioRenderer:
    """Renders a selected plot type into a matplotlib Figure using ReportGenerator."""

    def __init__(self, generator: ReportGenerator):
        self._generator = generator

    @property
    def generator(self) -> ReportGenerator:
        return self._generator

    def build_plot_config(self, settings: ReportStudioSettings) -> PlotConfig:
        """Translate nested studio settings into a flat PlotConfig."""
        fig_cfg = settings.figure
        typo = settings.typography
        ax = settings.axis
        leg = settings.legend
        spec = settings.spectrum
        overlay = settings.curve_overlay
        nf = settings.near_field

        return PlotConfig(
            figsize=(fig_cfg.width, fig_cfg.height),
            dpi=fig_cfg.dpi,
            font_family=typo.font_family,
            font_size=int(typo.axis_label_size),
            font_weight=typo.font_weight,
            line_width=settings.line_width,
            marker_size=settings.marker_size,
            marker_style=settings.marker_style,
            title=ax.title or None,
            title_fontsize=int(typo.title_size),
            legend_position=leg.location,
            legend_columns=leg.ncol,
            legend_frameon=leg.frame_on,
            color_palette=settings.color_palette,
            uncertainty_alpha=settings.uncertainty_alpha,
            near_field_alpha=nf.alpha,
            mark_near_field=nf.mark,
            near_field_style=nf.style,
            nacd_threshold=nf.nacd_threshold,
            nf_farfield_color=nf.farfield_color,
            nf_nearfield_color=nf.nearfield_color,
            nf_show_spectrum=nf.show_spectrum,
            nf_grid_display_mode=nf.grid_display_mode,
            nf_grid_offset_indices=nf.grid_offset_indices,
            show_grid=ax.grid.show,
            grid_alpha=ax.grid.alpha,
            xlabel=ax.xlabel,
            ylabel=ax.ylabel,
            xlim=(ax.x_min, ax.x_max) if not ax.auto_x and ax.x_min is not None and ax.x_max is not None else None,
            ylim=(ax.y_min, ax.y_max) if not ax.auto_y and ax.y_min is not None and ax.y_max is not None else None,
            output_format=settings.export.format,
            tight_layout=fig_cfg.tight_layout,
            spectrum_colormap=spec.colormap,
            spectrum_render_mode=spec.render_mode,
            spectrum_alpha=spec.alpha,
            spectrum_levels=spec.levels,
            show_spectrum_colorbar=spec.show_colorbar,
            peak_color=overlay.color,
            peak_outline=overlay.outline,
            peak_outline_color=overlay.outline_color,
            peak_line_width=overlay.line_width,
            curve_overlay_style=overlay.style,
            spectrum_colorbar_orientation=spec.colorbar_orientation,
            grid_offset_indices=None,
            grid_shared_colorbar=spec.colorbar_orientation,
        )

    def render(
        self,
        settings: ReportStudioSettings,
        fig: Figure,
        *,
        offset_index: int = 0,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Figure:
        """Render the active plot type into *fig*.

        Clears the figure, builds a PlotConfig from studio settings,
        and dispatches to the appropriate generator method.
        The generator creates its own axes via plt.subplots -- we intercept
        by temporarily patching plt.subplots to reuse *fig*.
        """
        fig.clear()

        plot_type = settings.active_plot_type
        if not plot_type:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "Select a plot type",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=14, color="#888888")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        config = self.build_plot_config(settings)
        gen = self._generator
        kw = extra_kwargs or {}

        _orig_subplots = plt.subplots

        def _patched_subplots(*args, **kwargs):
            """Redirect plt.subplots() into our existing figure."""
            fig.clear()
            figsize = kwargs.pop("figsize", None)
            dpi = kwargs.pop("dpi", None)
            if figsize:
                fig.set_size_inches(*figsize)
            nrows = args[0] if len(args) >= 1 else kwargs.pop("nrows", 1)
            ncols = args[1] if len(args) >= 2 else kwargs.pop("ncols", 1)
            squeeze = kwargs.pop("squeeze", True)
            subplot_kw = kwargs.pop("subplot_kw", None)
            gridspec_kw = kwargs.pop("gridspec_kw", None)
            axes = fig.subplots(
                nrows, ncols,
                squeeze=squeeze,
                subplot_kw=subplot_kw,
                gridspec_kw=gridspec_kw,
            )
            return fig, axes

        plt.subplots = _patched_subplots
        try:
            self._dispatch(gen, plot_type, config, offset_index, kw)
        finally:
            plt.subplots = _orig_subplots

        return fig

    def _dispatch(
        self,
        gen: ReportGenerator,
        plot_type: str,
        config: PlotConfig,
        offset_index: int,
        kw: Dict[str, Any],
    ) -> None:
        """Call the correct generator method for *plot_type*."""
        max_offsets = kw.get("max_offsets", 10)
        rows = kw.get("rows", None)
        cols = kw.get("cols", None)
        include_spectrum = kw.get("include_spectrum", False)
        include_curves = kw.get("include_curves", True)

        if plot_type == "aggregated":
            gen.generate_aggregated_plot(config=config)
        elif plot_type == "per_offset":
            gen.generate_per_offset_plot(config=config, max_offsets=max_offsets)
        elif plot_type == "uncertainty":
            gen.generate_uncertainty_plot(config=config)
        elif plot_type == "aggregated_wavelength":
            gen.generate_aggregated_wavelength_plot(config=config)
        elif plot_type == "per_offset_wavelength":
            gen.generate_per_offset_wavelength_plot(config=config, max_offsets=max_offsets)
        elif plot_type == "dual_domain":
            gen.generate_dual_domain_plot(config=config)
        elif plot_type == "canvas_frequency":
            gen.generate_canvas_frequency(config=config)
        elif plot_type == "canvas_wavelength":
            gen.generate_canvas_wavelength(config=config)
        elif plot_type == "canvas_dual":
            gen.generate_canvas_dual(config=config)
        elif plot_type == "offset_curve_only":
            gen.generate_offset_curve_only(offset_index=offset_index, config=config)
        elif plot_type == "offset_with_spectrum":
            gen.generate_offset_with_spectrum(offset_index=offset_index, config=config)
        elif plot_type == "offset_spectrum_only":
            gen.generate_offset_spectrum_only(offset_index=offset_index, config=config)
        elif plot_type == "offset_grid":
            spectrum_data_list = gen.spectrum_data_list if include_spectrum else None
            gen.generate_offset_grid(
                config=config, rows=rows, cols=cols,
                include_spectrum=include_spectrum,
                spectrum_data_list=spectrum_data_list,
                include_curves=include_curves,
            )
        elif plot_type == "nacd_curve":
            gen.generate_nacd_curve(config=config, offset_index=offset_index)
        elif plot_type == "nacd_grid":
            gen.generate_nacd_grid(config=config, rows=rows, cols=cols)
        elif plot_type == "nacd_combined":
            gen.generate_nacd_combined(config=config)
        elif plot_type == "nacd_comparison":
            gen.generate_nacd_comparison(config=config)
        elif plot_type == "nacd_summary":
            gen.generate_nacd_summary(config=config)
        else:
            raise NotImplementedError(f"Plot type '{plot_type}' is not yet implemented.")
