"""Legend rendering for Report Studio subplots.

This is the single place that turns a :class:`SubplotLegendConfig`
into a Matplotlib legend. The renderer should never call
``ax.legend(...)`` directly; instead it calls :func:`build_legend`
once per subplot and then (optionally) :func:`build_combined_outside_legend`
once for the whole figure.

The builder honours every option exposed in
:class:`SubplotLegendConfig`:

* ``visible`` — skip entirely (and remove any existing legend).
* ``placement`` — ``inside`` (attach to ax), ``outside_left/right/top/bottom``
  (defer to the combined builder), ``adjacent`` (anchored just
  outside the subplot but on the axes itself).
* ``location`` — Matplotlib loc string, e.g. ``"upper right"``.
* ``ncol`` / ``markerscale`` / ``frame_on`` / ``frame_alpha`` /
  ``shadow`` / ``title``.
* ``fontsize`` — overrides the typography-derived default.
* ``hidden_labels`` — exact label strings to drop from the legend.
* ``offset_x`` / ``offset_y`` — fine-tune anchor (axes fraction).
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.patches as mpatches

from . import registry as _reg


# Matches "<name> = <number> <unit>" (e.g. "λ_max = 43.0 m", "f_min = 8.7 Hz").
# We only care that the right-hand side starts with a number; everything
# after it is treated as the unit string.
_LBL_VALUE_RE = re.compile(
    r"^\s*(?P<name>.+?)\s*=\s*"
    r"(?P<value>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
    r"\s*(?P<unit>\S.*?)?\s*$"
)

# Default labels we recognise as the NACD "Contaminated" entry. Anything
# the user typed via ``NFAnalysis.legend_label`` is matched separately
# via the handle's collection type.
_NACD_DEFAULT_LABELS = {"contaminated", "bad band"}


def _classify_entry(label: str, handle) -> str:
    """Return ``"curve" | "nacd" | "guide" | "other"`` for one legend entry.

    Used by ordering and curve-collapse. The classification is best-effort
    and falls back to ``"curve"`` for anything we can't pin down — that's
    safe because the curve bucket is the one the user can opt to collapse.
    """
    lbl = (label or "").strip()
    if not lbl:
        return "other"
    if _LBL_VALUE_RE.match(lbl):
        return "guide"
    if lbl.lower() in _NACD_DEFAULT_LABELS:
        return "nacd"
    # Scatter plots (used by NACD's contaminated points) are PathCollection;
    # anything that scatters and isn't a guide line is treated as NACD even
    # when the user renamed it via ``legend_label``.
    try:
        from matplotlib.collections import PathCollection
        if isinstance(handle, PathCollection):
            return "nacd"
    except Exception:
        pass
    return "curve"


_KIND_ORDER = {"curve": 0, "nacd": 1, "guide": 2, "other": 3}


def _apply_collapse_curves(handles: list, labels: list,
                           curves_label: str) -> Tuple[list, list]:
    """Replace every ``"curve"`` entry with a single combined row.

    Keeps the *first* curve's handle so the marker swatch matches one of
    the actual curves; everything else is removed.
    """
    out_h: list = []
    out_l: list = []
    inserted = False
    for h, l in zip(handles, labels):
        if _classify_entry(l, h) == "curve":
            if not inserted:
                out_h.append(h)
                out_l.append(curves_label or "Curves")
                inserted = True
            continue
        out_h.append(h)
        out_l.append(l)
    return out_h, out_l


def _apply_entry_order(handles: list, labels: list, order: str) -> Tuple[list, list]:
    """Sort entries by ``"by_name"`` or ``"by_kind"``; otherwise preserve order."""
    if order == "by_name":
        paired = sorted(zip(handles, labels), key=lambda hl: (hl[1] or "").lower())
    elif order == "by_kind":
        paired = sorted(
            enumerate(zip(handles, labels)),
            key=lambda item: (
                _KIND_ORDER.get(_classify_entry(item[1][1], item[1][0]), 9),
                item[0],  # stable within kind
            ),
        )
        paired = [pair for _, pair in paired]
    else:
        return handles, labels
    if not paired:
        return [], []
    h2, l2 = zip(*paired)
    return list(h2), list(l2)


# Matplotlib's default legend zorder is 5; curves/scatter often sit at
# 2-3, but lambda guide lines and canvas labels we draw can reach 9-12.
# Park the legend above all of those so it is never overdrawn.
_LEGEND_ZORDER = 1000


# Anchor points used when ``offset_x``/``offset_y`` need a baseline
# inside the axes for ``inside`` placement.
LOC_ANCHORS: Dict[str, Tuple[float, float]] = {
    "upper right": (1.0, 1.0), "upper left": (0.0, 1.0),
    "lower left": (0.0, 0.0), "lower right": (1.0, 0.0),
    "right": (1.0, 0.5), "center left": (0.0, 0.5),
    "center right": (1.0, 0.5), "lower center": (0.5, 0.0),
    "upper center": (0.5, 1.0), "center": (0.5, 0.5),
    "best": (1.0, 1.0),
}


def _gather(ax, sp, sheet) -> Tuple[list, list]:
    """Collect handles+labels from artists *and* registered collectors."""
    handles, labels = ax.get_legend_handles_labels()
    handles = list(handles)
    labels = list(labels)
    for item in _reg.collect_items(ax, sp, sheet):
        if item.label and item.label not in labels:
            handles.append(item.handle)
            labels.append(item.label)
    return handles, labels


def _parse_value_label(label: str) -> Optional[Tuple[str, float, str]]:
    """Return ``(name, value, unit)`` for ``"λ_max = 43.0 m"`` style labels.

    ``None`` for any label that doesn't fit the ``<name> = <number> <unit>``
    pattern, in which case it falls through to exact deduping.
    """
    m = _LBL_VALUE_RE.match(label or "")
    if not m:
        return None
    try:
        value = float(m.group("value"))
    except (TypeError, ValueError):
        return None
    unit = (m.group("unit") or "").strip()
    return m.group("name").strip(), value, unit


def _format_range(values: List[float], decimals: int = 1) -> str:
    """Format a value range, collapsing to a single value when it makes sense."""
    lo, hi = min(values), max(values)
    if abs(hi - lo) < 10 ** (-decimals):
        return f"{lo:.{decimals}f}"
    return f"{lo:.{decimals}f} \u2013 {hi:.{decimals}f}"  # en dash


def _dedupe_smart(pairs: List[Tuple[object, str]],
                  kind: str) -> Tuple[list, list]:
    """Apply ``prefix``/``range`` dedupe to ``[(handle, label), …]``.

    * ``prefix`` collapses every ``<name> = <value> <unit>`` label to a
      single ``<name>`` entry, keeping the *first* handle encountered.
    * ``range`` collapses likewise but reformats the kept label as
      ``<name> = <min> – <max> <unit>`` (single value when min == max).

    Labels that don't match the value pattern fall back to exact dedupe
    (first occurrence wins) so user-set legend names still appear once.
    """
    out_h: list = []
    out_l: list = []
    # Track first index for each name so we can rewrite it later (range mode).
    name_to_idx: Dict[str, int] = {}
    name_to_unit: Dict[str, str] = {}
    name_to_values: Dict[str, list] = {}
    seen_exact: set = set()

    for h, l in pairs:
        parsed = _parse_value_label(l)
        if parsed is None:
            if l in seen_exact:
                continue
            seen_exact.add(l)
            out_h.append(h)
            out_l.append(l)
            continue
        name, value, unit = parsed
        if name in name_to_idx:
            name_to_values[name].append(value)
            continue
        name_to_idx[name] = len(out_l)
        name_to_unit[name] = unit
        name_to_values[name] = [value]
        out_h.append(h)
        out_l.append(name)  # placeholder; rewritten below for range mode

    if kind == "range":
        for name, idx in name_to_idx.items():
            unit = name_to_unit.get(name, "")
            rng = _format_range(name_to_values[name])
            out_l[idx] = f"{name} = {rng} {unit}".strip()

    return out_h, out_l


def _filter_hidden(handles: list, labels: list,
                   hidden: Iterable[str]) -> Tuple[list, list]:
    s = {h for h in (hidden or ())}
    if not s:
        return handles, labels
    paired = [(h, l) for h, l in zip(handles, labels) if l not in s]
    if not paired:
        return [], []
    h2, l2 = zip(*paired)
    return list(h2), list(l2)


def _resolve_fontsize(lc, style) -> float:
    """Pick the legend font size, honouring per-subplot override."""
    if getattr(lc, "fontsize", None):
        return float(lc.fontsize)
    return float(getattr(style, "legend_font_size", 9))


def _resolve_scale(lc) -> float:
    s = float(getattr(lc, "scale", 1.0) or 1.0)
    return max(0.25, min(s, 5.0))


def _resolve_ncol(lc, n_items: int, placement: str) -> int:
    """Pick column count from orientation + ncol settings.

    * ``orientation == "vertical"`` → 1 column.
    * ``orientation == "horizontal"`` → as many columns as items
      (clamped to 8 for readability).
    * ``orientation == "auto"`` → vertical for left/right, horizontal
      for top/bottom outside placements; otherwise honour ``ncol``.
    """
    o = (getattr(lc, "orientation", "auto") or "auto").lower()
    requested = max(1, int(getattr(lc, "ncol", 1) or 1))
    if o == "vertical":
        return 1
    if o == "horizontal":
        return max(1, min(n_items, 8))
    # auto:
    if placement in ("outside_top", "outside_bottom"):
        return max(requested, min(n_items, 8))
    if placement in ("outside_left", "outside_right"):
        return 1
    return requested


def _legend_kwargs(lc, style, font_family: str, font_weight: str,
                   *, n_items: int = 0, placement: str = "inside") -> dict:
    fs = _resolve_fontsize(lc, style)
    scale = _resolve_scale(lc)
    fs_eff = fs * scale
    kw = dict(
        fontsize=fs_eff,
        frameon=bool(lc.frame_on),
        framealpha=float(lc.frame_alpha),
        shadow=bool(lc.shadow),
        ncol=_resolve_ncol(lc, n_items, placement),
        markerscale=float(lc.markerscale) * scale,
        handlelength=1.5 * scale,
        handletextpad=0.6 * scale,
        labelspacing=0.4 * scale,
        columnspacing=1.2 * scale,
        borderpad=0.4 * scale,
        prop={"family": font_family, "size": fs_eff, "weight": font_weight},
    )
    if lc.title:
        kw["title"] = lc.title
    return kw


def build_legend(ax, sp, sheet, style) -> Optional[object]:
    """Render the legend for one subplot. Returns the legend or ``None``.

    Callers must invoke this exactly once per axes; any earlier
    legend on ``ax`` is removed first so re-renders stay clean.
    """
    lc = getattr(sp, "legend", None)
    if lc is None:
        # Subplot without rich legend config — bail out without touching ax.
        return None

    # Drop any pre-existing legend (idempotent re-render).
    old = ax.get_legend()
    if old is not None:
        try:
            old.remove()
        except Exception:
            pass

    if not lc.visible:
        return None

    placement = str(lc.placement)
    # Combined outside placements are handled by the figure-level builder
    # later. Per-subplot outside ("not combined") fall through and get a
    # legend anchored just outside this axes — matches geo_figure's
    # "adjacent" behaviour.
    if placement.startswith("outside_") and bool(getattr(lc, "combine", True)):
        return None

    handles, labels = _gather(ax, sp, sheet)
    handles, labels = _filter_hidden(handles, labels, lc.hidden_labels)
    if bool(getattr(lc, "collapse_curves", False)):
        handles, labels = _apply_collapse_curves(
            handles, labels,
            getattr(lc, "curves_label", "") or "Curves",
        )
    handles, labels = _apply_entry_order(
        handles, labels, str(getattr(lc, "entry_order", "as_drawn")),
    )
    if not handles:
        return None

    font_family = sp.font_family or getattr(style, "font_family", "sans-serif")
    font_weight = getattr(style, "font_weight", "normal")
    kwargs = _legend_kwargs(
        lc, style, font_family, font_weight,
        n_items=len(labels), placement=placement,
    )

    if placement.startswith("outside_") or placement == "adjacent":
        # Per-subplot outside legend: anchor just outside the axes.
        side = (placement.split("_", 1)[1] if placement.startswith("outside_")
                else (getattr(lc, "adjacent_side", "right") or "right"))
        loc, anchor = _adjacent_anchor(side)
        kwargs["loc"] = loc
        kwargs["bbox_to_anchor"] = (
            anchor[0] + float(getattr(lc, "offset_x", 0.0) or 0.0),
            anchor[1] + float(getattr(lc, "offset_y", 0.0) or 0.0),
        )
        kwargs["bbox_transform"] = ax.transAxes
        kwargs["borderaxespad"] = 0.2
    else:
        kwargs["loc"] = lc.location or "best"
        # Optional fine-tuning offset (in axes fraction).
        ox = float(getattr(lc, "offset_x", 0.0) or 0.0)
        oy = float(getattr(lc, "offset_y", 0.0) or 0.0)
        if ox or oy:
            bx, by = LOC_ANCHORS.get(kwargs["loc"], (1.0, 1.0))
            kwargs["bbox_to_anchor"] = (bx + ox, by + oy)
            kwargs["bbox_transform"] = ax.transAxes

    legend = ax.legend(handles, labels, **kwargs)
    if legend is not None:
        # Park the legend above every artist (curves, scatter, guide lines,
        # canvas labels) so it is never overdrawn.
        legend.set_zorder(_LEGEND_ZORDER)
    return legend


def _adjacent_anchor(side: str) -> Tuple[str, Tuple[float, float]]:
    """Return ``(loc, (x, y))`` for an axes-relative anchor outside *side*."""
    side = (side or "right").lower()
    if side == "left":
        return "center right", (-0.02, 0.5)
    if side == "top":
        return "lower center", (0.5, 1.02)
    if side == "bottom":
        return "upper center", (0.5, -0.12)
    return "center left", (1.02, 0.5)  # right (default)


def _outside_axes(state) -> List[Tuple[str, object]]:
    """Iterate over (key, ax) pairs for subplots flagged as outside_*."""
    out = []
    for key, sp in getattr(state, "subplots", {}).items():
        lc = getattr(sp, "legend", None)
        if lc is None or not lc.visible:
            continue
        if not str(lc.placement).startswith("outside_"):
            continue
        ax = getattr(state, "_axes_map", {}).get(key)
        if ax is not None:
            out.append((key, ax))
    return out


def build_combined_outside_legend(fig, axes_map: Dict[str, object],
                                  sheet, style) -> Optional[object]:
    """Emit one ``fig.legend`` covering every subplot using outside_* placement.

    Subplots are grouped by their display name with a bold header
    so the combined legend stays legible.
    """
    # (display_name, axes, handles, labels) — keep the axes around so we
    # can align the combined legend to a *single* contributing subplot
    # when only one opted in (instead of centring it on the whole figure).
    groups: List[Tuple[str, object, list, list]] = []
    placement = None
    first_lc = None

    for key, sp in getattr(sheet, "subplots", {}).items():
        lc = getattr(sp, "legend", None)
        if lc is None or not lc.visible:
            continue
        if not str(lc.placement).startswith("outside_"):
            continue
        # Only "combined" outside legends contribute to the figure-level
        # legend; "not combined" subplots get their own per-axes legend
        # in build_legend instead.
        if not bool(getattr(lc, "combine", True)):
            continue
        ax = axes_map.get(key)
        if ax is None:
            continue
        handles, labels = _gather(ax, sp, sheet)
        handles, labels = _filter_hidden(handles, labels, lc.hidden_labels)
        # Per-subplot curve collapse runs *before* combining so a single
        # "Source offset curves" row replaces the noisy per-offset list
        # in each contributing subplot.
        if bool(getattr(lc, "collapse_curves", False)):
            handles, labels = _apply_collapse_curves(
                handles, labels,
                getattr(lc, "curves_label", "") or "Curves",
            )
        if not handles:
            continue
        if placement is None:
            placement = str(lc.placement)
            first_lc = lc
        groups.append((sp.display_name or key, ax, handles, labels))

    if not groups or first_lc is None:
        return None

    dedupe = bool(getattr(first_lc, "dedupe", True))
    dedupe_kind = str(getattr(first_lc, "dedupe_kind", "exact") or "exact")
    combined_h: list = []
    combined_l: list = []
    header_idx: list = []
    sep_idx: list = []

    if dedupe and dedupe_kind in ("prefix", "range"):
        # Prefix/range modes flatten *every* group into one list, then
        # collapse value-bearing labels (``λ_max = 43 m``…) by name.
        all_pairs: List[Tuple[object, str]] = []
        for _name, _ax, hs, ls in groups:
            all_pairs.extend(zip(hs, ls))
        merged_h, merged_l = _dedupe_smart(all_pairs, dedupe_kind)
        combined_h.extend(merged_h)
        combined_l.extend(merged_l)

    elif dedupe:
        # Exact mode: drop byte-identical labels but keep the order
        # they were collected in.
        seen: set = set()
        for _name, _ax, hs, ls in groups:
            for h, l in zip(hs, ls):
                if l in seen:
                    continue
                seen.add(l)
                combined_h.append(h)
                combined_l.append(l)

    else:
        # No dedupe: keep one bold header per group so the user can tell
        # which subplot contributed which entries.
        for i, (name, _ax, hs, ls) in enumerate(groups):
            if i > 0 and combined_h:
                sep_idx.append(len(combined_h))
                combined_h.append(
                    mpatches.Patch(facecolor="none", edgecolor="none"))
                combined_l.append(" ")
            if len(groups) > 1:
                header_idx.append(len(combined_h))
                combined_h.append(
                    mpatches.Patch(facecolor="none", edgecolor="none"))
                combined_l.append(name)
            combined_h.extend(hs)
            combined_l.extend(ls)

    if not combined_h:
        return None

    # Final sort pass for the combined legend. Skipped when the user has
    # turned dedupe off because in that mode we already inserted bold
    # group headers per subplot whose ordering must be preserved.
    order = str(getattr(first_lc, "entry_order", "as_drawn"))
    if order != "as_drawn" and not header_idx and not sep_idx:
        combined_h, combined_l = _apply_entry_order(
            combined_h, combined_l, order
        )

    font_family = getattr(style, "font_family", "sans-serif")
    font_weight = getattr(style, "font_weight", "normal")
    n_data_items = sum(1 for _ in combined_l)
    kwargs = _legend_kwargs(
        first_lc, style, font_family, font_weight,
        n_items=n_data_items, placement=placement,
    )
    fs = kwargs["fontsize"]

    # Build at figure centre first so we can measure it, then we expand
    # the figure dimensions to append a dedicated legend area on the
    # requested side (mirrors geo_figure's behaviour).
    kwargs.update(
        loc="center",
        bbox_to_anchor=(0.5, 0.5),
        bbox_transform=fig.transFigure,
        borderaxespad=0.3,
    )

    legend = fig.legend(combined_h, combined_l, **kwargs)
    if legend is not None:
        legend.set_zorder(_LEGEND_ZORDER)

    # Style the section headers and inter-group spacers.
    if legend is not None:
        texts = legend.get_texts()
        handles = legend.legend_handles if hasattr(legend, "legend_handles") \
            else legend.legendHandles
        for idx in sep_idx:
            if idx < len(texts):
                texts[idx].set_fontsize(fs * 0.15)
                texts[idx].set_color("none")
            if idx < len(handles):
                handles[idx].set_visible(False)
        for idx in header_idx:
            if idx < len(texts):
                texts[idx].set_fontweight("bold")
                texts[idx].set_fontsize(fs * 1.05)
            if idx < len(handles):
                handles[idx].set_visible(False)

        # If only one subplot opted into the combined outside legend,
        # align the legend to *that* subplot's edge instead of the
        # figure centre — otherwise it floats halfway down the figure
        # for an outside_left on the top-left subplot.
        unique_axes = {g[1] for g in groups}
        single_target = next(iter(unique_axes)) if len(unique_axes) == 1 \
            else None

        try:
            _expand_figure_for_legend(
                fig, legend, placement,
                offset_x=float(first_lc.offset_x or 0.0),
                offset_y=float(first_lc.offset_y or 0.0),
                target_axes=single_target,
            )
        except Exception:
            # Expansion is a best-effort polish; never fail the render.
            pass

    return legend


def _expand_figure_for_legend(fig, legend, placement: str,
                              offset_x: float = 0.0,
                              offset_y: float = 0.0,
                              target_axes=None) -> None:
    """Grow the figure to make room for *legend* on the requested side.

    Mirrors geo_figure's approach: measure the legend, expand
    ``set_size_inches`` accordingly, scale and shift every existing
    axes so their *inch* footprint stays the same, then re-anchor the
    legend at the appended margin's centre.

    When ``target_axes`` is provided, the legend is anchored to the
    centre of that one axes (vertically for left/right, horizontally
    for top/bottom) instead of the figure centre. This is what you
    want when only one subplot opted into a combined outside legend
    — otherwise it floats halfway down the figure regardless of which
    subplot it represents.
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    # Force a draw so the legend has a measurable extent.
    if fig.canvas is None or not hasattr(fig.canvas, "get_renderer"):
        FigureCanvasAgg(fig)
    fig.canvas.draw()
    rndr = fig.canvas.get_renderer()

    leg_bb = legend.get_window_extent(rndr)
    leg_bb_in = leg_bb.transformed(fig.dpi_scale_trans.inverted())
    leg_w = float(leg_bb_in.width)
    leg_h = float(leg_bb_in.height)

    fig_w, fig_h = fig.get_size_inches()
    pad = 0.25  # inches between subplot area and legend

    all_axes = list(fig.get_axes())

    if placement in ("outside_left", "outside_right"):
        extra_w = leg_w + pad
        new_w = fig_w + extra_w
        if placement == "outside_left":
            shift_x = extra_w / new_w
            leg_x = shift_x / 2.0
        else:
            shift_x = 0.0
            leg_x = 1.0 - (extra_w / 2.0) / new_w
        ratio_w = fig_w / new_w

        # Secondary growth if the legend is taller than the figure.
        extra_h = max(leg_h + pad - fig_h, 0.0)
        new_h = fig_h + extra_h
        ratio_h = fig_h / new_h if extra_h > 0 else 1.0
        shift_y = (extra_h / 2.0) / new_h if extra_h > 0 else 0.0

        fig.set_size_inches(new_w, new_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                shift_x + pos.x0 * ratio_w,
                shift_y + pos.y0 * ratio_h,
                pos.width * ratio_w,
                pos.height * ratio_h,
            ])
        # Vertical alignment: figure centre by default, but pin to the
        # target subplot's vertical centre when a single contributor
        # opted in.
        leg_y_anchor = 0.5
        if target_axes is not None:
            try:
                pos = target_axes.get_position()
                leg_y_anchor = pos.y0 + pos.height / 2.0
            except Exception:
                leg_y_anchor = 0.5
        legend.set_bbox_to_anchor(
            (leg_x + offset_x, leg_y_anchor + offset_y),
            transform=fig.transFigure,
        )
        legend._loc = 10  # center

    elif placement in ("outside_top", "outside_bottom"):
        extra_h = leg_h + pad
        new_h = fig_h + extra_h
        if placement == "outside_bottom":
            shift_y = extra_h / new_h
            leg_y = shift_y / 2.0
        else:
            shift_y = 0.0
            leg_y = 1.0 - (extra_h / 2.0) / new_h
        ratio_h = fig_h / new_h

        extra_w = max(leg_w + pad - fig_w, 0.0)
        new_w = fig_w + extra_w
        ratio_w = fig_w / new_w if extra_w > 0 else 1.0
        shift_x = (extra_w / 2.0) / new_w if extra_w > 0 else 0.0

        fig.set_size_inches(new_w, new_h)
        for ax in all_axes:
            pos = ax.get_position()
            ax.set_position([
                shift_x + pos.x0 * ratio_w,
                shift_y + pos.y0 * ratio_h,
                pos.width * ratio_w,
                pos.height * ratio_h,
            ])
        # Horizontal alignment: figure centre by default, but pin to
        # the target subplot's horizontal centre when only one
        # contributed.
        leg_x_anchor = 0.5
        if target_axes is not None:
            try:
                pos = target_axes.get_position()
                leg_x_anchor = pos.x0 + pos.width / 2.0
            except Exception:
                leg_x_anchor = 0.5
        legend.set_bbox_to_anchor(
            (leg_x_anchor + offset_x, leg_y + offset_y),
            transform=fig.transFigure,
        )
        legend._loc = 10  # center
