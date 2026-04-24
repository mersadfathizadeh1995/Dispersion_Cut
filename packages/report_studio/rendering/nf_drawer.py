"""Near-field (NACD-Only) overlays: severity scatter + limit lines."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Dict, List, Optional

import matplotlib as mpl
import numpy as np
from matplotlib.transforms import blended_transform_factory

from ..core.models import NFAnalysis, NFLambdaLine, NFLine, OffsetCurve
from . import lambda_drawer
from .label_format import fmt_freq, fmt_lambda
from .style import StyleConfig


def _active_font_family() -> Optional[str]:
    """Return the active matplotlib font family so text labels can
    honour the global typography (request 1).  Falls back to ``None``
    when rcParams is empty/invalid which lets matplotlib use its own
    default.
    """
    try:
        fam = mpl.rcParams.get("font.family", None)
        if isinstance(fam, (list, tuple)):
            fam = fam[0] if fam else None
        if isinstance(fam, str) and fam:
            return fam
    except Exception:
        return None
    return None

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..core.models import OffsetCurve as OffsetCurveT


@contextmanager
def _preserve_limits(*axes):
    """Snapshot ``(xlim, ylim, autoscale_on_*)`` for every axes and
    restore on exit.  Prevents λ-hyperbola padding from blowing up
    the y-axis when matplotlib autoscales on a fresh or sparsely
    populated axes.  See :func:`_draw_single_limit` in
    :mod:`dc_cut.gui.widgets.nf_limit_lines` for the DC-Cut twin.
    """
    saved: list = []
    for ax in axes:
        if ax is None:
            continue
        try:
            saved.append((
                ax,
                ax.get_xlim(),
                ax.get_ylim(),
                ax.get_autoscalex_on(),
                ax.get_autoscaley_on(),
            ))
        except Exception:
            continue
    try:
        yield
    finally:
        for ax, xlim, ylim, ax_on, ay_on in saved:
            try:
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
                ax.set_autoscalex_on(ax_on)
                ax.set_autoscaley_on(ay_on)
            except Exception:
                pass


def _zone_thresholds_from_spec(spec) -> Optional[list]:
    """Return the sorted ``ZoneThreshold`` list for the first
    non-empty group of ``spec``, or ``None`` when ``spec`` has no
    thresholds.
    """
    if spec is None:
        return None
    groups = list(getattr(spec, "groups", None) or [])
    for grp in groups:
        ths = list(getattr(grp, "thresholds", None) or [])
        if ths:
            try:
                return sorted(ths, key=lambda t: float(t.nacd))
            except Exception:
                return ths
    return None


def _zone_point_colors_from_spec(spec) -> Optional[list]:
    """Return the list of per-zone point colours (index = zone index)
    for the first non-empty group.

    ``point_color`` takes precedence; when a zone has no explicit
    ``point_color`` we fall back to its ``band_color`` so the scatter
    initially follows the band shading the user already picked in
    DC Cut's Zones table (where the "Point color" column is often
    left untouched).  Returns ``None`` when ``spec`` is missing or
    when *no* zone carries either colour — callers then fall back
    to the flat severity palette.
    """
    if spec is None:
        return None
    groups = list(getattr(spec, "groups", None) or [])
    for grp in groups:
        zones = list(getattr(grp, "zones", None) or [])
        if not zones:
            continue
        colors = []
        any_color = False
        for z in zones:
            pc = (getattr(z, "point_color", "") or "").strip()
            bc = (getattr(z, "band_color", "") or "").strip()
            chosen = pc or bc
            if chosen:
                any_color = True
            colors.append(chosen if chosen else None)
        if any_color:
            return colors
        return None
    return None


def _scatter_colors_for_points(r, mask, zone_colors, zone_thresholds, fallback):
    """Build a per-point colour array for contaminated scatter.

    Falls back to the scalar ``fallback`` string when per-zone colours
    are not configured or cannot be resolved.
    """
    if zone_colors is None or zone_thresholds is None:
        return fallback
    try:
        try:
            from dc_cut.core.processing.nearfield.nacd_zones import (
                classify_points_into_zones,
            )
        except ImportError:
            from core.processing.nearfield.nacd_zones import (
                classify_points_into_zones,
            )
    except Exception:
        return fallback
    try:
        nacd = np.asarray(getattr(r, "nacd", None), dtype=float)
    except Exception:
        return fallback
    if nacd.size == 0:
        return fallback
    try:
        m = np.asarray(mask, dtype=bool)
        nacd_sel = nacd[m] if m.shape == nacd.shape else nacd
    except Exception:
        nacd_sel = nacd
    try:
        zidx = classify_points_into_zones(nacd_sel, zone_thresholds)
    except Exception:
        return fallback
    out = []
    n_zones = len(zone_colors)
    for zi in zidx:
        zi_i = int(zi)
        if 0 <= zi_i < n_zones and zone_colors[zi_i]:
            out.append(zone_colors[zi_i])
        else:
            out.append(fallback)
    return out


def _freq_line_label_text(ln: "NFLine", decimals: int = 1) -> str:
    """Default canvas label for a frequency NF guide line.

    Honors ``custom_label`` when the user explicitly typed one; otherwise
    formats the value with the typography-driven decimal precision so the
    canvas label always tracks the Global decimal setting (auto-baked
    ``display_label`` is only used in the data tree).
    """
    custom = (ln.custom_label or "").strip()
    if custom:
        return custom
    return f"f = {fmt_freq(ln.value, decimals)} Hz"


def _freq_line_bbox(ln: "NFLine") -> Optional[dict]:
    if not bool(getattr(ln, "label_box", False)):
        return None
    pad = float(max(getattr(ln, "label_box_pad", 0.0) or 0.0, 0.0))
    scale = float(getattr(ln, "label_scale", 1.0) or 1.0)
    if scale <= 0:
        scale = 1.0
    pad *= scale
    return dict(
        boxstyle=f"round,pad={pad / 10.0 + 0.15}",
        facecolor=ln.label_box_facecolor,
        edgecolor=ln.label_box_edgecolor,
        alpha=float(np.clip(ln.label_box_alpha, 0.0, 1.0)),
        linewidth=0.5,
    )


def _draw_freq_line(
    ax: "Axes",
    ln: "NFLine",
    style: StyleConfig,
    *,
    zorder: int,
    legend_label: Optional[str] = None,
) -> None:
    """Draw a vertical frequency guide line + optional label/box."""
    line_label = legend_label if legend_label else "_nolegend_"
    ax.axvline(
        float(ln.value),
        color=ln.color,
        linestyle=ln.line_style,
        lw=ln.line_width,
        alpha=ln.alpha,
        zorder=zorder,
        label=line_label,
    )
    if not bool(getattr(ln, "show_label", True)):
        return
    txt = _freq_line_label_text(ln, int(getattr(style, "freq_decimals", 1)))
    if not txt:
        return
    try:
        t = float(ln.label_position)
    except (TypeError, ValueError):
        t = 0.55
    t = float(np.clip(t, 0.02, 0.98))
    fs_default = max(8, int(style.tick_label_size))
    fs = int(getattr(ln, "label_fontsize", 0) or 0) or fs_default
    scale = float(getattr(ln, "label_scale", 1.0) or 1.0)
    if scale <= 0:
        scale = 1.0
    fs = max(1, int(round(fs * scale)))
    rotation = 90 if str(getattr(ln, "label_rotation_mode", "along")) == "along" else 0
    bbox = _freq_line_bbox(ln)
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    ax.text(
        float(ln.value),
        t,
        f" {txt} ",
        fontsize=fs,
        color=ln.color,
        alpha=0.95,
        rotation=rotation,
        ha="left",
        va="center",
        zorder=zorder + 1,
        fontweight="bold",
        transform=trans,
        bbox=bbox,
    )
    # When the line carries a NACD-style ``custom_label`` (e.g.
    # "NACD = 1"), mirror the actual frequency value on the OPPOSITE
    # side of the vertical line so the user can read both the
    # criterion and the resulting f at a glance.
    custom = (ln.custom_label or "").strip()
    if custom and bool(getattr(ln, "show_value_label", True)):
        side = str(getattr(ln, "value_label_side", "right") or "right").lower()
        try:
            offset = float(getattr(ln, "value_label_offset", 0.0) or 0.0)
        except (TypeError, ValueError):
            offset = 0.0
        mirror_text = f" f = {fmt_freq(ln.value, int(getattr(style, 'freq_decimals', 1)))} Hz "
        mirror_t = float(np.clip(t + offset, 0.02, 0.98))
        if side in ("right", "left"):
            # Opposite side of the primary label on the same row.
            # primary uses ha="left" \u2192 sits right of the line; so
            # side="right" (default) draws on the LEFT (ha="right").
            mirror_ha = "right" if side == "right" else "left"
            mirror_va = "center"
            mirror_rot = rotation
        elif side == "above":
            mirror_ha = "left"
            mirror_va = "center"
            mirror_t = float(np.clip(t + (offset or 0.08), 0.02, 0.98))
            mirror_rot = rotation
        else:  # "below"
            mirror_ha = "left"
            mirror_va = "center"
            mirror_t = float(np.clip(t - (offset or 0.08), 0.02, 0.98))
            mirror_rot = rotation
        ax.text(
            float(ln.value),
            mirror_t,
            mirror_text,
            fontsize=fs,
            color=ln.color,
            alpha=0.95,
            rotation=mirror_rot,
            ha=mirror_ha,
            va=mirror_va,
            zorder=zorder + 1,
            fontweight="bold",
            transform=trans,
            bbox=bbox,
        )


def _curve_for_result(
    curves: List["OffsetCurveT"], r
) -> Optional["OffsetCurveT"]:
    """Match dispersion curve to per-offset NF result."""
    try:
        from dc_cut.core.processing.wavelength_lines import (
            parse_source_offset_from_label,
        )
    except ImportError:
        parse_source_offset_from_label = None  # type: ignore

    for c in curves:
        if not c.visible:
            continue
        if c.name == r.label:
            return c
        if r.source_offset is not None and parse_source_offset_from_label:
            cso = parse_source_offset_from_label(c.name)
            if cso is not None and abs(float(cso) - float(r.source_offset)) < 0.05:
                return c
    for c in curves:
        if c.name == r.label:
            return c
    return None


def _align_mask_to_curve_f(f_r: np.ndarray, mask: np.ndarray, curve: OffsetCurve):
    """Map mask sampled on *f_r* to curve.frequency (nearest neighbour)."""
    f_c = np.asarray(curve.frequency, dtype=float)
    m = np.asarray(mask, dtype=bool)
    if f_c.size == 0:
        return m
    if f_r.size == m.size and f_r.size == f_c.size and np.allclose(f_r, f_c):
        return m
    if f_r.size != m.size:
        return m
    out = np.zeros(len(f_c), dtype=bool)
    for i, fc in enumerate(f_c):
        j = int(np.argmin(np.abs(f_r - fc)))
        if 0 <= j < len(m):
            out[i] = bool(m[j])
    return out


def _draw_zone_bands_and_labels(
    ax: "Axes",
    spec: dict,
    x_domain: str,
    nf: NFAnalysis,
) -> None:
    """Paint multi-zone translucent bands + zone labels on a single axes.

    Report Studio figures use only one axes per NF subplot (either ``f``
    or ``λ`` on the x-axis, ``V`` on the y-axis), so we can't reuse the
    dual-axes ``draw_zone_bands`` helper from DC Cut directly.  We
    translate the :class:`NACDZoneSpec` dict into ``axvspan`` rectangles
    + text labels aligned to the current x-domain.  Unrelated bands
    (e.g. frequency bands on a wavelength subplot) are silently skipped.
    """
    try:
        from dc_cut.core.processing.nearfield.nacd_zones import (
            NACDZoneSpec, spec_to_zone_bands,
        )
    except Exception:
        return

    if not isinstance(spec, dict) or not spec.get("groups"):
        return
    try:
        zs = NACDZoneSpec.from_dict(spec)
    except Exception:
        return
    if zs.style == "classic" or not zs.groups:
        return

    # Derive a representative ``x_bar`` from the NFAnalysis.  When the
    # sidecar / PKL round-tripped with per-offset results, ``per_offset``
    # carries the same ``x_bar`` DC Cut used when building the spec, so
    # the zone boundaries reproduce byte-for-byte.  Otherwise fall back
    # to the first ``lambda_max`` it can find (``x_bar = λ_max * NACD``
    # when NACD is the threshold) or a benign default.
    x_bar = 0.0
    for r in getattr(nf, "per_offset", []) or []:
        xb = float(getattr(r, "x_bar", 0.0) or 0.0)
        if np.isfinite(xb) and xb > 0:
            x_bar = xb
            break
    if x_bar <= 0:
        for r in getattr(nf, "per_offset", []) or []:
            lm = float(getattr(r, "lambda_max", 0.0) or 0.0)
            if np.isfinite(lm) and lm > 0:
                x_bar = lm  # NACD=1 → x_bar == λ_max
                break
    if x_bar <= 0:
        x_bar = 1.0

    x_lim = ax.get_xlim()
    y_lim = ax.get_ylim()
    axis_want = "freq" if x_domain == "frequency" else "lambda"
    # Pick a V(f) curve so the adapter can solve f-boundaries for each
    # λ level.  Using the first per-offset result works because all
    # offsets share the same V(f) sampling upstream.
    f_curve = None
    v_curve = None
    for r in getattr(nf, "per_offset", []) or []:
        fc = np.asarray(getattr(r, "f", []), float)
        vc = np.asarray(getattr(r, "v", []), float)
        if fc.size >= 2 and vc.size >= 2:
            f_curve, v_curve = fc, vc
            break
    if axis_want == "freq":
        bands = spec_to_zone_bands(
            zs, x_bar,
            f_curve=f_curve, v_curve=v_curve,
            f_axis_min=float(x_lim[0]), f_axis_max=float(x_lim[1]),
        )
    else:
        bands = spec_to_zone_bands(
            zs, x_bar,
            f_curve=f_curve, v_curve=v_curve,
            lambda_axis_min=float(x_lim[0]), lambda_axis_max=float(x_lim[1]),
        )

    edge_groups: dict = {"top": [], "bottom": [], "left": [], "right": []}
    seen_pos: dict = {}
    for b in bands:
        gi = int(getattr(b, "group_index", 0))
        pos = str(getattr(b, "label_position", "top"))
        if pos not in edge_groups:
            pos = "top"
        if gi not in seen_pos:
            seen_pos[gi] = pos
            if gi not in edge_groups[pos]:
                edge_groups[pos].append(gi)
    group_row: dict = {}
    for pos, gids in edge_groups.items():
        for row, gi in enumerate(gids):
            group_row[gi] = row

    drawn_labels: set = set()
    # Build a (gi, zi, axis) → NFZoneBand lookup for layer overrides.
    band_ov: dict = {}
    for ob in getattr(nf, "zone_bands", None) or []:
        band_ov[(int(ob.group_index), int(ob.zone_index),
                 str(ob.axis))] = ob
    # Build a (gi, axis) → NFZoneSpan lookup and compute, per group, the
    # lo/hi extremes so we can identify the leftmost/rightmost bands.
    span_ov: dict = {}
    for sp in getattr(nf, "zone_spans", None) or []:
        span_ov[(int(sp.group_index), str(sp.axis))] = sp
    group_extents: dict = {}
    for b in bands:
        if getattr(b, "axis", "lambda") != axis_want:
            continue
        gi_b = int(getattr(b, "group_index", 0))
        lo_b = float(getattr(b, "lo", 0.0))
        hi_b = float(getattr(b, "hi", 0.0))
        if hi_b <= lo_b or not np.isfinite(lo_b) or not np.isfinite(hi_b):
            continue
        prev = group_extents.get(gi_b)
        if prev is None:
            group_extents[gi_b] = [lo_b, hi_b]
        else:
            if lo_b < prev[0]:
                prev[0] = lo_b
            if hi_b > prev[1]:
                prev[1] = hi_b
    font_fam = _active_font_family()
    for b in bands:
        if getattr(b, "axis", "lambda") != axis_want:
            continue
        gi = int(getattr(b, "group_index", 0))
        zi = int(getattr(b, "zone_index", 0))
        ov = band_ov.get((gi, zi, axis_want))
        if ov is not None and not bool(getattr(ov, "visible", True)):
            continue
        color = getattr(b, "color", "") or ""
        alpha = float(getattr(b, "alpha", 0.15) or 0.15)
        if ov is not None:
            if ov.band_color:
                color = ov.band_color
            alpha = float(getattr(ov, "band_alpha", alpha) or alpha)
        lo = float(getattr(b, "lo", 0.0))
        hi = float(getattr(b, "hi", 0.0))
        if hi <= lo:
            continue
        if not np.isfinite(hi):
            hi = float(x_lim[1])
        # Request 6 — outer band extension: push the leftmost / rightmost
        # band's edge out to the axis limit so the shading continues
        # beyond the dispersion curve's data range.
        sp = span_ov.get((gi, axis_want))
        ext = group_extents.get(gi)
        if sp is not None and ext is not None:
            try:
                if bool(getattr(sp, "extend_left_to_axis", False)) \
                        and abs(lo - ext[0]) < 1e-9:
                    lo = float(x_lim[0])
                if bool(getattr(sp, "extend_right_to_axis", False)) \
                        and abs(hi - ext[1]) < 1e-9:
                    hi = float(x_lim[1])
            except Exception:
                pass
        if color:
            ax.axvspan(
                lo, hi, facecolor=color, alpha=alpha,
                linewidth=0, zorder=0.5, label="_nf_zone_band",
            )

        pos_b = str(getattr(b, "label_position", "top"))
        if ov is not None:
            pos_b = str(getattr(ov, "label_position", pos_b) or pos_b)
        pos = pos_b
        if pos not in edge_groups:
            pos = "top"
        key = (gi, zi, pos)
        if key in drawn_labels:
            continue
        drawn_labels.add(key)

        if ov is not None and not bool(getattr(ov, "label_visible", True)):
            continue

        label = str(getattr(b, "label", "") or f"Zone {zi + 1}")
        if ov is not None and ov.label:
            label = ov.label
        row = int(group_row.get(gi, 0))
        row_offset = 0.04 * row
        if ov is not None:
            row_offset += float(getattr(ov, "label_row_offset", 0.0) or 0.0)
        label_fs = 8
        if ov is not None:
            label_fs = int(getattr(ov, "label_fontsize", label_fs) or label_fs)
        label_color = "black"
        if ov is not None and getattr(ov, "label_color", ""):
            label_color = ov.label_color
        # Per-label ha/va override (request 1).
        lbl_ha = "center"
        if ov is not None:
            lbl_ha = str(getattr(ov, "label_ha", lbl_ha) or lbl_ha)
        text_kwargs = {}
        if font_fam:
            text_kwargs["fontfamily"] = font_fam
        x_mid = 0.5 * (lo + hi)
        if pos == "top":
            y_frac = 1.0 - row_offset
            va = "top"
        elif pos == "bottom":
            y_frac = 0.02 + row_offset
            va = "bottom"
        elif pos == "left":
            # Sideways labels — pin to the left spine and use band
            # midpoint as the y-coordinate.
            y_mid = 0.5 * (y_lim[0] + y_lim[1])
            ax.text(
                0.02 + row_offset, y_mid, label,
                transform=ax.get_yaxis_transform(),
                fontsize=label_fs, fontweight="bold",
                color=label_color,
                ha="left", va="center", rotation=90,
                zorder=9, label="_nf_zone_label",
                bbox=dict(facecolor="white", edgecolor="none",
                          alpha=0.6, pad=1.0),
                **text_kwargs,
            )
            continue
        else:  # right
            y_mid = 0.5 * (y_lim[0] + y_lim[1])
            ax.text(
                1.0 - row_offset, y_mid, label,
                transform=ax.get_yaxis_transform(),
                fontsize=label_fs, fontweight="bold",
                color=label_color,
                ha="right", va="center", rotation=90,
                zorder=9, label="_nf_zone_label",
                bbox=dict(facecolor="white", edgecolor="none",
                          alpha=0.6, pad=1.0),
                **text_kwargs,
            )
            continue

        ax.text(
            x_mid, y_frac, label,
            transform=ax.get_xaxis_transform(),
            fontsize=label_fs, fontweight="bold",
            color=label_color,
            ha=lbl_ha, va=va,
            zorder=9, label="_nf_zone_label",
            bbox=dict(facecolor="white", edgecolor="none",
                      alpha=0.6, pad=1.0),
            **text_kwargs,
        )

        # Request 1 — horizontal <-> arrow beneath the top/bottom
        # zone label spanning the band.
        if ov is not None and bool(getattr(ov, "arrow_below_label", False)):
            try:
                gap = float(getattr(ov, "arrow_below_gap", 0.03) or 0.03)
            except (TypeError, ValueError):
                gap = 0.03
            lw = float(getattr(ov, "arrow_below_linewidth", 1.4) or 1.4)
            arrow_color = str(getattr(ov, "arrow_below_color", "") or "") \
                or label_color
            _draw_zone_label_arrow(
                ax, lo, hi,
                y_frac - gap if pos == "top" else y_frac + gap,
                color=arrow_color, linewidth=lw,
            )

    # ── v2: per-zone double-headed arrows (enabled=False on v1) ────
    _draw_zone_arrows(ax, zs, bands, axis_want, x_lim, nf=nf)


def _draw_zone_label_arrow(ax, lo: float, hi: float, y_frac: float,
                           *, color: str, linewidth: float) -> None:
    """Draw a horizontal ``<->`` arrow spanning ``[lo, hi]`` at
    ``y_frac`` (axes-frac y, data x).  Used to emphasise a zone band
    directly under its top/bottom label (request 1).
    """
    try:
        from matplotlib.patches import FancyArrowPatch
    except Exception:
        return
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    arr = FancyArrowPatch(
        (float(lo), float(y_frac)), (float(hi), float(y_frac)),
        arrowstyle="<->", mutation_scale=12,
        color=color or "black", linewidth=float(linewidth),
        transform=trans, zorder=9.5, label="_nf_zone_label_arrow",
    )
    ax.add_patch(arr)


def _draw_zone_arrows(ax, zs, bands, axis_want, x_lim, nf=None):
    """Render the optional ``ZoneArrow`` per zone as a FancyArrowPatch.

    Arrows span the band's ``[lo, hi]`` along the x-axis and sit at a
    fixed axes-fraction y-coordinate. A centred text label is drawn
    just below (``text_y_offset``). When ``arrow.text`` is empty the
    band label is reused.

    When ``nf`` is provided and carries ``zone_arrows`` overrides the
    renderer reads those first (``visible``/``enabled``/colour/
    position/text) — the spec's ``ZoneArrow`` is only consulted as a
    fallback.
    """
    try:
        from matplotlib.patches import FancyArrowPatch
        from matplotlib.transforms import blended_transform_factory
    except Exception:
        return

    arr_ov: dict = {}
    if nf is not None:
        for oa in getattr(nf, "zone_arrows", None) or []:
            arr_ov[(int(oa.group_index), int(oa.zone_index),
                    str(oa.axis))] = oa

    for b in bands:
        if getattr(b, "axis", "lambda") != axis_want:
            continue
        gi = int(getattr(b, "group_index", 0))
        zi = int(getattr(b, "zone_index", 0))
        ov = arr_ov.get((gi, zi, axis_want))
        if ov is not None and not bool(getattr(ov, "visible", True)):
            continue
        # Resolve enable: override wins; otherwise fall back to spec.
        if ov is not None:
            enabled = bool(getattr(ov, "enabled", False))
        else:
            try:
                enabled = bool(getattr(zs.groups[gi].zones[zi].arrow,
                                       "enabled", False))
            except (IndexError, AttributeError):
                enabled = False
        if not enabled:
            continue
        try:
            zone = zs.groups[gi].zones[zi]
        except (IndexError, AttributeError):
            zone = None
        spec_arrow = getattr(zone, "arrow", None) if zone is not None else None

        def _field(name, default):
            """Prefer override, else spec arrow, else default."""
            if ov is not None:
                v = getattr(ov, name, None)
                if v is not None and v != "":
                    return v
            if spec_arrow is not None:
                v = getattr(spec_arrow, name, None)
                if v is not None and v != "":
                    return v
            return default

        lo = float(getattr(b, "lo", 0.0))
        hi = float(getattr(b, "hi", 0.0))
        if hi <= lo or not np.isfinite(hi):
            # Clamp unbounded right edge to axes limit so the arrow
            # still lands inside the frame.
            hi = float(x_lim[1])
        if hi <= lo:
            continue
        # Data x, axes-fraction y
        trans = blended_transform_factory(ax.transData, ax.transAxes)
        try:
            y_frac = float(np.clip(float(_field("y_frac", 0.5)), 0.02, 0.98))
        except (TypeError, ValueError):
            y_frac = 0.5
        color = str(_field("color", "#C00000") or "#C00000")
        try:
            lw = float(_field("linewidth", 1.8) or 1.8)
        except (TypeError, ValueError):
            lw = 1.8
        style = str(_field("style", "<->") or "<->")
        try:
            patch = FancyArrowPatch(
                (lo, y_frac), (hi, y_frac),
                transform=trans,
                arrowstyle=style,
                mutation_scale=14.0,
                color=color,
                linewidth=lw,
                zorder=9,
                clip_on=True,
            )
            ax.add_patch(patch)
        except Exception:
            continue
        # Text just below the arrow midpoint.
        text = str(_field("text", "") or "").strip()
        if not text:
            text = str(getattr(b, "label", "") or "")
        if text:
            try:
                dy = float(_field("text_y_offset", -0.06))
                fs = int(_field("text_fontsize", 11))
            except (TypeError, ValueError):
                dy, fs = -0.06, 11
            ty = float(np.clip(y_frac + dy, 0.01, 0.99))
            ax.text(
                0.5 * (lo + hi), ty, text,
                transform=trans,
                fontsize=fs, fontweight="bold",
                color=color,
                ha="center", va="top" if dy < 0 else "bottom",
                zorder=10, label="_nf_zone_arrow_label",
            )


def draw(
    ax: "Axes",
    nf: NFAnalysis,
    curves: List["OffsetCurveT"],
    x_domain: str,
    style: StyleConfig,
    *,
    zorder: int = 8,
    legend_seen: Optional[set] = None,
    nacd_zone_spec: Optional[dict] = None,
) -> None:
    """Draw NF overlays for one subplot.

    ``legend_seen`` is a per-axes registry of legend keys already used.
    Pass an empty set when calling per axes; the function adds keys like
    ``"contaminated"``, ``"lambda_max"``, ``"lambda_<role>"`` and
    ``"freq_<role>"`` as it tags the first artist of each kind so the
    matplotlib legend gets exactly one entry per concept.
    """
    if not nf.visible:
        return

    if legend_seen is None:
        legend_seen = set()

    lambda_dec = int(getattr(style, "lambda_decimals", 1))
    freq_dec = int(getattr(style, "freq_decimals", 1))

    # Collect λ values already contributed by the subplot's curves
    # (``OffsetCurve.lambda_lines``). The renderer's lambda_drawer step
    # will draw those hyperbolas, so we must not redraw the same value
    # via an NFLine below (otherwise we get two overlapping hyperbolas).
    # Legacy projects that still carry ``lambda_max_curve=True`` NFLines
    # are also caught by this guard.
    curve_lambda_values: set = set()
    for c in curves:
        if not getattr(c, "visible", True):
            continue
        for L in (getattr(c, "lambda_lines", None) or []):
            try:
                if not getattr(L, "visible", True):
                    continue
                lv = float(L.lambda_value)
                if lv > 0:
                    curve_lambda_values.add(round(lv, 3))
            except (TypeError, ValueError):
                continue

    def _curve_owns_lambda(value: float) -> bool:
        try:
            return round(float(value), 3) in curve_lambda_values
        except (TypeError, ValueError):
            return False

    if nf.severity_overlay_mode == "scatter_on_top":
        col = nf.severity_palette.get("contaminated", "#d62728")
        # If a multi-zone spec provides per-zone ``point_color``s, use
        # them to colour contaminated points by their NACD zone
        # (matches DC Cut's coloured scatter overlay).  Falls back to
        # the flat ``col`` when no per-zone colours are configured.
        zone_colors = _zone_point_colors_from_spec(nacd_zone_spec)
        zone_thresholds = _zone_thresholds_from_spec(nacd_zone_spec)
        # If NFAnalysis carries per-zone overrides, merge their
        # point_color into the spec-derived list (same first-group
        # semantics).
        nf_bands = list(getattr(nf, "zone_bands", None) or [])
        if nf_bands:
            # Point coloring is NACD-domain (not x-axis-domain) so we
            # merge point_color overrides from ALL bands of the first
            # group regardless of axis. Edits on the lambda-axis zone
            # (the only axis shown when the active subplot is λ-based)
            # must still retint the scatter; filtering by axis==freq
            # dropped those edits silently.  For each zone_index, prefer
            # whichever band has an explicit point_color — any axis
            # wins over none.
            first_gi = min((int(b.group_index) for b in nf_bands),
                           default=0)
            group_bands = [b for b in nf_bands
                           if int(b.group_index) == first_gi]
            # Collapse per zone_index: keep the first band with a
            # non-empty effective colour (point_color or band_color);
            # fall back to any band otherwise.
            by_zone: Dict[int, "NFZoneBand"] = {}

            def _eff(b) -> str:
                pc = (getattr(b, "point_color", "") or "").strip()
                bc = (getattr(b, "band_color", "") or "").strip()
                return pc or bc

            for b in group_bands:
                zi = int(b.zone_index)
                cur = by_zone.get(zi)
                cur_color = _eff(cur) if cur is not None else ""
                new_color = _eff(b)
                if cur is None or (not cur_color and new_color):
                    by_zone[zi] = b
            ordered = [by_zone[k] for k in sorted(by_zone.keys())]
            merged = []
            any_color = False
            for b in ordered:
                c = _eff(b)
                if c:
                    any_color = True
                    merged.append(c)
                elif zone_colors is not None and int(b.zone_index) < len(zone_colors):
                    merged.append(zone_colors[int(b.zone_index)])
                else:
                    merged.append(None)
            if any_color:
                zone_colors = merged
        for r in nf.per_offset:
            if not bool(getattr(r, "scatter_visible", True)):
                continue
            if r.f.size == 0 or r.v.size == 0:
                continue
            m = r.mask_contaminated
            if m is None or m.size != r.f.size:
                continue
            if not np.any(m):
                continue
            curve = _curve_for_result(curves, r)
            f_r = np.asarray(r.f, dtype=float)
            v_r = np.asarray(r.v, dtype=float)
            if curve is not None:
                f_plot, v_plot = curve.masked_arrays("frequency")
                f_plot = np.asarray(f_plot, dtype=float)
                v_plot = np.asarray(v_plot, dtype=float)
                if f_plot.size == 0 or v_plot.size == 0:
                    continue
                class _CurveLike:
                    frequency = f_plot
                m_plot = _align_mask_to_curve_f(f_r, m, _CurveLike())
            else:
                m_plot = m
                f_plot, v_plot = f_r, v_r

            hidden = getattr(r, "point_hidden", None)
            if hidden is not None:
                hidden_arr = np.asarray(hidden, dtype=bool)
                if hidden_arr.size == m_plot.size:
                    m_plot = np.logical_and(m_plot, ~hidden_arr)

            if not np.any(m_plot):
                continue

            if x_domain == "frequency":
                xs = f_plot[m_plot]
            else:
                with np.errstate(divide="ignore", invalid="ignore"):
                    xs = np.where(f_plot[m_plot] > 0, v_plot[m_plot] / f_plot[m_plot], np.nan)
            ys = v_plot[m_plot]
            if "contaminated" in legend_seen:
                scatter_label = "_nolegend_"
            else:
                scatter_label = (
                    nf.legend_label.strip()
                    if getattr(nf, "legend_label", "")
                    else "Contaminated"
                )
                legend_seen.add("contaminated")
            edge_visible = bool(
                getattr(nf, "contaminated_edge_visible", True)
            )
            edge_w = float(getattr(nf, "contaminated_edge_width", 0.5) or 0.0)
            edge_c = getattr(nf, "contaminated_edge_color", "#000000") or "none"
            if not edge_visible or edge_w <= 0:
                edge_w = 0.0
                edge_c = "none"
            # Per-zone coloring: map each point to a zone and look up
            # its point_color; if none configured, use the flat col.
            point_c = _scatter_colors_for_points(
                r, m_plot, zone_colors, zone_thresholds, fallback=col,
            )
            ax.scatter(
                xs,
                ys,
                s=36,
                marker="D",
                c=point_c,
                alpha=0.85,
                zorder=max(zorder, 15),
                linewidths=edge_w,
                edgecolors=edge_c,
                clip_on=True,
                label=scatter_label,
            )

            # Request 3 \u2014 3-tier scatter: when the spec provides
            # distinct colours for non-contaminated zones (e.g. blue
            # for NACD 1\u20131.5, green for >1.5), overlay the clean
            # points coloured by zone so the user sees the full tri-
            # colour classification (matches DC Cut's live view).
            clean_mask = np.logical_and(~m_plot, np.isfinite(f_plot))
            distinct_clean = 0
            if zone_colors:
                seen: set = set()
                for idx, zc in enumerate(zone_colors):
                    if idx == 0:
                        continue  # zone 0 \u2192 contaminated
                    if isinstance(zc, str) and zc.strip():
                        seen.add(zc.strip().lower())
                distinct_clean = len(seen)
            if distinct_clean >= 1 and np.any(clean_mask):
                if x_domain == "frequency":
                    xs_c = f_plot[clean_mask]
                else:
                    with np.errstate(divide="ignore", invalid="ignore"):
                        xs_c = np.where(
                            f_plot[clean_mask] > 0,
                            v_plot[clean_mask] / f_plot[clean_mask],
                            np.nan,
                        )
                ys_c = v_plot[clean_mask]
                clean_fallback = nf.severity_palette.get("clean", "#1f77b4")
                clean_c = _scatter_colors_for_points(
                    r, clean_mask, zone_colors, zone_thresholds,
                    fallback=clean_fallback,
                )
                ax.scatter(
                    xs_c, ys_c,
                    s=20, marker="o", c=clean_c, alpha=0.85,
                    zorder=max(zorder, 14),
                    linewidths=0.0, edgecolors="none",
                    clip_on=True, label="_nolegend_",
                )

    # Per-offset lambda_max hyperbolas now live on the dispersion curve
    # (via ``OffsetCurve.lambda_lines``) and are drawn by the renderer's
    # lambda_drawer pass. The NACD drawer no longer mints synthetic
    # hyperbolas from ``nf.per_offset.lambda_max``; legacy
    # ``NFLine(lambda_max_curve=True)`` rows remain handled in the loop
    # below for backwards compatibility with old projects.

    with _preserve_limits(ax):
     for ln in nf.lines:
        if not ln.valid or not ln.visible or ln.value <= 0:
            continue
        # Prefer the user-typed custom label as legend text; otherwise let
        # the formatter use typography decimals.
        custom = (ln.custom_label or "").strip()
        if ln.lambda_max_curve:
            if _curve_owns_lambda(ln.value):
                # Curve's own lambda_drawer step already drew this hyperbola.
                continue
            tmp = OffsetCurve(name="_nf_lambda_max")
            tmp.add_lambda_line(
                NFLambdaLine(
                    lambda_value=float(ln.value),
                    label="",
                    custom_label=ln.custom_label or "",
                    color=ln.color,
                    visible=True,
                    line_style=ln.line_style,
                    line_width=ln.line_width,
                    alpha=ln.alpha,
                    show_label=ln.show_label,
                    label_position=float(ln.label_position),
                    label_fontsize=int(ln.label_fontsize or 0),
                    label_rotation_mode=str(ln.label_rotation_mode or "along"),
                    label_box=bool(ln.label_box),
                    label_box_facecolor=ln.label_box_facecolor,
                    label_box_alpha=float(ln.label_box_alpha),
                    label_box_edgecolor=ln.label_box_edgecolor,
                    label_box_pad=float(ln.label_box_pad),
                    label_scale=float(getattr(ln, "label_scale", 1.0) or 1.0),
                )
            )
            if "lambda_max" in legend_seen:
                ll = None
            else:
                ll = custom or f"\u03bb_max = {fmt_lambda(ln.value, lambda_dec)} m"
                legend_seen.add("lambda_max")
            lambda_drawer.draw(
                ax, tmp, x_domain, style, zorder=zorder - 1, legend_label=ll,
            )
            continue
        if ln.kind == "lambda":
            # Derived ``λ / max`` rows alongside a matching curve-owned λ
            # line would draw a second hyperbola. Keep the NFLine in the
            # tree (so the user can still see/toggle it), but skip the
            # draw call — curve's lambda_drawer step already drew it.
            if ln.role == "max" and _curve_owns_lambda(ln.value):
                continue
            tmp = OffsetCurve(name="_nf_lim")
            tmp.add_lambda_line(
                NFLambdaLine(
                    lambda_value=float(ln.value),
                    custom_label=ln.custom_label or "",
                    color=ln.color,
                    visible=True,
                    line_style=ln.line_style,
                    line_width=ln.line_width,
                    alpha=ln.alpha,
                    show_label=ln.show_label,
                    label_position=float(ln.label_position),
                    label_fontsize=int(ln.label_fontsize or 0),
                    label_rotation_mode=str(ln.label_rotation_mode or "along"),
                    label_box=bool(ln.label_box),
                    label_box_facecolor=ln.label_box_facecolor,
                    label_box_alpha=float(ln.label_box_alpha),
                    label_box_edgecolor=ln.label_box_edgecolor,
                    label_box_pad=float(ln.label_box_pad),
                    label_scale=float(getattr(ln, "label_scale", 1.0) or 1.0),
                )
            )
            key = f"lambda_{ln.role}"
            if key in legend_seen:
                ll = None
            else:
                ll = custom or f"\u03bb_{ln.role} = {fmt_lambda(ln.value, lambda_dec)} m"
                legend_seen.add(key)
            lambda_drawer.draw(
                ax, tmp, x_domain, style, zorder=zorder, legend_label=ll,
            )
        elif ln.kind == "freq" and x_domain == "frequency":
            key = f"freq_{ln.role}"
            if key in legend_seen:
                ll = None
            else:
                ll = custom or f"f_{ln.role} = {fmt_freq(ln.value, freq_dec)} Hz"
                legend_seen.add(key)
            _draw_freq_line(ax, ln, style, zorder=zorder, legend_label=ll)

    if nacd_zone_spec:
        try:
            _draw_zone_bands_and_labels(ax, nacd_zone_spec, x_domain, nf)
        except Exception:
            pass
