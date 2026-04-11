"""Composable figure model for the Report Studio.

Hierarchical model: FigureModel -> SubplotModel -> DataSeries.
This replaces the flat "pick one plot type" approach with a composable
figure where users can assign data series to subplots, move them around,
and control per-series and per-subplot styling independently.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class DataSeries:
    """One offset's data assigned to a subplot with full style control."""
    uid: str = ""
    offset_index: int = 0
    label: str = ""
    subplot_key: str = ""
    visible: bool = True
    point_mask: Optional[List[bool]] = None
    color: Optional[str] = None
    line_width: Optional[float] = None
    line_style: str = "solid"
    show_line: bool = True
    marker_style: Optional[str] = "o"
    marker_size: Optional[float] = None
    alpha: float = 1.0
    legend_label: Optional[str] = None

    def __post_init__(self):
        if not self.uid:
            self.uid = uuid.uuid4().hex[:12]


@dataclass
class SubplotModel:
    """One subplot in the figure grid with axis and display config."""
    key: str = ""
    title: str = ""
    row: int = 0
    col: int = 0
    x_scale: str = "log"
    y_scale: str = "linear"
    x_label: str = "Frequency (Hz)"
    y_label: str = "Phase Velocity (m/s)"
    auto_x: bool = True
    auto_y: bool = True
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    show_grid: bool = True
    grid_alpha: float = 0.3
    grid_linestyle: str = "--"
    show_spectrum: bool = False
    spectrum_offset_index: Optional[int] = None
    show_legend: bool = True
    legend_location: str = "best"
    legend_ncol: int = 1

    def __post_init__(self):
        if not self.key:
            self.key = f"subplot_{uuid.uuid4().hex[:8]}"


@dataclass
class FigureModel:
    """Composable figure: a grid of subplots each containing data series."""
    subplots: List[SubplotModel] = field(default_factory=list)
    data_series: List[DataSeries] = field(default_factory=list)
    layout_rows: int = 1
    layout_cols: int = 1
    preset_origin: str = ""

    def series_for_subplot(self, subplot_key: str) -> List[DataSeries]:
        return [ds for ds in self.data_series if ds.subplot_key == subplot_key]

    def subplot_by_key(self, key: str) -> Optional[SubplotModel]:
        for sp in self.subplots:
            if sp.key == key:
                return sp
        return None

    def series_by_uid(self, uid: str) -> Optional[DataSeries]:
        for ds in self.data_series:
            if ds.uid == uid:
                return ds
        return None

    def add_subplot(self, title: str = "", row: int = 0, col: int = 0) -> SubplotModel:
        sp = SubplotModel(title=title, row=row, col=col)
        self.subplots.append(sp)
        return sp

    def add_data_series(self, subplot_key: str, offset_index: int,
                        label: str, **overrides) -> DataSeries:
        ds = DataSeries(
            offset_index=offset_index,
            label=label,
            subplot_key=subplot_key,
            **overrides,
        )
        self.data_series.append(ds)
        return ds

    def move_series(self, uid: str, new_subplot_key: str) -> bool:
        ds = self.series_by_uid(uid)
        if ds is None:
            return False
        if self.subplot_by_key(new_subplot_key) is None:
            return False
        ds.subplot_key = new_subplot_key
        return True

    def remove_series(self, uid: str) -> bool:
        for i, ds in enumerate(self.data_series):
            if ds.uid == uid:
                self.data_series.pop(i)
                return True
        return False

    def remove_subplot(self, key: str) -> bool:
        for i, sp in enumerate(self.subplots):
            if sp.key == key:
                self.data_series = [
                    ds for ds in self.data_series if ds.subplot_key != key
                ]
                self.subplots.pop(i)
                return True
        return False
