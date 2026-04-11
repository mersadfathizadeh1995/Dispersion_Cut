"""Data models for the Report Studio settings.

Nested dataclass hierarchy that drives all studio panels and the render cycle.
The StudioRenderer bridges these into a flat PlotConfig for the existing
ReportGenerator mixins.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List


@dataclass
class FigureConfig:
    width: float = 8.0
    height: float = 6.0
    dpi: int = 300
    preview_dpi: int = 100
    margin_left: float = 0.8
    margin_right: float = 0.3
    margin_top: float = 0.4
    margin_bottom: float = 0.6
    tight_layout: bool = True
    facecolor: str = "white"


@dataclass
class TypographyConfig:
    font_family: str = "serif"
    font_weight: str = "normal"
    title_size: float = 14.0
    axis_label_size: float = 12.0
    tick_label_size: float = 10.0
    legend_size: float = 10.0
    annotation_size: float = 9.0
    title_pad: float = 6.0
    label_pad: float = 4.0
    bold_ticks: bool = False


@dataclass
class GridConfig:
    show: bool = True
    which: str = "major"
    linestyle: str = "--"
    alpha: float = 0.3
    linewidth: float = 0.5


@dataclass
class TickConfig:
    direction: str = "out"
    show_top: bool = False
    show_right: bool = False
    show_minor: bool = False
    major_length: float = 4.0
    minor_length: float = 2.0


@dataclass
class AxisConfig:
    title: str = ""
    auto_x: bool = True
    auto_y: bool = True
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    x_scale: str = "log"
    y_scale: str = "linear"
    xlabel: str = "Frequency (Hz)"
    ylabel: str = "Phase Velocity (m/s)"
    show_x_label: bool = True
    show_y_label: bool = True
    ticks: TickConfig = field(default_factory=TickConfig)
    grid: GridConfig = field(default_factory=GridConfig)


@dataclass
class LegendConfig:
    show: bool = True
    location: str = "best"
    placement: str = "inside"
    ncol: int = 1
    fontsize: Optional[float] = None
    frame_on: bool = False
    frame_alpha: float = 0.8
    shadow: bool = False
    markerscale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    hidden_labels: List[str] = field(default_factory=list)


@dataclass
class ExportConfig:
    format: str = "pdf"
    dpi: int = 300
    transparent: bool = False
    tight_bbox: bool = True
    pad_inches: float = 0.1
    facecolor: str = "white"
    legend_separate: bool = False


@dataclass
class OutputConfig:
    directory: str = ""
    auto_name: bool = True
    overwrite: bool = False
    name_template: str = ""


@dataclass
class SpectrumConfig:
    colormap: str = "viridis"
    render_mode: str = "imshow"
    alpha: float = 0.8
    levels: int = 30
    show_colorbar: bool = True
    colorbar_orientation: str = "vertical"


@dataclass
class CurveOverlayConfig:
    color: str = "#FFFFFF"
    outline: bool = True
    outline_color: str = "#000000"
    line_width: float = 2.5
    style: str = "line"


@dataclass
class NearFieldConfig:
    mark: bool = True
    style: str = "faded"
    alpha: float = 0.4
    nacd_threshold: float = 1.0
    farfield_color: str = "blue"
    nearfield_color: str = "red"
    show_spectrum: bool = False
    grid_display_mode: str = "curves"
    grid_offset_indices: Optional[List[int]] = None


@dataclass
class StudioLayerState:
    """Per-layer style overrides and point mask for the Report Studio."""
    index: int = 0
    label: str = ""
    visible: bool = True
    point_mask: Optional[List[bool]] = None
    color: Optional[str] = None
    line_width: Optional[float] = None
    line_style: str = "solid"
    marker_size: Optional[float] = None
    marker_style: Optional[str] = None
    alpha: float = 1.0
    legend_label: Optional[str] = None


@dataclass
class ReportStudioSettings:
    """Aggregate settings object for the Report Studio.

    Follows the same pattern as geo_figure's StudioSettings: a top-level
    container with named sub-configs and per-subplot override dicts.
    """
    figure: FigureConfig = field(default_factory=FigureConfig)
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    axis: AxisConfig = field(default_factory=AxisConfig)
    legend: LegendConfig = field(default_factory=LegendConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    spectrum: SpectrumConfig = field(default_factory=SpectrumConfig)
    curve_overlay: CurveOverlayConfig = field(default_factory=CurveOverlayConfig)
    near_field: NearFieldConfig = field(default_factory=NearFieldConfig)

    active_plot_type: str = ""
    committed: bool = False
    color_palette: str = "vibrant"
    line_width: float = 1.5
    marker_size: float = 4.0
    marker_style: str = "o"
    uncertainty_alpha: float = 0.3
    max_offsets: int = 10
    grid_offset_indices: Optional[List[int]] = None
    layer_states: List[StudioLayerState] = field(default_factory=list)

    axis_overrides: Dict[str, AxisConfig] = field(default_factory=dict)
    legend_overrides: Dict[str, LegendConfig] = field(default_factory=dict)

    def axis_for(self, key: str) -> AxisConfig:
        """Return per-subplot axis config, creating from defaults on first access."""
        if key not in self.axis_overrides:
            self.axis_overrides[key] = copy.deepcopy(self.axis)
        return self.axis_overrides[key]

    def legend_for(self, key: str) -> LegendConfig:
        """Return per-subplot legend config, creating from defaults on first access."""
        if key not in self.legend_overrides:
            self.legend_overrides[key] = copy.deepcopy(self.legend)
        return self.legend_overrides[key]


# Typography-only presets
PRESETS = {
    "publication": TypographyConfig(
        font_family="serif",
        font_weight="normal",
        title_size=14.0,
        axis_label_size=12.0,
        tick_label_size=10.0,
        legend_size=10.0,
        annotation_size=9.0,
        title_pad=6.0,
        label_pad=4.0,
        bold_ticks=False,
    ),
    "compact": TypographyConfig(
        font_family="sans-serif",
        font_weight="normal",
        title_size=11.0,
        axis_label_size=9.0,
        tick_label_size=8.0,
        legend_size=8.0,
        annotation_size=7.0,
        title_pad=4.0,
        label_pad=3.0,
        bold_ticks=False,
    ),
}

PRESET_LABELS = {
    "publication": "Publication (Serif 14/12/10)",
    "compact": "Compact (Sans-serif 11/9/8)",
}


def apply_preset(settings: ReportStudioSettings, name: str) -> None:
    """Apply a named typography preset to *settings* in-place."""
    preset = PRESETS.get(name)
    if preset is None:
        return
    for f in preset.__dataclass_fields__:
        setattr(settings.typography, f, getattr(preset, f))
