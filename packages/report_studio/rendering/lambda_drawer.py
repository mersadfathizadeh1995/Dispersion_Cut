"""
Draw constant-λ guide lines on Report Studio axes (single-axis view).

Ports the essential logic from ``dc_cut.gui.widgets.nf_limit_lines`` but
keeps this package self-contained.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.transforms import blended_transform_factory

from .label_format import fmt_lambda
from .style import StyleConfig

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from ..core.models import NFLambdaLine, OffsetCurve


# ── helpers ──────────────────────────────────────────────────────────────

def _label_text_for(
    line: "NFLambdaLine",
    lam: float,
    decimals: int = 1,
) -> str:
    """The text drawn next to a λ guide line.

    Always derived from the *lambda value* so the plot label matches what
    the data tree shows (`λ = 43 m`).  ``custom_label`` overrides only
    when explicitly set by the user.
    """
    custom = (line.custom_label or "").strip()
    if custom:
        return custom
    return f"\u03bb = {fmt_lambda(lam, decimals)} m"


def _t_from_position(line: "NFLambdaLine") -> float:
    """Normalised position along the visible line (0..1)."""
    try:
        t = float(line.label_position)
    except (TypeError, ValueError):
        t = 0.55
    return float(np.clip(t, 0.02, 0.98))


def _label_scale(line: "NFLambdaLine") -> float:
    scale = float(getattr(line, "label_scale", 1.0) or 1.0)
    return scale if scale > 0 else 1.0


def _bbox_kwargs(line: "NFLambdaLine") -> dict | None:
    if not getattr(line, "label_box", False):
        return None
    pad = max(line.label_box_pad, 0.0) * _label_scale(line)
    return dict(
        boxstyle=f"round,pad={pad / 10.0 + 0.15}",
        facecolor=line.label_box_facecolor,
        edgecolor=line.label_box_edgecolor,
        alpha=float(np.clip(line.label_box_alpha, 0.0, 1.0)),
        linewidth=0.5,
    )


def _label_fontsize(line: "NFLambdaLine", style_default: int) -> int:
    fs = int(getattr(line, "label_fontsize", 0) or 0)
    fs = fs if fs > 0 else int(style_default)
    fs = max(1, int(round(fs * _label_scale(line))))
    return fs


# ── label repositioning on zoom (frequency axis only) ────────────────────

def _reposition_lambda_labels(ax: "Axes") -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    if xmax <= xmin or ymax <= ymin:
        return
    xmin_safe = max(xmin, 1e-9)
    for txt in list(ax.texts):
        if getattr(txt, "_nf_kind", None) != "lambda_curve":
            continue
        lam = getattr(txt, "_nf_lam", None)
        if lam is None or lam <= 0:
            continue
        t = float(getattr(txt, "_nf_t", 0.55))
        f_lo = max(xmin_safe, ymin / lam if ymin > 0 else xmin_safe)
        f_hi = min(xmax, ymax / lam) if ymax > 0 else xmax
        if f_hi <= f_lo:
            f_pick = 0.5 * (xmin_safe + xmax)
            v_pick = float(np.clip(lam * f_pick, ymin, ymax))
        else:
            f_pick = float(
                10.0 ** (
                    np.log10(f_lo) + t * (np.log10(f_hi) - np.log10(f_lo))
                )
            )
            v_pick = float(lam * f_pick)
        try:
            txt.set_position((f_pick, v_pick))
        except Exception:
            pass


def _ensure_lambda_label_callback(ax: "Axes") -> None:
    if getattr(ax, "_nf_lambda_cb_attached", False):
        return
    try:
        ax.callbacks.connect("xlim_changed", lambda a: _reposition_lambda_labels(a))
        ax.callbacks.connect("ylim_changed", lambda a: _reposition_lambda_labels(a))
        ax._nf_lambda_cb_attached = True  # type: ignore[attr-defined]
    except Exception:
        pass


# ── drawers ──────────────────────────────────────────────────────────────

def _draw_lambda_on_frequency_axis(
    ax: "Axes",
    lam: float,
    *,
    color: str,
    linestyle: str,
    linewidth: float,
    alpha: float,
    show_labels: bool,
    label_fontsize: int,
    zorder: int,
    line: "NFLambdaLine",
    legend_label: str | None = None,
    lambda_decimals: int = 1,
) -> None:
    fmin, fmax = ax.get_xlim()
    fmin = max(fmin, 1e-6)
    fmax = max(fmax, fmin * 1.1)
    f_lo = fmin / 10.0
    f_hi = fmax * 10.0
    f_curve = np.logspace(np.log10(f_lo), np.log10(f_hi), 600)
    v_curve = lam * f_curve
    ax.plot(
        f_curve,
        v_curve,
        linestyle=linestyle,
        color=color,
        lw=linewidth,
        alpha=alpha,
        zorder=zorder,
        label=legend_label if legend_label else "_nf_limit",
        scalex=False,
        scaley=False,
    )
    if not (show_labels and line.show_label):
        return

    t = _t_from_position(line)
    y_lo_f, y_hi_f = ax.get_ylim()
    f_lo_vis = max(fmin, y_lo_f / lam if y_lo_f > 0 else fmin)
    f_hi_vis = min(fmax, y_hi_f / lam) if y_hi_f > 0 else fmax
    if f_hi_vis > f_lo_vis:
        f_pos = float(
            10.0 ** (
                np.log10(f_lo_vis) + t * (np.log10(f_hi_vis) - np.log10(f_lo_vis))
            )
        )
    else:
        f_pos = float(np.sqrt(fmin * fmax))
    v_pos = float(lam * f_pos)
    lbl = _label_text_for(line, lam, lambda_decimals)
    rotation = 30 if line.label_rotation_mode == "along" else 0
    bbox = _bbox_kwargs(line)
    fs = _label_fontsize(line, label_fontsize)
    txt = ax.text(
        f_pos,
        v_pos,
        f" {lbl} ",
        fontsize=fs,
        color=color,
        alpha=0.95,
        rotation=rotation,
        rotation_mode="anchor",
        ha="left",
        va="bottom",
        zorder=zorder + 1,
        fontweight="bold",
        bbox=bbox,
    )
    try:
        setattr(txt, "_nf_kind", "lambda_curve")
        setattr(txt, "_nf_lam", float(lam))
        setattr(txt, "_nf_t", float(t))
    except Exception:
        pass
    _ensure_lambda_label_callback(ax)


def _draw_lambda_on_wavelength_axis(
    ax: "Axes",
    lam: float,
    *,
    color: str,
    linestyle: str,
    linewidth: float,
    alpha: float,
    show_labels: bool,
    label_fontsize: int,
    zorder: int,
    line: "NFLambdaLine",
    legend_label: str | None = None,
    lambda_decimals: int = 1,
) -> None:
    ax.axvline(
        lam,
        linestyle=linestyle,
        color=color,
        lw=linewidth,
        alpha=alpha,
        zorder=zorder,
        label=legend_label if legend_label else "_nf_limit",
    )
    if not (show_labels and line.show_label):
        return
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    lbl = _label_text_for(line, lam, lambda_decimals)
    t = _t_from_position(line)
    bbox = _bbox_kwargs(line)
    fs = _label_fontsize(line, label_fontsize)
    rotation = 90 if line.label_rotation_mode == "along" else 0
    ax.text(
        lam,
        t,
        f" {lbl} ",
        fontsize=fs,
        color=color,
        alpha=0.95,
        rotation=rotation,
        ha="left",
        va="center",
        zorder=zorder + 1,
        fontweight="bold",
        transform=trans,
        bbox=bbox,
    )


def draw(
    ax: "Axes",
    curve: "OffsetCurve",
    x_domain: str,
    style: StyleConfig,
    *,
    zorder: float = 5.0,
    legend_label: str | None = None,
) -> None:
    """Draw every visible :class:`NFLambdaLine` on *curve*.

    When ``legend_label`` is provided, the FIRST drawn line carries it as
    its matplotlib ``label`` so it appears in the axes legend. Subsequent
    lines on the same call still use the hidden label (``_nf_limit``).
    """
    if not curve.lambda_lines:
        return
    label_fs = max(8, int(style.tick_label_size))
    lambda_dec = int(getattr(style, "lambda_decimals", 1))
    first = True
    for line in curve.lambda_lines:
        if not line.visible or line.lambda_value <= 0:
            continue
        lam = float(line.lambda_value)
        this_label = legend_label if (legend_label and first) else None
        first = False
        if x_domain == "frequency":
            _draw_lambda_on_frequency_axis(
                ax,
                lam,
                color=line.color,
                linestyle=line.line_style,
                linewidth=line.line_width,
                alpha=line.alpha,
                show_labels=True,
                label_fontsize=label_fs,
                zorder=int(zorder),
                line=line,
                legend_label=this_label,
                lambda_decimals=lambda_dec,
            )
        else:
            _draw_lambda_on_wavelength_axis(
                ax,
                lam,
                color=line.color,
                linestyle=line.line_style,
                linewidth=line.line_width,
                alpha=line.alpha,
                show_labels=True,
                label_fontsize=label_fs,
                zorder=int(zorder),
                line=line,
                legend_label=this_label,
                lambda_decimals=lambda_dec,
            )
