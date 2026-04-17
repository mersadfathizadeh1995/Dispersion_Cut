"""
Layout builder — create matplotlib subplot grids from SheetState.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import SheetState


def create_grid(
    fig: Figure,
    sheet_state: "SheetState",
    width_ratios: Optional[List[float]] = None,
    height_ratios: Optional[List[float]] = None,
) -> Dict[str, "Axes"]:
    """
    Create a grid of subplots on *fig* matching the sheet's layout.

    Returns a dict mapping subplot_key → Axes.
    """
    rows = sheet_state.grid_rows
    cols = sheet_state.grid_cols
    w_ratios = width_ratios or sheet_state.col_ratios
    h_ratios = height_ratios or sheet_state.row_ratios

    if len(w_ratios) < cols:
        w_ratios = w_ratios + [1.0] * (cols - len(w_ratios))
    w_ratios = w_ratios[:cols]

    if len(h_ratios) < rows:
        h_ratios = h_ratios + [1.0] * (rows - len(h_ratios))
    h_ratios = h_ratios[:rows]

    ordered_keys = sheet_state.subplot_keys_ordered()

    # Simple case: single subplot
    if rows == 1 and cols == 1:
        key = ordered_keys[0] if ordered_keys else "main"
        ax = fig.add_subplot(111)
        return {key: ax}

    # Grid layout
    gs = GridSpec(
        rows, cols, figure=fig,
        width_ratios=w_ratios,
        height_ratios=h_ratios,
        hspace=sheet_state.hspace,
        wspace=sheet_state.wspace,
    )
    axes: Dict[str, "Axes"] = {}

    for idx, key in enumerate(ordered_keys):
        r = idx // cols
        c = idx % cols
        if r < rows and c < cols:
            ax = fig.add_subplot(gs[r, c])
            axes[key] = ax

    return axes
