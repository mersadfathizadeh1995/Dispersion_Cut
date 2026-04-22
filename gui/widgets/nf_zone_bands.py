"""Matplotlib overlay helpers for NACD multi-zone bands and labels.

Pure matplotlib — no Qt.  Both DC Cut's live figure and Report Studio
can call these with their own axes.

Two public entry points:

* :func:`draw_zone_bands` — paints each :class:`ZoneBand` as an
  ``axhspan`` (λ axis) or ``axvspan`` (f axis) rectangle.  Returns the
  list of created artists so callers can clear them on the next draw.
* :func:`draw_zone_labels` — writes each group's "Zone 1 / Zone 2 /
  ..." annotations.  Each band's label is drawn on the axes that
  matches its ``band.axis`` (freq bands label on the V-vs-f plot,
  lambda bands on the V-vs-λ plot), at the top or bottom edge chosen
  by ``band.label_position``.  The label text is rendered in the
  zone's own band color so it reads as part of the band.

Both helpers happily accept an empty list.  Callers may pass
``visible_keys`` / ``color_overrides`` dicts keyed by
``(group_index, zone_index)`` to respect Limit Lines tab state.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from matplotlib.axes import Axes


ZONE_LABEL_FONTSIZE = 9
ZONE_LABEL_FONTWEIGHT = "bold"
ZONE_LABEL_ROW_SPACING_FRAC = 0.05


ZoneKey = Tuple[int, int]


# ───────────────────────────────────────────────────────────────────
#  Bands
# ───────────────────────────────────────────────────────────────────


def draw_zone_bands(
    ax_freq: Axes,
    ax_wave: Axes,
    bands: Iterable,
    *,
    visible_keys: Optional[Dict[ZoneKey, bool]] = None,
    color_overrides: Optional[Dict[ZoneKey, str]] = None,
) -> List:
    """Paint translucent ``axhspan`` / ``axvspan`` rectangles for each band.

    ``bands`` is an iterable of :class:`ZoneBand` (duck-typed — only
    ``axis``, ``lo``, ``hi``, ``color``, ``alpha``, ``group_index``
    and ``zone_index`` are accessed).  Bands with missing ``color`` or
    ``lo==hi`` are skipped silently.

    ``visible_keys`` lets the caller suppress individual zones by
    ``(group_index, zone_index)``; missing entries default to visible.
    ``color_overrides`` replaces the band color for a specific key
    (Limit Lines "set color" edits).  The returned list can be fed to
    :func:`clear_nf_zone_artists` to remove the artists later.
    """
    artists: List = []
    vis = visible_keys or {}
    overrides = color_overrides or {}
    for b in bands:
        gi = int(getattr(b, "group_index", 0))
        zi = int(getattr(b, "zone_index", 0))
        if not vis.get((gi, zi), True):
            continue
        color = overrides.get((gi, zi)) or getattr(b, "color", "")
        alpha = getattr(b, "alpha", 0.15)
        lo = float(getattr(b, "lo", 0.0))
        hi = float(getattr(b, "hi", 0.0))
        if not color or hi <= lo:
            continue

        # Clamp +inf to the visible axis limit so matplotlib renders a
        # finite rectangle.  The caller typically clamps in the spec
        # builder already, but keep a belt-and-braces here.
        axis = getattr(b, "axis", "lambda")
        if axis == "lambda":
            ax = ax_wave
            if not np.isfinite(hi):
                hi = float(ax.get_xlim()[1])
            patch = ax.axvspan(
                lo, hi, facecolor=color, alpha=alpha,
                linewidth=0, zorder=0.5, label="_nf_zone_band",
            )
        elif axis == "freq":
            ax = ax_freq
            if not np.isfinite(hi):
                hi = float(ax.get_xlim()[1])
            patch = ax.axvspan(
                lo, hi, facecolor=color, alpha=alpha,
                linewidth=0, zorder=0.5, label="_nf_zone_band",
            )
        else:
            continue
        artists.append(patch)
    return artists


# ───────────────────────────────────────────────────────────────────
#  Labels
# ───────────────────────────────────────────────────────────────────


def _pos_y(pos: str, row_offset: float) -> Tuple[float, str]:
    """Axes-fraction y + matplotlib va for ``label_position``."""
    if pos == "bottom":
        return 0.02 + row_offset, "bottom"
    # default top (treat "left"/"right" as top when mixed into freq/λ)
    return 1.0 - row_offset, "top"


def draw_zone_labels(
    ax_freq: Axes,
    ax_wave: Axes,
    bands: Sequence,
    *,
    row_spacing_frac: float = ZONE_LABEL_ROW_SPACING_FRAC,
    fontsize: int = ZONE_LABEL_FONTSIZE,
    visible_keys: Optional[Dict[ZoneKey, bool]] = None,
    color_overrides: Optional[Dict[ZoneKey, str]] = None,
) -> List:
    """Write a "Zone N" annotation into each band, colored by the band.

    One text is drawn per band (so the V-vs-f subplot *and* the
    V-vs-λ subplot both get their own annotations when the group
    emitted bands for both axes).  Groups that share the same
    ``label_position`` stack vertically: the first group gets the
    outermost row; subsequent groups are nudged toward the plot by
    ``row_spacing_frac`` axes-fraction units so the text never
    overlaps.

    ``visible_keys`` and ``color_overrides`` mirror the signature of
    :func:`draw_zone_bands` so the Limit Lines tab can hide or
    recolour zone labels individually.
    """
    artists: List = []
    if not bands:
        return artists

    # Determine per-group row (per edge) so overlapping groups don't
    # paint their labels on top of each other.  Each edge gets its own
    # count so "top" / "bottom" stacks are independent.
    edge_groups: dict[str, List[int]] = {"top": [], "bottom": []}
    seen: dict[int, str] = {}
    for b in bands:
        gi = int(getattr(b, "group_index", 0))
        pos = str(getattr(b, "label_position", "top"))
        if pos not in edge_groups:
            pos = "top"
        if gi not in seen:
            seen[gi] = pos
            if gi not in edge_groups[pos]:
                edge_groups[pos].append(gi)
    group_row: dict[int, int] = {}
    for pos, gids in edge_groups.items():
        for row, gi in enumerate(gids):
            group_row[gi] = row

    # Deduplicate to one label per (group_index, zone_index, axis) so
    # we don't paint the same ``ax_freq`` label twice when the spec
    # happens to emit duplicate bands.
    drawn: set = set()
    vis = visible_keys or {}
    overrides = color_overrides or {}
    for b in bands:
        gi = int(getattr(b, "group_index", 0))
        zi = int(getattr(b, "zone_index", 0))
        if not vis.get((gi, zi), True):
            continue
        axis = getattr(b, "axis", "lambda")
        pos = str(getattr(b, "label_position", "top"))
        if pos not in edge_groups:
            pos = "top"
        dedup = (gi, zi, axis)
        if dedup in drawn:
            continue
        drawn.add(dedup)

        label = str(getattr(b, "label", "") or f"Zone {zi + 1}")
        color = overrides.get((gi, zi)) or getattr(b, "color", "") or "#444"
        lo = float(getattr(b, "lo", 0.0))
        hi = float(getattr(b, "hi", 0.0))
        if hi <= lo:
            continue

        ax = ax_freq if axis == "freq" else ax_wave
        upper = float(ax.get_xlim()[1])
        x_hi = hi if np.isfinite(hi) else upper
        x_mid = 0.5 * (lo + x_hi)
        row = group_row.get(gi, 0)
        row_offset = row * float(row_spacing_frac)
        y_frac, va = _pos_y(pos, row_offset)
        try:
            trans = ax.get_xaxis_transform()
        except Exception:
            trans = ax.transAxes
        txt = ax.text(
            x_mid, y_frac, label,
            transform=trans,
            fontsize=fontsize,
            fontweight=ZONE_LABEL_FONTWEIGHT,
            color=color,
            ha="center", va=va,
            zorder=9,
            label="_nf_zone_label",
            bbox=dict(
                facecolor="white", edgecolor="none",
                alpha=0.7, pad=1.5,
            ),
        )
        artists.append(txt)

    return artists


# ───────────────────────────────────────────────────────────────────
#  Cleanup
# ───────────────────────────────────────────────────────────────────


def clear_nf_zone_artists(artists: List) -> None:
    """Remove each artist in ``artists`` and clear the list in place."""
    for a in list(artists):
        try:
            a.remove()
        except Exception:
            pass
    artists.clear()


__all__ = [
    "draw_zone_bands",
    "draw_zone_labels",
    "clear_nf_zone_artists",
    "ZONE_LABEL_FONTSIZE",
    "ZONE_LABEL_FONTWEIGHT",
    "ZONE_LABEL_ROW_SPACING_FRAC",
]
