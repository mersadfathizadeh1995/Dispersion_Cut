"""Composable renderer -- renders a FigureModel per-subplot.

Unlike the preset StudioRenderer that calls monolithic generator methods,
this renderer iterates over the FigureModel's subplots and data series,
drawing each individually with full per-series style control.
"""
from __future__ import annotations

from typing import Optional, List

import numpy as np
from matplotlib.figure import Figure

from ..config import PlotConfig
from ..generator import ReportGenerator
from ..styling import (
    apply_matplotlib_defaults,
    get_color_palette,
    apply_legend,
)
from .figure_model import FigureModel, SubplotModel, DataSeries
from .models import ReportStudioSettings


class ComposableRenderer:
    """Renders a FigureModel per-subplot with full per-series style overrides."""

    def __init__(self, generator: ReportGenerator):
        self._gen = generator

    def render(
        self,
        model: FigureModel,
        settings: ReportStudioSettings,
        fig: Figure,
    ) -> Figure:
        fig.clear()

        if not model.subplots:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No subplots defined",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=14, color="#888888")
            ax.set_xticks([])
            ax.set_yticks([])
            return fig

        config = self._build_config(settings)
        apply_matplotlib_defaults(config)

        rows, cols = model.layout_rows, model.layout_cols
        axes = fig.subplots(rows, cols, squeeze=False)

        for sp in model.subplots:
            if sp.row >= rows or sp.col >= cols:
                continue
            ax = axes[sp.row][sp.col]
            series = model.series_for_subplot(sp.key)
            visible_series = [ds for ds in series if ds.visible]

            if sp.show_spectrum:
                self._draw_spectrum_background(ax, sp, settings)

            palette = get_color_palette(config, max(len(visible_series), 1))
            for idx, ds in enumerate(visible_series):
                color = ds.color or palette[idx % len(palette)]
                self._draw_data_series(ax, ds, color, settings)

            self._configure_axis(ax, sp, settings)

            if sp.show_legend and visible_series:
                ax.legend(
                    loc=sp.legend_location,
                    ncol=sp.legend_ncol,
                    fontsize=settings.typography.legend_size,
                    frameon=settings.legend.frame_on,
                )
                leg = ax.get_legend()
                if leg:
                    try:
                        leg.set_draggable(True)
                    except AttributeError:
                        pass

        # Hide unused axes
        for r in range(rows):
            for c in range(cols):
                used = any(sp.row == r and sp.col == c for sp in model.subplots)
                if not used:
                    axes[r][c].set_visible(False)

        if settings.figure.tight_layout:
            try:
                fig.tight_layout()
            except Exception:
                pass

        return fig

    def _draw_data_series(
        self,
        ax,
        ds: DataSeries,
        fallback_color: str,
        settings: ReportStudioSettings,
    ) -> None:
        gen = self._gen
        idx = ds.offset_index
        if idx >= len(gen.frequency_arrays) or idx >= len(gen.velocity_arrays):
            return

        freq = gen.frequency_arrays[idx].copy()
        vel = gen.velocity_arrays[idx].copy()

        if ds.point_mask is not None:
            mask = np.array(ds.point_mask[:len(freq)])
            freq = np.where(mask, freq, np.nan)
            vel = np.where(mask, vel, np.nan)

        color = ds.color or fallback_color
        lw = ds.line_width if ds.line_width is not None else settings.line_width
        ls = ds.line_style or "solid"
        alpha = ds.alpha
        marker = ds.marker_style
        ms = ds.marker_size if ds.marker_size is not None else settings.marker_size
        label = ds.legend_label or ds.label

        if ds.show_line:
            ax.plot(
                freq, vel,
                color=color, linewidth=lw, linestyle=ls,
                marker=marker, markersize=ms,
                alpha=alpha, label=label,
                zorder=5,
            )
        elif marker:
            ax.plot(
                freq, vel,
                color=color, linestyle="none",
                marker=marker, markersize=ms,
                alpha=alpha, label=label,
                zorder=5,
            )

    def _draw_spectrum_background(
        self,
        ax,
        sp: SubplotModel,
        settings: ReportStudioSettings,
    ) -> None:
        gen = self._gen
        idx = sp.spectrum_offset_index
        if idx is None or idx >= len(gen.spectrum_data_list):
            return
        spec_data = gen.spectrum_data_list[idx]
        if spec_data is None:
            return

        spec_freqs = spec_data.get("frequencies", spec_data.get("freq"))
        spec_vels = spec_data.get("velocities", spec_data.get("vel"))
        spec_power = spec_data.get("power", spec_data.get("spectrum"))
        if spec_freqs is None or spec_vels is None or spec_power is None:
            return

        spec_cfg = settings.spectrum
        if spec_cfg.render_mode == "contour":
            cf = ax.contourf(
                spec_freqs, spec_vels, spec_power,
                levels=spec_cfg.levels,
                cmap=spec_cfg.colormap,
                alpha=spec_cfg.alpha,
                zorder=1,
            )
            if spec_cfg.show_colorbar:
                try:
                    ax.figure.colorbar(
                        cf, ax=ax,
                        orientation=spec_cfg.colorbar_orientation,
                        label="Power",
                        shrink=0.8,
                    )
                except Exception:
                    pass
        else:
            extent = [
                float(spec_freqs.min()), float(spec_freqs.max()),
                float(spec_vels.min()), float(spec_vels.max()),
            ]
            im = ax.imshow(
                spec_power, aspect="auto", origin="lower",
                extent=extent,
                cmap=spec_cfg.colormap,
                alpha=spec_cfg.alpha,
                zorder=1,
            )
            if spec_cfg.show_colorbar:
                try:
                    ax.figure.colorbar(
                        im, ax=ax,
                        orientation=spec_cfg.colorbar_orientation,
                        label="Power",
                        shrink=0.8,
                    )
                except Exception:
                    pass

    def _configure_axis(
        self,
        ax,
        sp: SubplotModel,
        settings: ReportStudioSettings,
    ) -> None:
        typo = settings.typography
        ax.set_xscale(sp.x_scale)
        ax.set_yscale(sp.y_scale)
        ax.set_xlabel(sp.x_label, fontsize=typo.axis_label_size)
        ax.set_ylabel(sp.y_label, fontsize=typo.axis_label_size)
        if sp.title:
            ax.set_title(sp.title, fontsize=typo.title_size, pad=typo.title_pad)
        ax.tick_params(labelsize=typo.tick_label_size)

        if sp.show_grid:
            ax.grid(True, alpha=sp.grid_alpha, linestyle=sp.grid_linestyle, linewidth=0.5)
        else:
            ax.grid(False)

        if not sp.auto_x and sp.x_min is not None and sp.x_max is not None:
            ax.set_xlim(sp.x_min, sp.x_max)
        if not sp.auto_y and sp.y_min is not None and sp.y_max is not None:
            ax.set_ylim(sp.y_min, sp.y_max)

    def _build_config(self, settings: ReportStudioSettings) -> PlotConfig:
        fig_cfg = settings.figure
        typo = settings.typography
        return PlotConfig(
            figsize=(fig_cfg.width, fig_cfg.height),
            dpi=fig_cfg.dpi,
            font_family=typo.font_family,
            font_size=int(typo.axis_label_size),
            font_weight=typo.font_weight,
            line_width=settings.line_width,
            marker_size=settings.marker_size,
            marker_style=settings.marker_style,
            color_palette=settings.color_palette,
        )
