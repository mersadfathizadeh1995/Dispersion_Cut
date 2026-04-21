"""
Data models — pure dataclasses, no Qt dependency.

SheetState is the single source of truth for one sheet/tab.
The renderer takes SheetState → Figure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import subplot_types as ST


# ── Color palette ─────────────────────────────────────────────────────────

CURVE_COLORS = [
    "#2196F3",  # Blue
    "#F44336",  # Red
    "#4CAF50",  # Green
    "#FF9800",  # Orange
    "#9C27B0",  # Purple
    "#00BCD4",  # Cyan
    "#795548",  # Brown
    "#607D8B",  # Blue Grey
    "#E91E63",  # Pink
    "#CDDC39",  # Lime
    "#FF5722",  # Deep Orange
    "#3F51B5",  # Indigo
]


def _short_uid() -> str:
    return uuid.uuid4().hex[:8]


# ── NFLambdaLine (Layers-panel λ reference lines) ─────────────────────────

@dataclass
class NFLambdaLine:
    """One constant-λ guide line attached to a source-offset curve."""

    uid: str = ""
    lambda_value: float = 0.0
    source_offset: Optional[float] = None
    label: str = ""               # source label (e.g. "+66 m") — informational
    custom_label: str = ""        # user override for plot text; empty = auto λ=…
    color: str = "#000000"
    visible: bool = True
    line_style: str = "--"
    line_width: float = 1.5
    alpha: float = 0.85
    show_label: bool = True
    # Position along the visible line, 0.0 = left/bottom, 1.0 = right/top
    label_position: float = 0.55
    label_fontsize: int = 10
    label_rotation_mode: str = "along"  # "along" | "horizontal"
    # Optional background box behind label
    label_box: bool = True
    label_box_facecolor: str = "#ffffff"
    label_box_alpha: float = 0.75
    label_box_edgecolor: str = "#888888"
    label_box_pad: float = 2.0
    # Single multiplier that scales font + padding of the whole label box.
    label_scale: float = 1.0
    transform_used: str = ""

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = _short_uid()
        # Backward-compat: older projects stored label_position as "auto"/"top"/...
        if isinstance(self.label_position, str):
            mapping = {
                "auto": 0.55, "top": 0.85, "mid": 0.5,
                "bottom": 0.15, "start": 0.1, "end": 0.9,
            }
            self.label_position = float(mapping.get(self.label_position, 0.55))


# ── OffsetCurve ───────────────────────────────────────────────────────────

@dataclass
class OffsetCurve:
    """One dispersion curve (one source offset)."""

    uid: str = ""
    name: str = ""
    frequency: np.ndarray = field(default_factory=lambda: np.array([]))
    velocity: np.ndarray = field(default_factory=lambda: np.array([]))
    wavelength: np.ndarray = field(default_factory=lambda: np.array([]))

    # Display
    visible: bool = True
    color: str = "#2196F3"
    line_width: float = 1.5
    marker_size: float = 4.0
    line_style: str = "-"       # "-", "--", "-.", ":"
    marker_style: str = "o"     # "o", "s", "^", "D", "none"
    line_visible: bool = True
    marker_visible: bool = True

    # Peak display style
    peak_color: str = ""              # "" = use curve color
    peak_outline: bool = False
    peak_outline_color: str = "#000000"
    peak_outline_width: float = 1.0

    # Subplot assignment
    subplot_key: str = "main"

    # Per-point visibility
    point_mask: Optional[np.ndarray] = None

    # Wavelength (λ) guide lines from DC Cut Layers panel / PKL
    lambda_lines: List[NFLambdaLine] = field(default_factory=list)

    # Spectrum association
    spectrum_uid: str = ""
    spectrum_visible: bool = False
    spectrum_cmap: str = "jet"
    spectrum_alpha: float = 0.85
    spectrum_colorbar: bool = False
    spectrum_colorbar_orient: str = "vertical"   # "vertical" | "horizontal"
    spectrum_colorbar_position: str = "right"     # "right", "left", "top", "bottom"
    spectrum_colorbar_label: str = ""
    # Multiplier applied to the per-subplot colorbar's cax size, pad, and
    # tick/label fontsize so the user can scale the whole bar at once.
    spectrum_colorbar_scale: float = 1.0

    # Per-curve legend label override (empty = use ``name``)
    legend_label: str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = _short_uid()
        if self.point_mask is None and len(self.frequency) > 0:
            self.point_mask = np.ones(len(self.frequency), dtype=bool)

    def add_lambda_line(self, line: NFLambdaLine) -> None:
        if not line.uid:
            line.uid = _short_uid()
        self.lambda_lines.append(line)

    @property
    def has_data(self) -> bool:
        return self.frequency is not None and len(self.frequency) > 0

    @property
    def display_name(self) -> str:
        return self.name or self.uid

    @property
    def n_points(self) -> int:
        return len(self.frequency) if self.has_data else 0

    def masked_arrays(self, x_domain: str = "frequency"):
        """Return (x, y) arrays with masked points set to NaN."""
        if not self.has_data:
            return np.array([]), np.array([])
        x = self.frequency if x_domain == "frequency" else self.wavelength
        y = self.velocity.copy()
        x_out = x.copy().astype(float)
        if self.point_mask is not None and len(self.point_mask) == len(y):
            mask = ~self.point_mask
            x_out[mask] = np.nan
            y[mask] = np.nan
        return x_out, y


# ── SpectrumData ──────────────────────────────────────────────────────────

@dataclass
class SpectrumData:
    """Power spectrum for one offset (2D frequency×velocity image)."""

    uid: str = ""
    offset_name: str = ""
    frequencies: np.ndarray = field(default_factory=lambda: np.array([]))
    velocities: np.ndarray = field(default_factory=lambda: np.array([]))
    power: np.ndarray = field(default_factory=lambda: np.array([]))
    method: str = "fdbf"
    # Per-spectrum legend label override (empty = use ``offset_name``)
    legend_label: str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = _short_uid()

    @property
    def has_data(self) -> bool:
        return self.power is not None and self.power.size > 0


# ── AggregatedCurve ───────────────────────────────────────────────────────

@dataclass
class AggregatedCurve:
    """Binned average dispersion curve with uncertainty."""

    uid: str = ""
    name: str = "Average"

    # Computed arrays (frequency-domain by default)
    bin_centers: np.ndarray = field(default_factory=lambda: np.array([]))
    avg_vals: np.ndarray = field(default_factory=lambda: np.array([]))
    std_vals: np.ndarray = field(default_factory=lambda: np.array([]))

    # Binning configuration
    num_bins: int = 50
    log_bias: float = 0.7
    x_domain: str = "frequency"  # "frequency" | "wavelength"

    # Average line display
    avg_color: str = "#0173B2"
    avg_line_width: float = 2.0
    avg_line_style: str = "-"          # "-", "--", "-.", ":"
    avg_marker_style: str = "o"        # "o", "s", "^", "D", "none"
    avg_marker_size: float = 5.0
    avg_visible: bool = True

    # Uncertainty display
    uncertainty_mode: str = "band"     # "band" | "errorbar" | "sticks"
    uncertainty_alpha: float = 0.3
    uncertainty_color: str = ""        # "" = use avg_color
    uncertainty_visible: bool = True

    # Shadow curves (individual offsets as faded background)
    shadow_visible: bool = True
    shadow_alpha: float = 0.15

    # UIDs of associated shadow curves stored in SheetState.curves
    shadow_curve_uids: List[str] = field(default_factory=list)

    # Subplot assignment
    subplot_key: str = "main"

    # Per-aggregated legend label override (empty = use ``name``)
    legend_label: str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = _short_uid()

    @property
    def has_data(self) -> bool:
        return self.bin_centers is not None and len(self.bin_centers) > 0

    @property
    def display_name(self) -> str:
        return self.name or self.uid

    @property
    def effective_uncertainty_color(self) -> str:
        return self.uncertainty_color or self.avg_color


# ── Near-field (NACD-Only) analysis models ────────────────────────────────

@dataclass
class NFLine:
    uid: str = ""
    band_index: int = 0
    kind: str = "lambda"  # "lambda" | "freq"
    role: str = "max"  # "min" | "max"
    value: float = 0.0
    source: str = "user"  # "user" | "derived"
    valid: bool = True
    derived_from: Optional[float] = None
    color: str = "#000000"
    visible: bool = True
    line_style: str = "--"
    line_width: float = 1.5
    alpha: float = 0.85
    show_label: bool = True
    # Label rendering (mirrors :class:`NFLambdaLine` for λ/f guide styling)
    custom_label: str = ""
    label_position: float = 0.55
    label_fontsize: int = 0 # 0 → use renderer default
    label_rotation_mode: str = "along"  # "along" | "horizontal"
    label_box: bool = True
    label_box_facecolor: str = "#ffffff"
    label_box_alpha: float = 0.75
    label_box_edgecolor: str = "#888888"
    label_box_pad: float = 2.0
    # Single multiplier that scales font + padding of the whole label box.
    label_scale: float = 1.0
    source_offset: Optional[float] = None
    offset_label: str = ""
    display_label: str = ""
    lambda_max_curve: bool = False

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = _short_uid()
        if isinstance(self.label_position, str):
            mapping = {
                "auto": 0.55,
                "top": 0.85,
                "mid": 0.5,
                "bottom": 0.15,
                "start": 0.1,
                "end": 0.9,
            }
            self.label_position = float(mapping.get(self.label_position, 0.55))


@dataclass
class NFOffsetResult:
    label: str = ""
    offset_index: int = 0
    source_offset: Optional[float] = None
    x_bar: float = 0.0
    lambda_max: float = 0.0
    f: np.ndarray = field(default_factory=lambda: np.array([]))
    v: np.ndarray = field(default_factory=lambda: np.array([]))
    nacd: np.ndarray = field(default_factory=lambda: np.array([]))
    mask_contaminated: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=bool)
    )
    scatter_visible: bool = True
    point_hidden: Optional[np.ndarray] = None
    in_range: Optional[np.ndarray] = None
    severity: Optional[np.ndarray] = None
    n_total: int = 0
    n_clean: int = 0
    n_contaminated: int = 0


@dataclass
class NFAnalysis:
    uid: str = ""
    name: str = "NACD-Only"
    mode: str = "nacd"  # "nacd" | "reference"
    layout: str = "single"  # "single" | "grid" | "aggregated"
    per_offset: List[NFOffsetResult] = field(default_factory=list)
    lines: List[NFLine] = field(default_factory=list)
    severity_palette: Dict[str, str] = field(
        default_factory=lambda: {
            "clean": "#1f77b4",
            "marginal": "#ff7f0e",
            "contaminated": "#d62728",
            "unknown": "#888888",
        }
    )
    show_lambda_max: bool = True
    show_user_range: bool = True
    visible: bool = True
    severity_overlay_mode: str = "scatter_on_top"
    settings: Dict[str, Any] = field(default_factory=dict)
    source_offset: Optional[float] = None
    offset_label: str = ""
    use_range_as_mask: bool = False
    # Per-NACD legend label override (empty = use "Contaminated")
    legend_label: str = ""
    # Scatter (contaminated points) outline appearance. The previous
    # hard-coded look was a 0.5 px black box around every marker; these
    # fields let the user switch it off or restyle it per NACD analysis.
    contaminated_edge_visible: bool = True
    contaminated_edge_color: str = "#000000"
    contaminated_edge_width: float = 0.5

    def __post_init__(self) -> None:
        if not self.uid:
            self.uid = _short_uid()

    @property
    def display_name(self) -> str:
        if self.offset_label:
            return f"NACD: {self.offset_label}"
        return self.name or self.uid


# ── CombinedSpectrumBarConfig ─────────────────────────────────────────────

@dataclass
class CombinedSpectrumBarConfig:
    """Sheet-level single colorbar that replaces every per-subplot bar.

    When enabled and every spectrum drawn on the figure shares the same
    ``cmap``, ``vmin`` and ``vmax``, the renderer emits one figure-level
    colorbar on the chosen side (and grows the figure to make room, the
    same way the combined outside legend does). If the scales differ,
    the renderer leaves the per-subplot bars alone and appends a
    human-readable warning to ``SheetState._last_render_warnings`` so
    the main window can surface it in the status bar.
    """

    enabled: bool = False
    # "outside_right" | "outside_left" | "outside_top" | "outside_bottom"
    placement: str = "outside_right"
    # "auto" (vertical for left/right, horizontal for top/bottom),
    # "vertical", "horizontal"
    orientation: str = "auto"
    # Multiplier applied to fontsize + cax size + pad, 0.5–3.0.
    scale: float = 1.0
    label: str = ""
    pad: float = 0.05


# ── SubplotState ──────────────────────────────────────────────────────────

@dataclass
class SubplotLegendConfig:
    """Per-subplot legend layer (rich appearance + placement options).

    Mirrors the geo_figure ``LegendConfig`` so users get the same set of
    knobs in Report Studio. Lives on every :class:`SubplotState` and is
    consumed by :mod:`packages.report_studio.legend.builder`.
    """

    visible: bool = True
    location: str = "best"
    placement: str = "inside"  # inside | outside_left/right/top/bottom | adjacent
    bbox_anchor: Optional[Tuple[float, float]] = None
    ncol: int = 1
    fontsize: Optional[float] = None  # None → inherit typography.legend_font_size
    frame_on: bool = True
    frame_alpha: float = 0.9
    shadow: bool = False
    title: str = ""
    markerscale: float = 1.0
    hidden_labels: List[str] = field(default_factory=list)
    adjacent_side: str = "right"
    adjacent_target: str = ""
    offset_x: float = 0.0
    offset_y: float = 0.0
    # Multiplier applied to font/marker/handlelength so the user can
    # scale the *whole* legend block at once (50%-300%).
    scale: float = 1.0
    # "auto" (vertical for left/right, horizontal for top/bottom),
    # "vertical" (force ncol=1), "horizontal" (force ncol=N entries).
    orientation: str = "auto"
    # When True for outside placements, *every* subplot's legend is
    # merged into one figure-level legend on the requested side.
    # Otherwise each subplot gets its own legend just outside itself.
    combine: bool = True
    # When ``combine`` is True, drop labels that appear in multiple
    # subplots so the merged legend only lists them once.
    dedupe: bool = True
    # How aggressively to merge entries when ``dedupe`` is on:
    #   "exact"  – only collapse byte-identical labels (default).
    #   "prefix" – treat ``λ_max = 43 m``, ``λ_max = 33 m``… as the
    #              same entry and show just ``λ_max`` once.
    #   "range"  – same grouping as ``prefix`` but show the value
    #              span, e.g. ``λ_max = 28 – 53 m``.
    dedupe_kind: str = "exact"
    # Replace every dispersion-curve entry with a single combined row.
    # Useful when the legend would otherwise list one entry per source
    # offset (Love/fdbf -5, -10, -15, …).
    collapse_curves: bool = False
    # Display text used when ``collapse_curves`` is on.
    curves_label: str = "Source offset curves"
    # How to sort the final legend rows:
    #   "as_drawn" – matplotlib's draw order (default).
    #   "by_name"  – alphabetical, so similar names group together.
    #   "by_kind"  – curves first, then NACD, then guide lines.
    entry_order: str = "as_drawn"


@dataclass
class SubplotState:
    """State for one subplot in the figure grid."""

    key: str = "main"
    name: str = ""
    stype: str = ST.UNSET
    curve_uids: List[str] = field(default_factory=list)
    x_domain: str = "frequency"  # "frequency" | "wavelength"

    # Axis limits (None = auto)
    x_range: Optional[Tuple[float, float]] = None
    y_range: Optional[Tuple[float, float]] = None

    # Auto-limit flags
    auto_x: bool = True
    auto_y: bool = True

    # Axis scales: "linear" | "log"
    x_scale: str = "linear"
    y_scale: str = "linear"

    # Typography (per-subplot overrides; empty = use global)
    font_family: str = ""
    title_font_size: int = 0    # 0 = use global
    axis_label_font_size: int = 0
    tick_label_font_size: int = 0

    # Tick format: "plain" | "sci" | "eng"
    x_tick_format: str = "plain"
    y_tick_format: str = "plain"

    # Frequency-axis tick style (only used when x_domain == "frequency").
    # "decades" | "one-two-five" | "custom" | "ruler".
    # Default matches the dc_cut properties panel default.
    freq_tick_style: str = "one-two-five"
    # List of custom tick positions (Hz) used when ``freq_tick_style == "custom"``.
    freq_custom_ticks: List[float] = field(default_factory=list)

    # Label overrides (empty = use default)
    x_label: str = ""
    y_label: str = ""

    # Per-subplot legend (None/0/empty = use global defaults)
    # NOTE: kept for backward compatibility; new code reads ``legend``.
    legend_visible: Optional[bool] = None
    legend_position: str = ""
    legend_font_size: int = 0
    legend_frame_on: Optional[bool] = None

    # Rich per-subplot legend layer config (placement, ncol, frame, …)
    legend: SubplotLegendConfig = field(default_factory=SubplotLegendConfig)

    # Aggregated curve link (uid of AggregatedCurve, "" = none)
    aggregated_uid: str = ""

    # Near-field overlays (uids of NFAnalysis in SheetState.nf_analyses)
    nf_uids: List[str] = field(default_factory=list)

    # Last auto-computed axis limits from the renderer. These are transient
    # (not persisted) and are used to seed the spinboxes in
    # :class:`SubplotSettingsPanel` when the user unchecks "Auto" so the
    # manual fields start from the value the plot is currently showing
    # instead of defaulting to 0.0 / 0.0.
    last_auto_xlim: Optional[Tuple[float, float]] = None
    last_auto_ylim: Optional[Tuple[float, float]] = None

    @property
    def display_name(self) -> str:
        return self.name or self.key

    @property
    def nf_uid(self) -> str:
        """Backward-compat: first linked NF analysis."""
        return self.nf_uids[0] if self.nf_uids else ""

    @nf_uid.setter
    def nf_uid(self, uid: str) -> None:
        """Assign a single NF uid (replaces list)."""
        self.nf_uids = [uid] if uid else []


@dataclass
class LegendConfig:
    visible: bool = True
    position: str = "best"
    font_size: int = 9
    frame_on: bool = True
    alpha: float = 0.8


# ── TypographyConfig ──────────────────────────────────────────────────────

@dataclass
class TypographyConfig:
    """Global typography: base size × scales (defaults match legacy12/10/9 pt)."""

    base_size: int = 10
    title_scale: float = 1.2
    axis_label_scale: float = 1.0
    tick_label_scale: float = 0.9
    legend_scale: float = 0.9
    font_family: str = "sans-serif"
    font_weight: str = "normal"  # "normal" | "bold"
    # Decimal precision for frequency/wavelength labels on the canvas
    # (lambda guide lines, frequency guide lines, NACD legend entries…).
    freq_decimals: int = 1
    lambda_decimals: int = 1

    @property
    def title_size(self) -> int:
        return max(6, int(round(self.base_size * self.title_scale)))

    @property
    def axis_label_size(self) -> int:
        return max(6, int(round(self.base_size * self.axis_label_scale)))

    @property
    def tick_label_size(self) -> int:
        return max(6, int(round(self.base_size * self.tick_label_scale)))

    @property
    def legend_font_size(self) -> int:
        return max(6, int(round(self.base_size * self.legend_scale)))


# ── SheetState ────────────────────────────────────────────────────────────

@dataclass
class SheetState:
    """
    Complete state for one sheet/tab — the single source of truth.

    The unified renderer takes this and produces a matplotlib Figure.
    """

    name: str = "Sheet 1"

    # Data containers (keyed by uid)
    curves: Dict[str, OffsetCurve] = field(default_factory=dict)
    spectra: Dict[str, SpectrumData] = field(default_factory=dict)
    aggregated: Dict[str, AggregatedCurve] = field(default_factory=dict)

    # Subplot container (keyed by subplot key)
    subplots: Dict[str, SubplotState] = field(default_factory=dict)

    # Grid layout
    grid_rows: int = 1
    grid_cols: int = 1
    col_ratios: List[float] = field(default_factory=lambda: [1.0])
    row_ratios: List[float] = field(default_factory=lambda: [1.0])
    hspace: float = 0.3
    wspace: float = 0.3
    figure_width: float = 10.0
    figure_height: float = 7.0

    # Canvas rendering quality (DPI for interactive display)
    canvas_dpi: int = 600

    # Data source paths (for sheet-level persistence)
    pkl_path: str = ""
    npz_path: str = ""
    # Optional third "NF evaluation" sidecar file (JSON) exported from
    # DC Cut. When set, :class:`NacdOnlyPlugin` merges the sidecar
    # ``nf_results`` / ``nf_settings`` over whatever is embedded in the
    # PKL, giving users explicit control over the NF figure state.
    nf_sidecar_path: str = ""

    # Legend
    legend: LegendConfig = field(default_factory=LegendConfig)

    # Typography
    typography: TypographyConfig = field(default_factory=TypographyConfig)

    # Near-field analyses (NACD-Only / future reference mode)
    nf_analyses: Dict[str, NFAnalysis] = field(default_factory=dict)

    # Combined spectrum colorbar (figure-level; fuses every per-subplot
    # bar when all spectra share cmap/vmin/vmax).
    combined_spectrum_bar: CombinedSpectrumBarConfig = field(
        default_factory=CombinedSpectrumBarConfig
    )

    # Transient diagnostic messages the renderer writes each pass so the
    # main window can surface them in the status bar. NOT persisted.
    _last_render_warnings: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.subplots:
            self.subplots["main"] = SubplotState(key="main", name="Main")

    # ── Convenience helpers ────────────────────────────────────────────

    def add_curve(self, curve: OffsetCurve, subplot_key: str = "main"):
        """Add a curve to the sheet and assign it to a subplot."""
        self.curves[curve.uid] = curve
        curve.subplot_key = subplot_key
        if subplot_key not in self.subplots:
            self.subplots[subplot_key] = SubplotState(key=subplot_key)
        sp = self.subplots[subplot_key]
        if curve.uid not in sp.curve_uids:
            sp.curve_uids.append(curve.uid)
        sp.stype = ST.auto_assign_type(sp.stype, ST.KIND_CURVE)

    def remove_curve(self, uid: str):
        """Remove a curve from the sheet and its subplot."""
        if uid not in self.curves:
            return
        curve = self.curves.pop(uid)
        for sp in self.subplots.values():
            if uid in sp.curve_uids:
                sp.curve_uids.remove(uid)

    def remove_curves(self, uids: list):
        """Remove multiple curves in one pass."""
        uid_set = set(uids)
        for uid in uids:
            self.curves.pop(uid, None)
        for sp in self.subplots.values():
            sp.curve_uids = [u for u in sp.curve_uids if u not in uid_set]

    def move_curve(self, uid: str, new_subplot_key: str):
        """Move a curve from its current subplot to another."""
        if uid not in self.curves:
            return
        curve = self.curves[uid]
        old_key = curve.subplot_key
        # Remove from old
        if old_key in self.subplots:
            sp_old = self.subplots[old_key]
            if uid in sp_old.curve_uids:
                sp_old.curve_uids.remove(uid)
        # Add to new
        if new_subplot_key not in self.subplots:
            self.subplots[new_subplot_key] = SubplotState(key=new_subplot_key)
        sp_new = self.subplots[new_subplot_key]
        if uid not in sp_new.curve_uids:
            sp_new.curve_uids.append(uid)
        curve.subplot_key = new_subplot_key
        sp_new.stype = ST.auto_assign_type(sp_new.stype, ST.KIND_CURVE)

    def add_aggregated(self, agg: "AggregatedCurve", subplot_key: str = "main"):
        """Add an aggregated curve and link it to a subplot."""
        self.aggregated[agg.uid] = agg
        agg.subplot_key = subplot_key
        if subplot_key not in self.subplots:
            self.subplots[subplot_key] = SubplotState(key=subplot_key)
        self.subplots[subplot_key].aggregated_uid = agg.uid

    def remove_aggregated(self, uid: str):
        """Remove an aggregated curve and its shadow curves."""
        if uid not in self.aggregated:
            return
        agg = self.aggregated.pop(uid)
        # Unlink from subplot
        for sp in self.subplots.values():
            if sp.aggregated_uid == uid:
                sp.aggregated_uid = ""
        # Remove shadow curves
        self.remove_curves(list(agg.shadow_curve_uids))

    def move_aggregated(self, uid: str, new_subplot_key: str):
        """Move an aggregated curve and all its shadow curves to another subplot."""
        if uid not in self.aggregated:
            return
        agg = self.aggregated[uid]
        old_key = agg.subplot_key

        # Unlink from old subplot
        if old_key in self.subplots:
            self.subplots[old_key].aggregated_uid = ""

        # Move all shadow curves
        for sc_uid in agg.shadow_curve_uids:
            self.move_curve(sc_uid, new_subplot_key)

        # Link to new subplot
        if new_subplot_key not in self.subplots:
            self.subplots[new_subplot_key] = SubplotState(key=new_subplot_key)
        self.subplots[new_subplot_key].aggregated_uid = uid
        agg.subplot_key = new_subplot_key

    def set_grid(self, rows: int, cols: int):
        """Resize the subplot grid, migrating curves between subplots."""
        self.grid_rows = max(1, rows)
        self.grid_cols = max(1, cols)

        # Ensure col_ratios matches
        while len(self.col_ratios) < self.grid_cols:
            self.col_ratios.append(1.0)
        self.col_ratios = self.col_ratios[:self.grid_cols]
        # Ensure row_ratios matches
        while len(self.row_ratios) < self.grid_rows:
            self.row_ratios.append(1.0)
        self.row_ratios = self.row_ratios[:self.grid_rows]

        is_single = (self.grid_rows == 1 and self.grid_cols == 1)

        # Determine new subplot keys
        if is_single:
            new_keys = {"main"}
        else:
            new_keys = {
                f"cell_{r}_{c}"
                for r in range(self.grid_rows)
                for c in range(self.grid_cols)
            }

        # Collect all curve UIDs from old subplots that are disappearing
        orphan_uids: List[str] = []
        orphan_agg_uids: List[str] = []
        old_keys = set(self.subplots.keys())
        for old_key in old_keys - new_keys:
            sp = self.subplots[old_key]
            orphan_uids.extend(sp.curve_uids)
            if sp.aggregated_uid:
                orphan_agg_uids.append(sp.aggregated_uid)

        # Create new subplot entries
        if is_single:
            if "main" not in self.subplots:
                self.subplots["main"] = SubplotState(key="main", name="Main")
        else:
            for r in range(self.grid_rows):
                for c in range(self.grid_cols):
                    key = f"cell_{r}_{c}"
                    if key not in self.subplots:
                        self.subplots[key] = SubplotState(
                            key=key, name=f"Row {r+1}, Col {c+1}"
                        )

        # Migrate orphan curves to the first new subplot
        if orphan_uids:
            first_key = "main" if is_single else "cell_0_0"
            first_sp = self.subplots[first_key]
            for uid in orphan_uids:
                if uid in self.curves:
                    self.curves[uid].subplot_key = first_key
                    if uid not in first_sp.curve_uids:
                        first_sp.curve_uids.append(uid)

        # Migrate orphan aggregated UIDs to the first new subplot
        if orphan_agg_uids:
            first_key = "main" if is_single else "cell_0_0"
            first_sp = self.subplots[first_key]
            for agg_uid in orphan_agg_uids:
                if agg_uid in self.aggregated:
                    self.aggregated[agg_uid].subplot_key = first_key
                    if not first_sp.aggregated_uid:
                        first_sp.aggregated_uid = agg_uid

        # Remove old subplots that are no longer in the grid
        for old_key in old_keys - new_keys:
            del self.subplots[old_key]

    def subplot_keys_ordered(self) -> List[str]:
        """Return subplot keys in row-major grid order."""
        if self.grid_rows == 1 and self.grid_cols == 1:
            return ["main"] if "main" in self.subplots else list(self.subplots.keys())[:1]
        keys = []
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                key = f"cell_{r}_{c}"
                if key in self.subplots:
                    keys.append(key)
        return keys

    def populated_subplot_info(self) -> tuple:
        """Return (keys, display_names) for subplots that have curves."""
        keys = []
        names = {}
        for k in self.subplot_keys_ordered():
            sp = self.subplots[k]
            if sp.curve_uids:
                keys.append(k)
                names[k] = sp.display_name
        return keys, names

    def get_curves_for_subplot(self, subplot_key: str) -> List[OffsetCurve]:
        """Return all curves assigned to a subplot, in order."""
        sp = self.subplots.get(subplot_key)
        if not sp:
            return []
        return [self.curves[uid] for uid in sp.curve_uids if uid in self.curves]

    def add_nf_analysis(self, nf: NFAnalysis, subplot_key: str = "") -> None:
        self.nf_analyses[nf.uid] = nf
        if subplot_key and subplot_key in self.subplots:
            sp = self.subplots[subplot_key]
            if nf.uid not in sp.nf_uids:
                sp.nf_uids.append(nf.uid)

    def remove_nf_analysis(self, uid: str) -> None:
        self.nf_analyses.pop(uid, None)
        for sp in self.subplots.values():
            sp.nf_uids = [u for u in sp.nf_uids if u != uid]

    def move_nf_analysis(self, uid: str, new_subplot_key: str) -> None:
        for sp in self.subplots.values():
            sp.nf_uids = [u for u in sp.nf_uids if u != uid]
        if new_subplot_key in self.subplots:
            sp = self.subplots[new_subplot_key]
            if uid not in sp.nf_uids:
                sp.nf_uids.append(uid)

    def clear_subplot(self, key: str) -> None:
        """Remove every piece of data attached to one subplot cell.

        Used by the "Clear subplot" context-menu action. The cell itself
        stays in the grid (``grid_rows``/``grid_cols`` untouched); only
        its curves, aggregated curve, NF analyses and spectrum links are
        dropped. Spectra that become unreferenced are garbage-collected
        so project files don't accumulate orphans.
        """
        sp = self.subplots.get(key)
        if sp is None:
            return

        # Aggregated curves first — this also removes any shadow curves
        # via ``remove_aggregated``.
        agg_uid = sp.aggregated_uid
        if agg_uid:
            self.remove_aggregated(agg_uid)

        for uid in list(sp.curve_uids):
            self.remove_curve(uid)

        for nf_uid in list(sp.nf_uids):
            self.remove_nf_analysis(nf_uid)

        sp.curve_uids = []
        sp.nf_uids = []
        sp.aggregated_uid = ""

        referenced_spectra = {
            c.spectrum_uid for c in self.curves.values() if c.spectrum_uid
        }
        for spec_uid in list(self.spectra.keys()):
            if spec_uid not in referenced_spectra:
                self.spectra.pop(spec_uid, None)
