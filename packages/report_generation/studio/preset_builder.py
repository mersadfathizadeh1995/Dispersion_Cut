"""Preset builder -- converts plot type selections into FigureModel instances.

This bridges the old monolithic "pick a plot type" approach and the new
composable model. Each preset function creates a FigureModel with
appropriate subplots and data series pre-configured.
"""
from __future__ import annotations

import math
from typing import List, Optional

from ..generator import ReportGenerator
from .figure_model import FigureModel, SubplotModel, DataSeries
from .models import ReportStudioSettings


def build_from_preset(
    plot_type: str,
    generator: ReportGenerator,
    settings: ReportStudioSettings,
    *,
    offset_indices: Optional[List[int]] = None,
    grid_rows: Optional[int] = None,
    grid_cols: Optional[int] = None,
) -> FigureModel:
    """Convert a plot type key into a FigureModel.

    Parameters
    ----------
    offset_indices : list of int, optional
        Explicit offset indices for single-offset plot types. When multiple
        offsets are given, the builder creates a grid or multi-series subplot.
    grid_rows, grid_cols : int, optional
        Explicit grid layout. ``None`` means auto-compute.
    """
    labels = list(generator.layer_labels)
    active = list(generator.active_flags)
    active_indices = [i for i, a in enumerate(active) if a]

    if plot_type in ("aggregated", "uncertainty"):
        return _single_subplot_all_active(
            plot_type, labels, active_indices, title=plot_type.replace("_", " ").title(),
        )
    elif plot_type == "per_offset":
        return _single_subplot_all_active(
            plot_type, labels, active_indices, title="Per-Offset Frequency",
        )
    elif plot_type in ("aggregated_wavelength",):
        return _single_subplot_all_active(
            plot_type, labels, active_indices,
            title="Aggregated Wavelength",
            x_label="Wavelength (m)", y_label="Phase Velocity (m/s)",
        )
    elif plot_type == "per_offset_wavelength":
        return _single_subplot_all_active(
            plot_type, labels, active_indices,
            title="Per-Offset Wavelength",
            x_label="Wavelength (m)", y_label="Phase Velocity (m/s)",
        )
    elif plot_type == "dual_domain":
        return _dual_domain(labels, active_indices)
    elif plot_type in ("canvas_frequency", "canvas_wavelength", "canvas_dual"):
        return _canvas_preset(plot_type, labels, active_indices, generator)
    elif plot_type in ("offset_curve_only", "offset_with_spectrum", "offset_spectrum_only"):
        indices = offset_indices or [0]
        return _multi_offset(plot_type, indices, labels, generator,
                             grid_rows=grid_rows, grid_cols=grid_cols)
    elif plot_type == "offset_grid":
        indices = offset_indices or settings.grid_offset_indices or active_indices
        return _offset_grid(indices, labels, generator,
                            grid_rows=grid_rows, grid_cols=grid_cols)
    elif plot_type in ("nacd_curve",):
        return _single_subplot_all_active(
            plot_type, labels, active_indices, title="NACD Curve",
        )
    elif plot_type == "nacd_grid":
        indices = settings.near_field.grid_offset_indices or active_indices
        return _offset_grid(indices, labels, generator, title_prefix="NACD",
                            grid_rows=grid_rows, grid_cols=grid_cols)
    elif plot_type in ("nacd_combined", "nacd_comparison", "nacd_summary"):
        return _single_subplot_all_active(
            plot_type, labels, active_indices,
            title=plot_type.replace("_", " ").title(),
        )
    else:
        return _single_subplot_all_active(
            plot_type, labels, active_indices,
        )


def build_from_offset_selection(
    offset_indices: List[int],
    labels: List[str],
    layout_rows: int = 1,
    layout_cols: int = 1,
    generator: Optional[ReportGenerator] = None,
) -> FigureModel:
    """Custom: user picks offsets and grid layout."""
    model = FigureModel(
        layout_rows=layout_rows,
        layout_cols=layout_cols,
        preset_origin="custom",
    )
    for r in range(layout_rows):
        for c in range(layout_cols):
            sp = model.add_subplot(
                title=f"Subplot ({r},{c})", row=r, col=c,
            )
    if model.subplots:
        target = model.subplots[0].key
        for idx in offset_indices:
            lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
            has_spec = False
            if generator and idx < len(generator.spectrum_data_list):
                has_spec = generator.spectrum_data_list[idx] is not None
            model.add_data_series(target, idx, lbl)
    return model


def _single_subplot_all_active(
    preset: str,
    labels: List[str],
    active_indices: List[int],
    title: str = "",
    x_label: str = "Frequency (Hz)",
    y_label: str = "Phase Velocity (m/s)",
) -> FigureModel:
    model = FigureModel(layout_rows=1, layout_cols=1, preset_origin=preset)
    sp = model.add_subplot(title=title, row=0, col=0)
    sp.x_label = x_label
    sp.y_label = y_label
    for idx in active_indices:
        lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
        model.add_data_series(sp.key, idx, lbl)
    return model


def _dual_domain(labels: List[str], active_indices: List[int]) -> FigureModel:
    model = FigureModel(layout_rows=1, layout_cols=2, preset_origin="dual_domain")
    sp_freq = model.add_subplot(title="Frequency Domain", row=0, col=0)
    sp_freq.x_label = "Frequency (Hz)"
    sp_freq.y_label = "Phase Velocity (m/s)"
    sp_wave = model.add_subplot(title="Wavelength Domain", row=0, col=1)
    sp_wave.x_label = "Wavelength (m)"
    sp_wave.y_label = "Phase Velocity (m/s)"
    for idx in active_indices:
        lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
        model.add_data_series(sp_freq.key, idx, lbl)
        model.add_data_series(sp_wave.key, idx, lbl)
    return model


def _canvas_preset(
    plot_type: str,
    labels: List[str],
    active_indices: List[int],
    generator: ReportGenerator,
) -> FigureModel:
    if plot_type == "canvas_dual":
        model = FigureModel(layout_rows=1, layout_cols=2, preset_origin=plot_type)
        sp1 = model.add_subplot(title="Frequency", row=0, col=0)
        sp2 = model.add_subplot(title="Wavelength", row=0, col=1)
        sp2.x_label = "Wavelength (m)"
        for idx in active_indices:
            lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
            has_spec = (idx < len(generator.spectrum_data_list)
                        and generator.spectrum_data_list[idx] is not None)
            if has_spec:
                sp1.show_spectrum = True
                sp1.spectrum_offset_index = idx
            model.add_data_series(sp1.key, idx, lbl)
            model.add_data_series(sp2.key, idx, lbl)
        return model
    else:
        is_wave = "wavelength" in plot_type
        model = FigureModel(layout_rows=1, layout_cols=1, preset_origin=plot_type)
        sp = model.add_subplot(title="Canvas", row=0, col=0)
        if is_wave:
            sp.x_label = "Wavelength (m)"
        for idx in active_indices:
            lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
            has_spec = (idx < len(generator.spectrum_data_list)
                        and generator.spectrum_data_list[idx] is not None)
            if has_spec and not is_wave:
                sp.show_spectrum = True
                sp.spectrum_offset_index = idx
            model.add_data_series(sp.key, idx, lbl)
        return model


def _multi_offset(
    plot_type: str,
    indices: List[int],
    labels: List[str],
    generator: ReportGenerator,
    *,
    grid_rows: Optional[int] = None,
    grid_cols: Optional[int] = None,
) -> FigureModel:
    """Handle offset plot types with one or many selected offsets.

    * If only one offset is selected: single subplot with that offset.
    * If multiple offsets and grid_rows/cols both 1 (or unset): all offsets
      as separate DataSeries in one subplot.
    * If multiple offsets with grid layout > 1x1: one subplot per offset
      arranged in the grid (like _offset_grid).
    """
    n = len(indices)
    want_grid = (grid_rows is not None and grid_rows > 1) or \
                (grid_cols is not None and grid_cols > 1)

    if n > 1 and want_grid:
        return _offset_grid(indices, labels, generator,
                            grid_rows=grid_rows, grid_cols=grid_cols,
                            preset=plot_type)

    # Single subplot with all selected offsets as separate series
    model = FigureModel(layout_rows=1, layout_cols=1, preset_origin=plot_type)
    sp = model.add_subplot(row=0, col=0)
    if n == 1:
        idx = indices[0]
        lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
        sp.title = lbl
    else:
        sp.title = f"{n} Offsets"

    for idx in indices:
        lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
        has_spec = (idx < len(generator.spectrum_data_list)
                    and generator.spectrum_data_list[idx] is not None)
        if "spectrum" in plot_type and has_spec:
            sp.show_spectrum = True
            sp.spectrum_offset_index = idx
        model.add_data_series(sp.key, idx, lbl)
    return model


def _offset_grid(
    indices: List[int],
    labels: List[str],
    generator: ReportGenerator,
    title_prefix: str = "",
    *,
    grid_rows: Optional[int] = None,
    grid_cols: Optional[int] = None,
    preset: str = "offset_grid",
) -> FigureModel:
    n = len(indices)
    if grid_cols and grid_cols > 0:
        cols = grid_cols
    else:
        cols = min(n, 4)
    if grid_rows and grid_rows > 0:
        rows = grid_rows
    else:
        rows = math.ceil(n / cols) if cols else 1
    model = FigureModel(layout_rows=rows, layout_cols=cols, preset_origin=preset)
    for i, idx in enumerate(indices):
        r, c = divmod(i, cols)
        if r >= rows:
            break
        lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
        title = f"{title_prefix} {lbl}".strip() if title_prefix else lbl
        sp = model.add_subplot(title=title, row=r, col=c)
        has_spec = (idx < len(generator.spectrum_data_list)
                    and generator.spectrum_data_list[idx] is not None)
        if has_spec:
            sp.show_spectrum = True
            sp.spectrum_offset_index = idx
        model.add_data_series(sp.key, idx, lbl)
    return model
