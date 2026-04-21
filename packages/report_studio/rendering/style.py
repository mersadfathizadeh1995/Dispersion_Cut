"""
Rendering style configuration — colors, typography, axis styling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from ..core.models import SheetState


@dataclass
class StyleConfig:
    """Complete style configuration for figure rendering."""

    # Typography
    title_size: int = 12
    axis_label_size: int = 10
    tick_label_size: int = 9
    font_family: str = "sans-serif"
    font_weight: str = "normal"  # "normal" | "bold"
    # Decimal precision for frequency/wavelength labels (NACD/lambda lines)
    freq_decimals: int = 1
    lambda_decimals: int = 1

    # Axis
    grid_visible: bool = True
    grid_alpha: float = 0.3
    grid_style: str = "--"
    spine_width: float = 1.0

    # Legend
    legend_visible: bool = True
    legend_position: str = "best"
    legend_font_size: int = 9
    legend_frame_on: bool = True
    legend_alpha: float = 0.8

    # Spectrum colormap
    spectrum_cmap: str = "jet"
    spectrum_alpha: float = 0.85

    # Figure
    figure_facecolor: str = "#ffffff"
    subplot_facecolor: str = "#ffffff"
    dpi: int = 600

    # Axis labels
    frequency_label: str = "Frequency (Hz)"
    wavelength_label: str = "Wavelength (m)"
    velocity_label: str = "Phase Velocity (m/s)"

    def apply_to_axes(self, ax):
        """Apply common styling to a matplotlib Axes."""
        ax.tick_params(labelsize=self.tick_label_size)
        ax.grid(self.grid_visible, alpha=self.grid_alpha,
                linestyle=self.grid_style)
        for spine in ax.spines.values():
            spine.set_linewidth(self.spine_width)
        ax.set_facecolor(self.subplot_facecolor)

    def get_x_label(self, x_domain: str) -> str:
        return self.frequency_label if x_domain == "frequency" else self.wavelength_label

    def get_y_label(self) -> str:
        return self.velocity_label

    @classmethod
    def from_sheet(cls, sheet: "SheetState") -> "StyleConfig":
        """Build style from sheet legend + typography (base size × scales)."""
        t = sheet.typography
        leg_fs = (
            sheet.legend.font_size
            if sheet.legend.font_size > 0
            else t.legend_font_size
        )
        return cls(
            title_size=t.title_size,
            axis_label_size=t.axis_label_size,
            tick_label_size=t.tick_label_size,
            font_family=t.font_family,
            font_weight=getattr(t, "font_weight", "normal"),
            freq_decimals=int(getattr(t, "freq_decimals", 1)),
            lambda_decimals=int(getattr(t, "lambda_decimals", 1)),
            legend_visible=sheet.legend.visible,
            legend_position=sheet.legend.position,
            legend_font_size=leg_fs,
            legend_frame_on=sheet.legend.frame_on,
            legend_alpha=sheet.legend.alpha,
        )


# ── Color Palettes ────────────────────────────────────────────────────────

PALETTE_DEFAULT = [
    "#2196F3", "#F44336", "#4CAF50", "#FF9800", "#9C27B0",
    "#00BCD4", "#795548", "#607D8B", "#E91E63", "#CDDC39",
    "#FF5722", "#3F51B5",
]


def get_color(index: int, palette: List[str] = None) -> str:
    """Return a color from the palette, cycling if index exceeds length."""
    pal = palette or PALETTE_DEFAULT
    return pal[index % len(pal)]
