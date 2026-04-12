"""
Data models — pure dataclasses, no Qt dependency.

SheetState is the single source of truth for one sheet/tab.
The renderer takes SheetState → Figure.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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

    # Spectrum association
    spectrum_uid: str = ""
    spectrum_visible: bool = False
    spectrum_cmap: str = "jet"
    spectrum_alpha: float = 0.85
    spectrum_colorbar: bool = False
    spectrum_colorbar_orient: str = "vertical"   # "vertical" | "horizontal"
    spectrum_colorbar_position: str = "right"     # "right", "left", "top", "bottom"
    spectrum_colorbar_label: str = ""

    def __post_init__(self):
        if not self.uid:
            self.uid = _short_uid()
        if self.point_mask is None and len(self.frequency) > 0:
            self.point_mask = np.ones(len(self.frequency), dtype=bool)

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

    def __post_init__(self):
        if not self.uid:
            self.uid = _short_uid()

    @property
    def has_data(self) -> bool:
        return self.power is not None and self.power.size > 0


# ── SubplotState ──────────────────────────────────────────────────────────

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

    # Label overrides (empty = use default)
    x_label: str = ""
    y_label: str = ""

    # Per-subplot legend (None/0/empty = use global defaults)
    legend_visible: Optional[bool] = None
    legend_position: str = ""
    legend_font_size: int = 0
    legend_frame_on: Optional[bool] = None

    @property
    def display_name(self) -> str:
        return self.name or self.key


# ── LegendConfig ──────────────────────────────────────────────────────────

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
    title_size: int = 12
    axis_label_size: int = 10
    tick_label_size: int = 9
    font_family: str = "sans-serif"


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
    canvas_dpi: int = 72

    # Legend
    legend: LegendConfig = field(default_factory=LegendConfig)

    # Typography
    typography: TypographyConfig = field(default_factory=TypographyConfig)

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
        old_keys = set(self.subplots.keys())
        for old_key in old_keys - new_keys:
            sp = self.subplots[old_key]
            orphan_uids.extend(sp.curve_uids)

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
