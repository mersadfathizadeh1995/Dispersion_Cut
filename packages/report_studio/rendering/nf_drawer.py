"""Near-field (NACD-Only) overlays: severity scatter + limit lines."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import numpy as np
from matplotlib.transforms import blended_transform_factory

from ..core.models import NFAnalysis, NFLambdaLine, NFLine, OffsetCurve
from . import lambda_drawer
from .label_format import fmt_freq, fmt_lambda
from .style import StyleConfig

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..core.models import OffsetCurve as OffsetCurveT


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


def draw(
    ax: "Axes",
    nf: NFAnalysis,
    curves: List["OffsetCurveT"],
    x_domain: str,
    style: StyleConfig,
    *,
    zorder: int = 8,
    legend_seen: Optional[set] = None,
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
            ax.scatter(
                xs,
                ys,
                s=36,
                marker="D",
                c=col,
                alpha=0.85,
                zorder=max(zorder, 15),
                linewidths=edge_w,
                edgecolors=edge_c,
                clip_on=True,
                label=scatter_label,
            )

    has_lambda_max_line = any(ln.lambda_max_curve for ln in nf.lines)
    if nf.show_lambda_max and not has_lambda_max_line:
        for r in nf.per_offset:
            if r.lambda_max <= 0:
                continue
            if _curve_owns_lambda(r.lambda_max):
                # Curve's own lambda_drawer step already drew this hyperbola.
                continue
            tmp = OffsetCurve(name="_nf_lambda_max")
            tmp.add_lambda_line(
                NFLambdaLine(
                    lambda_value=float(r.lambda_max),
                    label="",
                    color=nf.severity_palette.get("marginal", "#ff7f0e"),
                    visible=True,
                    line_style=":",
                    line_width=1.2,
                    alpha=0.75,
                    show_label=False,
                )
            )
            if "lambda_max" in legend_seen:
                ll = None
            else:
                ll = f"\u03bb_max = {fmt_lambda(r.lambda_max, lambda_dec)} m"
                legend_seen.add("lambda_max")
            lambda_drawer.draw(
                ax, tmp, x_domain, style, zorder=zorder - 1, legend_label=ll,
            )

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
