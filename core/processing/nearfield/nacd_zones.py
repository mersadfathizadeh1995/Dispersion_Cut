"""NACD multi-zone specification.

This module adds two "view styles" on top of the classical
single-threshold NACD rule (``contaminated = NACD < threshold``):

* **multi_zone** — a single ordered list of NACD thresholds partitions
  the picks into ``N+1`` zones. Each zone has its own fill tint *and*
  its own scatter-point color so points are coloured by which zone they
  fall into (e.g. red on the contaminated side of ``NACD = 1``, blue on
  the clean side).  Only the vertical ``f`` guide is emitted by
  default — no λ hyperbola — because the user asked for a single
  cleanly-labelled ``NACD = <value>`` marker per threshold.
* **multi_group** — several independent zone lists drawn together on
  the same axes with different label positions so overlays don't
  collide (kept for completeness; the multi-zone UI is the primary
  surface today).

Data model
----------

Each :class:`ZoneGroup` owns:

* ``thresholds`` — ``N`` :class:`ZoneThreshold` rows, each carrying a
  NACD value, a line color and an optional custom label (the text
  written on the vertical line, defaulting to ``"NACD = <value>"``).
* ``zones`` — ``N+1`` :class:`ZoneFill` rows describing the
  translucent band color/alpha, the scatter-point color and the zone
  label for each of the ``N+1`` resulting zones.  Zone index 0 is the
  contaminated (low-f / large-λ / small-NACD) side, zone ``N`` is the
  clean side.

Every threshold is projected onto a :class:`DerivedLimitSet` so the
existing Limit Lines tree is the single source of truth for toggling,
recolouring and persisting individual lines.  The translucent band
and the zone label annotations are rendering concerns and are
re-derived from the spec on every draw.

No framework imports — pure computation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Literal, Optional, Sequence, Tuple

import numpy as np

from dc_cut.core.processing.nearfield.range_derivation import (
    DerivedLimitSet,
    DerivedLine,
    _solve_f_for_lambda,
)


ZoneStyle = Literal["classic", "multi_zone", "multi_group"]
LabelPosition = Literal["top", "bottom", "left", "right"]

_ALLOWED_STYLES: Tuple[str, ...] = ("classic", "multi_zone", "multi_group")
_ALLOWED_POSITIONS: Tuple[str, ...] = ("top", "bottom", "left", "right")

# Band-index reserved range for zone "label" rows in the DerivedLimitSet.
# Chosen high enough that real threshold band indices (0..N) never
# collide.  Every group gets a single zone band at
# ``ZONE_BAND_INDEX_OFFSET + group_index`` containing one leaf per zone.
ZONE_BAND_INDEX_OFFSET: int = 10000


# ───────────────────────────────────────────────────────────────────
#  Data classes
# ───────────────────────────────────────────────────────────────────


@dataclass
class ZoneThreshold:
    """One NACD divider between two zones.

    ``line_label`` overrides the default ``"NACD = <value>"`` text that
    is drawn on the vertical ``f`` guide and shown in the Limit Lines
    tree.  Leaving it empty falls back to the auto-formatted default.
    """

    nacd: float
    line_color: str = ""
    line_label: str = ""

    def resolved_label(self) -> str:
        txt = (self.line_label or "").strip()
        if txt:
            return txt
        return f"NACD = {self.nacd:g}"


@dataclass
class ZoneArrow:
    """Optional double-headed arrow spanning a zone's band.

    Rendered inside the zone's extent along the x-axis, at a fixed
    fraction of the axes height (``y_frac``). The arrow is intended
    to visually emphasise each zone's width (see the Zone I / Zone II
    reference screenshot).

    ``enabled`` defaults to ``False`` so v1 pickles render unchanged;
    multi-zone specs created after v2 flip it on by default.
    """

    enabled: bool = False
    color: str = "#C00000"
    linewidth: float = 1.8
    y_frac: float = 0.50  # axes-fraction y-coordinate
    style: str = "<->"    # matplotlib arrowstyle spec
    text: str = ""        # label drawn near the arrow (empty = use zone_label)
    text_y_offset: float = -0.06  # axes-fraction offset from arrow y_frac
    text_fontsize: int = 11


@dataclass
class ZoneFill:
    """Visual properties of one zone (band + scatter points)."""

    band_color: str = ""
    band_alpha: float = 0.15
    point_color: str = ""
    zone_label: str = ""
    arrow: ZoneArrow = field(default_factory=ZoneArrow)


@dataclass
class ZoneGroup:
    """An ordered list of :class:`ZoneThreshold` + :class:`ZoneFill` rows.

    ``thresholds`` has length ``N`` (0 is allowed for a single-zone
    group).  ``zones`` has length ``N+1`` — index ``0`` is the
    low-NACD / contaminated side, index ``N`` is the clean side.

    ``name`` becomes the prefix on the band title in the Limit Lines
    tree. ``label_position`` decides which side of the figure the
    "Zone I / Zone II / ..." annotations render on; each group should
    pick a different position when overlaying several groups so the
    labels do not collide.

    ``draw_lambda`` / ``draw_freq`` gate whether the group's λ lines
    and their derived ``f`` partners are emitted into the
    :class:`DerivedLimitSet`. Both default to ``True`` so that out of
    the box each NACD threshold draws a vertical ``f`` marker *and* a
    λ hyperbola / λ-axis vertical line, matching the reference
    rendering. Users can turn either axis off per-group via the
    SingleGroupEditor toggles.
    """

    name: str = "Group"
    thresholds: List[ZoneThreshold] = field(default_factory=list)
    zones: List[ZoneFill] = field(default_factory=list)
    draw_lambda: bool = True
    draw_freq: bool = True
    label_position: LabelPosition = "top"
    palette_hint: str = ""

    # ── shape helpers ────────────────────────────────────────────
    def sorted_thresholds(self) -> List[ZoneThreshold]:
        return sorted(self.thresholds, key=lambda t: float(t.nacd))

    def normalised(self) -> "ZoneGroup":
        """Return a copy with ``zones`` resized to ``len(thresholds)+1``.

        Zones beyond the required count are dropped; missing zones are
        appended as default :class:`ZoneFill`.  Threshold order is
        preserved — the caller is responsible for sorting by NACD when
        used for classification.
        """
        target = len(self.thresholds) + 1
        zones = list(self.zones)
        if len(zones) > target:
            zones = zones[:target]
        while len(zones) < target:
            zones.append(ZoneFill())
        return ZoneGroup(
            name=self.name,
            thresholds=list(self.thresholds),
            zones=zones,
            draw_lambda=self.draw_lambda,
            draw_freq=self.draw_freq,
            label_position=self.label_position,
            palette_hint=self.palette_hint,
        )

    def zone_count(self) -> int:
        return len(self.thresholds) + 1 if (self.thresholds or self.zones) else 0

    def zone_name(self, zone_index: int) -> str:
        idx = max(0, min(int(zone_index), max(0, len(self.zones) - 1)))
        if 0 <= idx < len(self.zones) and self.zones[idx].zone_label:
            return self.zones[idx].zone_label
        return f"Zone {idx + 1}"


@dataclass
class NACDZoneSpec:
    """Complete specification for the NACD-Only view style."""

    style: ZoneStyle = "classic"
    groups: List[ZoneGroup] = field(default_factory=list)
    primary_group_index: int = 0

    # ── convenience ────────────────────────────────────────────────
    def is_classic(self) -> bool:
        return self.style == "classic"

    def primary_group(self) -> Optional[ZoneGroup]:
        if not self.groups:
            return None
        i = max(0, min(self.primary_group_index, len(self.groups) - 1))
        return self.groups[i]

    # ── persistence ───────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "style": self.style,
            "primary_group_index": int(self.primary_group_index),
            "groups": [_group_to_dict(g) for g in self.groups],
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "NACDZoneSpec":
        if not d:
            return cls()
        style = str(d.get("style", "classic"))
        if style not in _ALLOWED_STYLES:
            style = "classic"
        groups_raw = d.get("groups") or []
        groups = [_group_from_dict(g) for g in groups_raw if isinstance(g, dict)]
        try:
            primary = int(d.get("primary_group_index", 0))
        except (TypeError, ValueError):
            primary = 0
        return cls(
            style=style,  # type: ignore[arg-type]
            groups=groups,
            primary_group_index=primary,
        )


@dataclass
class ZoneBand:
    """One translucent rectangle to paint on an axis.

    * ``axis`` is ``"lambda"`` for ``axhspan`` on the V-vs-λ plot and
      ``"freq"`` for ``axvspan`` on the V-vs-f plot.
    * ``lo`` / ``hi`` are the bounds along the relevant axis. ``hi``
      can be ``+inf`` when the band is unbounded (top zone on λ axis,
      for instance); renderers clip to the visible axis limits.
    """

    axis: Literal["lambda", "freq"]
    group_index: int
    zone_index: int
    lo: float
    hi: float
    color: str
    alpha: float
    label: str
    label_position: LabelPosition


# ───────────────────────────────────────────────────────────────────
#  Serialisation helpers (inc. legacy "levels" shape)
# ───────────────────────────────────────────────────────────────────


def _threshold_to_dict(t: ZoneThreshold) -> dict:
    return {
        "nacd": float(t.nacd),
        "line_color": str(t.line_color or ""),
        "line_label": str(t.line_label or ""),
    }


def _threshold_from_dict(d: dict) -> ZoneThreshold:
    try:
        nacd = float(d.get("nacd", 0.0))
    except (TypeError, ValueError):
        nacd = 0.0
    return ZoneThreshold(
        nacd=nacd,
        line_color=str(d.get("line_color", "") or ""),
        line_label=str(d.get("line_label", "") or ""),
    )


def _arrow_to_dict(a: ZoneArrow) -> dict:
    return {
        "enabled": bool(a.enabled),
        "color": str(a.color or "#C00000"),
        "linewidth": float(a.linewidth),
        "y_frac": float(a.y_frac),
        "style": str(a.style or "<->"),
        "text": str(a.text or ""),
        "text_y_offset": float(a.text_y_offset),
        "text_fontsize": int(a.text_fontsize),
    }


def _arrow_from_dict(d: Optional[dict]) -> ZoneArrow:
    if not isinstance(d, dict):
        return ZoneArrow()
    try:
        lw = float(d.get("linewidth", 1.8))
    except (TypeError, ValueError):
        lw = 1.8
    try:
        yf = float(d.get("y_frac", 0.50))
    except (TypeError, ValueError):
        yf = 0.50
    try:
        dy = float(d.get("text_y_offset", -0.06))
    except (TypeError, ValueError):
        dy = -0.06
    try:
        fs = int(d.get("text_fontsize", 11))
    except (TypeError, ValueError):
        fs = 11
    return ZoneArrow(
        enabled=bool(d.get("enabled", False)),
        color=str(d.get("color", "#C00000") or "#C00000"),
        linewidth=lw,
        y_frac=max(0.02, min(0.98, yf)),
        style=str(d.get("style", "<->") or "<->"),
        text=str(d.get("text", "") or ""),
        text_y_offset=dy,
        text_fontsize=fs,
    )


def _zone_to_dict(z: ZoneFill) -> dict:
    return {
        "band_color": str(z.band_color or ""),
        "band_alpha": float(z.band_alpha),
        "point_color": str(z.point_color or ""),
        "zone_label": str(z.zone_label or ""),
        "arrow": _arrow_to_dict(z.arrow),
    }


def _zone_from_dict(d: dict) -> ZoneFill:
    try:
        alpha = float(d.get("band_alpha", 0.15))
    except (TypeError, ValueError):
        alpha = 0.15
    return ZoneFill(
        band_color=str(d.get("band_color", "") or ""),
        band_alpha=max(0.0, min(1.0, alpha)),
        point_color=str(d.get("point_color", "") or ""),
        zone_label=str(d.get("zone_label", "") or ""),
        arrow=_arrow_from_dict(d.get("arrow")),
    )


def _group_to_dict(g: ZoneGroup) -> dict:
    g = g.normalised()
    return {
        "name": g.name,
        "thresholds": [_threshold_to_dict(t) for t in g.thresholds],
        "zones": [_zone_to_dict(z) for z in g.zones],
        "draw_lambda": bool(g.draw_lambda),
        "draw_freq": bool(g.draw_freq),
        "label_position": g.label_position,
        "palette_hint": g.palette_hint,
    }


def _group_from_dict(d: dict) -> ZoneGroup:
    pos = str(d.get("label_position", "top") or "top")
    if pos not in _ALLOWED_POSITIONS:
        pos = "top"

    # Preferred shape: "thresholds" + "zones"
    thr_raw = d.get("thresholds")
    zones_raw = d.get("zones")
    thresholds: List[ZoneThreshold] = []
    zones: List[ZoneFill] = []
    if isinstance(thr_raw, list):
        thresholds = [
            _threshold_from_dict(x) for x in thr_raw if isinstance(x, dict)
        ]
    if isinstance(zones_raw, list):
        zones = [
            _zone_from_dict(x) for x in zones_raw if isinstance(x, dict)
        ]

    # ── Back-compat: legacy "levels" payload ───────────────────────
    # A "level" carried its own ``band_color`` / ``band_alpha`` /
    # ``zone_label``; treat those fills as the lower zones (0..N-1)
    # and the last level's fill as the clean top zone (N).  ``point_color``
    # did not exist — leave it empty so the tab falls back to the
    # classic scatter colors.
    if not thresholds and isinstance(d.get("levels"), list):
        levels_raw = [x for x in d["levels"] if isinstance(x, dict)]
        for lv in levels_raw:
            try:
                nacd = float(lv.get("nacd", 0.0))
            except (TypeError, ValueError):
                nacd = 0.0
            thresholds.append(ZoneThreshold(
                nacd=nacd,
                line_color=str(lv.get("line_color", "") or ""),
                line_label="",
            ))
        # Build N+1 zones: zi copies from levels[zi] when zi<N, else
        # from levels[-1].
        for zi in range(len(levels_raw) + 1):
            src = levels_raw[min(zi, len(levels_raw) - 1)]
            try:
                alpha = float(src.get("band_alpha", 0.15))
            except (TypeError, ValueError):
                alpha = 0.15
            zones.append(ZoneFill(
                band_color=str(src.get("band_color", "") or ""),
                band_alpha=max(0.0, min(1.0, alpha)),
                point_color="",
                zone_label=str(src.get("zone_label", "") or ""),
            ))

    g = ZoneGroup(
        name=str(d.get("name", "Group") or "Group"),
        thresholds=thresholds,
        zones=zones,
        # Default to True so legacy specs saved before the default
        # flip still draw λ lines after loading.
        draw_lambda=bool(d.get("draw_lambda", True)),
        draw_freq=bool(d.get("draw_freq", True)),
        label_position=pos,  # type: ignore[arg-type]
        palette_hint=str(d.get("palette_hint", "") or ""),
    )
    return g.normalised()


# ───────────────────────────────────────────────────────────────────
#  Public API: classifier
# ───────────────────────────────────────────────────────────────────


def classify_points_into_zones(
    nacd: Iterable[float],
    thresholds: Sequence[ZoneThreshold],
) -> np.ndarray:
    """Return the zone index in ``[0, len(thresholds)]`` for each pick.

    Thresholds are sorted internally by ``nacd`` ascending.  Points
    with ``NACD < thresholds[0].nacd`` go to zone 0 (the contaminated
    side), points with ``NACD >= thresholds[-1].nacd`` go to the top
    zone (``len(thresholds)``, the clean side).  An empty thresholds
    list classifies everything as zone 0.
    """
    arr = np.asarray(list(nacd), dtype=float)
    if arr.size == 0 or not thresholds:
        return np.zeros(arr.shape, dtype=int)
    th_sorted = np.sort(
        np.asarray([float(t.nacd) for t in thresholds], dtype=float)
    )
    zones = np.searchsorted(th_sorted, arr, side="right")
    return zones.astype(int)


# ───────────────────────────────────────────────────────────────────
#  Public API: λ / f guide lines  (projected onto DerivedLimitSet)
# ───────────────────────────────────────────────────────────────────


def spec_to_derived_limit_set(
    spec: NACDZoneSpec,
    x_bar: float,
    f_curve: Optional[np.ndarray] = None,
    v_curve: Optional[np.ndarray] = None,
) -> DerivedLimitSet:
    """Project every ``(group, threshold)`` into a :class:`DerivedLimitSet`.

    Each threshold contributes:

    * a ``λ`` line at ``λ_i = x_bar / NACD_i`` when
      ``group.draw_lambda`` is True (sourced ``user``);
    * a derived ``f`` line from ``V(f)/f == λ`` when
      ``group.draw_freq`` is True and a V(f) curve is supplied
      (sourced ``derived``; flagged invalid when the solve fails).

    Both lines carry the threshold's :meth:`ZoneThreshold.resolved_label`
    as ``custom_label`` so the DC Cut canvas / Limit Lines tree and
    the Report Studio renderer show "NACD = 1" instead of the generic
    "f_min = 7.69 Hz".

    Bands are numbered in stable order: all thresholds of group 0
    (sorted ascending by NACD), then group 1, and so on.
    """
    out = DerivedLimitSet()
    if x_bar <= 0 or not np.isfinite(x_bar):
        return out

    fc = (
        np.asarray(f_curve, float)
        if f_curve is not None else np.asarray([], float)
    )
    vc = (
        np.asarray(v_curve, float)
        if v_curve is not None else np.asarray([], float)
    )
    has_curve = fc.size >= 2 and vc.size >= 2

    bi = 0
    zone_meta: dict = {}
    # First pass: one "threshold" DerivedLine band per threshold.
    for gi, group in enumerate(spec.groups):
        for zi, thr in enumerate(group.sorted_thresholds()):
            if thr.nacd <= 0 or not np.isfinite(thr.nacd):
                continue
            lam = float(x_bar) / float(thr.nacd)
            if not np.isfinite(lam) or lam <= 0:
                continue
            label_text = thr.resolved_label()

            if group.draw_lambda:
                out.lines.append(DerivedLine(
                    band_index=bi, kind="lambda", role="max",
                    value=float(lam), source="user", valid=True,
                    custom_label=label_text,
                ))

            if group.draw_freq:
                if has_curve:
                    f_val, ok = _solve_f_for_lambda(fc, vc, lam)
                    out.lines.append(DerivedLine(
                        band_index=bi, kind="freq", role="min",
                        value=float(f_val), source="derived", valid=ok,
                        derived_from=float(lam),
                        custom_label=label_text,
                    ))
                else:
                    out.lines.append(DerivedLine(
                        band_index=bi, kind="freq", role="min",
                        value=0.0, source="derived", valid=False,
                        derived_from=float(lam),
                        custom_label=label_text,
                    ))

            zone_meta[bi] = {
                "group_index": gi,
                "threshold_index": zi,
                "group_name": group.name,
                "threshold_label": label_text,
            }
            bi += 1

    # Second pass: one pseudo-band per group containing a zone
    # "label" line for each zone (N+1 zones for N thresholds).  The
    # Limit Lines tab renders these flat (no λ/f subgroups) so the
    # user can toggle and recolor each zone individually.
    zone_band_base = ZONE_BAND_INDEX_OFFSET
    for gi, group in enumerate(spec.groups):
        g = group.normalised()
        if not g.zones:
            continue
        zb = zone_band_base + gi
        for zi, z in enumerate(g.zones):
            # Zone N+1 only materialises when a threshold exists — a
            # group without thresholds still has one zone (the single
            # tint), but more zones without thresholds have no
            # geometric meaning.
            if not g.thresholds and zi > 0:
                break
            zone_name = g.zone_name(zi)
            out.lines.append(DerivedLine(
                band_index=zb,
                kind="zone",
                role="label",
                value=float(zi),
                source="derived",
                valid=True,
                derived_from=float(gi),
                custom_label=zone_name,
            ))
            zone_meta[zb] = {
                "group_index": gi,
                "group_name": g.name,
                "kind": "zone_group",
            }

    # Attach as a lightweight extension attribute (won't break
    # serialisers that only read ``lines``).
    setattr(out, "zone_meta", zone_meta)
    return out


# ───────────────────────────────────────────────────────────────────
#  Public API: band tints
# ───────────────────────────────────────────────────────────────────


def spec_to_zone_bands(
    spec: NACDZoneSpec,
    x_bar: float,
    *,
    f_curve: Optional[np.ndarray] = None,
    v_curve: Optional[np.ndarray] = None,
    f_axis_min: float = 0.0,
    f_axis_max: float = float("inf"),
    lambda_axis_min: float = 0.0,
    lambda_axis_max: float = float("inf"),
) -> List[ZoneBand]:
    """Derive the flat ``[ZoneBand]`` list the renderer paints.

    For every group the thresholds are sorted ascending by NACD which,
    since ``λ = x_bar / NACD``, means descending by λ.  That means the
    contaminated end of the picture is at *large* λ and *small* f,
    matching the picture the user shared (Zone II / "Red" on the
    short-f / long-λ side, Zone I / "Blue" on the long-f / short-λ
    side).
    """
    bands: List[ZoneBand] = []
    if x_bar <= 0 or not np.isfinite(x_bar):
        return bands

    fc = (
        np.asarray(f_curve, float)
        if f_curve is not None else np.asarray([], float)
    )
    vc = (
        np.asarray(v_curve, float)
        if v_curve is not None else np.asarray([], float)
    )
    has_curve = fc.size >= 2 and vc.size >= 2

    for gi, group in enumerate(spec.groups):
        group = group.normalised()
        thresholds = group.sorted_thresholds()
        if not thresholds:
            # Single zone: still let the renderer paint a full-axis
            # band when zones[0] has a color set (useful for drawing
            # only a background tint without any dividers).
            if group.zones and group.zones[0].band_color:
                z = group.zones[0]
                if group.draw_lambda:
                    bands.append(ZoneBand(
                        axis="lambda", group_index=gi, zone_index=0,
                        lo=max(0.0, lambda_axis_min),
                        hi=(
                            lambda_axis_max
                            if np.isfinite(lambda_axis_max)
                            else float("inf")
                        ),
                        color=z.band_color, alpha=z.band_alpha,
                        label=group.zone_name(0),
                        label_position=group.label_position,
                    ))
                if group.draw_freq:
                    bands.append(ZoneBand(
                        axis="freq", group_index=gi, zone_index=0,
                        lo=max(0.0, f_axis_min),
                        hi=(
                            f_axis_max
                            if np.isfinite(f_axis_max)
                            else float("inf")
                        ),
                        color=z.band_color, alpha=z.band_alpha,
                        label=group.zone_name(0),
                        label_position=group.label_position,
                    ))
            continue

        # Zone visuals — index 0 is the contaminated / low-NACD side.
        zones = list(group.zones)  # len == N+1 after normalised()

        # ── Wavelength bands (horizontal stripes on V-vs-λ plot) ──
        # Zone 0 (contaminated, largest λ) → [lam_boundaries[0], +inf)
        # Zone k (1..N-1)                 → [lam_boundaries[k], lam_boundaries[k-1])
        # Zone N (cleanest, smallest λ)   → [0, lam_boundaries[-1])
        if group.draw_lambda:
            lam_boundaries = [
                float(x_bar) / float(t.nacd) for t in thresholds
            ]
            for zi in range(len(thresholds) + 1):
                if zi == 0:
                    lo = lam_boundaries[0]
                    hi = (
                        lambda_axis_max
                        if np.isfinite(lambda_axis_max)
                        else float("inf")
                    )
                elif zi == len(thresholds):
                    lo = max(0.0, lambda_axis_min)
                    hi = lam_boundaries[-1]
                else:
                    lo = lam_boundaries[zi]
                    hi = lam_boundaries[zi - 1]
                if hi <= lo:
                    continue
                z = zones[zi]
                if not z.band_color:
                    continue
                bands.append(ZoneBand(
                    axis="lambda",
                    group_index=gi,
                    zone_index=zi,
                    lo=float(lo),
                    hi=float(hi),
                    color=z.band_color,
                    alpha=z.band_alpha,
                    label=group.zone_name(zi),
                    label_position=group.label_position,
                ))

        # ── Frequency bands (vertical stripes on V-vs-f plot) ──
        if group.draw_freq:
            # Resolve f for each threshold's λ; when we have no curve
            # (single-offset plots skip V(f)), we still paint bands but
            # clamp the dividers to the viewport so the user at least
            # gets the correct left / right shading.
            f_boundaries: List[float] = []
            valid: List[bool] = []
            if has_curve:
                for thr in thresholds:
                    lam = float(x_bar) / float(thr.nacd)
                    f_val, ok = _solve_f_for_lambda(fc, vc, lam)
                    f_boundaries.append(float(f_val))
                    valid.append(bool(ok))

            if not has_curve or not all(valid):
                # Cannot derive boundaries robustly — skip this group's
                # f bands. (Limit Lines still show individual lines that
                # are flagged valid/invalid independently.)
                continue

            # Because larger NACD ↔ smaller λ ↔ larger f for a monotone
            # V(f)/f profile, f_boundaries is ascending.
            # Zone 0 (contaminated, low f)  → [f_axis_min, f[0])
            # Zone k (1..N-1)              → [f[k-1], f[k])
            # Zone N (clean, high f)       → [f[-1], f_axis_max]
            for zi in range(len(thresholds) + 1):
                if zi == 0:
                    lo = max(0.0, f_axis_min)
                    hi = f_boundaries[0]
                elif zi == len(thresholds):
                    lo = f_boundaries[-1]
                    hi = (
                        f_axis_max
                        if np.isfinite(f_axis_max)
                        else float("inf")
                    )
                else:
                    lo = f_boundaries[zi - 1]
                    hi = f_boundaries[zi]
                if hi <= lo:
                    continue
                z = zones[zi]
                if not z.band_color:
                    continue
                bands.append(ZoneBand(
                    axis="freq",
                    group_index=gi,
                    zone_index=zi,
                    lo=float(lo),
                    hi=float(hi),
                    color=z.band_color,
                    alpha=z.band_alpha,
                    label=group.zone_name(zi),
                    label_position=group.label_position,
                ))

    return bands


# ───────────────────────────────────────────────────────────────────
#  Public API: validation
# ───────────────────────────────────────────────────────────────────


def validate_spec(spec: NACDZoneSpec) -> List[str]:
    """Return a list of human-readable problems with *spec*.

    Empty list == spec is valid.  Meant for calling before Run so the
    UI can surface a status message.
    """
    errs: List[str] = []
    if spec.style not in _ALLOWED_STYLES:
        errs.append(f"Unknown view style: {spec.style!r}")
    if spec.style == "classic":
        return errs
    if not spec.groups:
        errs.append("At least one zone group is required for this style.")
        return errs
    if spec.style == "multi_zone" and len(spec.groups) > 1:
        errs.append(
            "Multi-zone style uses a single group; extra groups are ignored."
        )
    for gi, g in enumerate(spec.groups):
        vals = [t.nacd for t in g.thresholds]
        if any(not np.isfinite(v) or v <= 0 for v in vals):
            errs.append(
                f"Group {gi + 1} ({g.name}) has invalid "
                "(non-positive / non-finite) NACD values."
            )
        if len(set(vals)) != len(vals):
            errs.append(
                f"Group {gi + 1} ({g.name}) has duplicate NACD values."
            )
        if g.label_position not in _ALLOWED_POSITIONS:
            errs.append(
                f"Group {gi + 1} ({g.name}) has invalid label_position "
                f"{g.label_position!r}."
            )
        # Shape check: normalise enforces len(zones) == len(thresholds)+1,
        # but we warn when the raw dataclass diverged (UI wiring bug).
        if g.zones and len(g.zones) != len(g.thresholds) + 1:
            errs.append(
                f"Group {gi + 1} ({g.name}) has "
                f"{len(g.zones)} zones for {len(g.thresholds)} thresholds; "
                f"expected {len(g.thresholds) + 1}."
            )
    return errs


__all__ = [
    "ZoneStyle",
    "LabelPosition",
    "ZoneThreshold",
    "ZoneFill",
    "ZoneArrow",
    "ZoneGroup",
    "NACDZoneSpec",
    "ZoneBand",
    "classify_points_into_zones",
    "spec_to_derived_limit_set",
    "spec_to_zone_bands",
    "validate_spec",
]
