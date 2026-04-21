"""
Unified renderer — SheetState → matplotlib Figure.

One function, no dual-renderer split. The entire rendering pipeline
in a single, testable module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from . import layout_builder, curve_drawer, spectrum_drawer, aggregated_drawer, lambda_drawer, nf_drawer
from .style import StyleConfig
from ..legend import builder as legend_builder

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ..core.models import OffsetCurve, SheetState, SpectrumData


def render_sheet(
    fig: Figure,
    state: "SheetState",
    style: Optional[StyleConfig] = None,
    selected_uid: str = "",
    quality: str = "draft",
) -> Dict[str, "Axes"]:
    """
    Render a complete sheet onto *fig*.

    Parameters
    ----------
    fig : Figure
        Target matplotlib figure (will be cleared).
    state : SheetState
        Complete state: curves, spectra, subplots, layout.
    style : StyleConfig, optional
        Rendering style. Uses defaults if not given.
    selected_uid : str
        UID of the currently selected curve (drawn highlighted).
    quality : str
        "draft" (fast canvas) or "high" (export quality).

    Returns
    -------
    dict
        Mapping subplot_key → Axes for post-render access.
    """
    if style is None:
        style = StyleConfig()

    fig.clear()
    fig.set_facecolor(style.figure_facecolor)
    fig.set_size_inches(state.figure_width, state.figure_height)

    # Reset transient diagnostics before this render pass.
    try:
        state._last_render_warnings = []
    except Exception:
        pass

    # Create subplot grid
    axes = layout_builder.create_grid(fig, state)

    # Render each subplot. ``bars_info`` collects one dict per subplot
    # that drew a spectrum; it's consumed by the combined-spectrum-bar
    # pass below.
    bars_info: List[Dict] = []
    for key, ax in axes.items():
        _render_subplot(
            ax, key, state, style, selected_uid, quality,
            bars_info=bars_info,
        )

    # Detect any outside legend placement so we know whether to skip the
    # standard margin pass (the legend will resize the whole figure).
    outside_side = _outside_legend_side(state)

    # Apply layout. For outside placements we deliberately leave margins
    # at matplotlib defaults — ``_expand_figure_for_legend`` (run by the
    # combined-legend builder) will grow the figure and reposition every
    # axes to make room, so the existing subplots keep their proportions.
    try:
        if state.grid_rows == 1 and state.grid_cols == 1 and not outside_side:
            fig.tight_layout(pad=1.5)
        elif not outside_side:
            fig.subplots_adjust(
                hspace=state.hspace, wspace=state.wspace,
                left=0.08, right=0.96, top=0.94, bottom=0.08,
            )
        else:
            # Inside-only layout first; the outside legend builder will
            # grow the figure afterwards.
            fig.subplots_adjust(
                hspace=state.hspace, wspace=state.wspace,
                left=0.08, right=0.96, top=0.94, bottom=0.08,
            )
    except Exception:
        pass

    # Combined outside legend (if any subplot uses outside_* placement).
    # Built *after* the layout is finalised so the builder can measure
    # the legend, then expand the figure dimensions to append a
    # dedicated legend area (the same approach as geo_figure).
    if outside_side:
        try:
            legend_builder.build_combined_outside_legend(
                fig, axes, state, style
            )
        except Exception:
            # Never let legend errors break the figure render.
            pass

    # Spectrum colorbar pass — either one combined bar for the whole
    # figure or one bar per subplot. See :func:`_draw_spectrum_colorbars`.
    try:
        _draw_spectrum_colorbars(fig, state, style, bars_info)
    except Exception:
        pass

    return axes


def _outside_legend_side(state: "SheetState") -> str:
    """Return ``"right"|"left"|"top"|"bottom"|""`` for combined outside.

    Only *combined* outside legends grow the figure; per-subplot outside
    legends ("not combined") are anchored against their own axes via
    ``build_legend`` and don't trigger figure-level expansion.
    """
    for sp in getattr(state, "subplots", {}).values():
        lc = getattr(sp, "legend", None)
        if lc is None or not lc.visible:
            continue
        place = str(getattr(lc, "placement", "") or "")
        if place.startswith("outside_") and bool(getattr(lc, "combine", True)):
            return place.split("_", 1)[1]
    return ""


def _render_subplot(
    ax: "Axes",
    subplot_key: str,
    state: "SheetState",
    style: StyleConfig,
    selected_uid: str,
    quality: str = "draft",
    bars_info: Optional[List[Dict]] = None,
):
    """Render one subplot: spectrum backgrounds + dispersion curves + axes."""
    sp = state.subplots.get(subplot_key)
    if sp is None:
        ax.set_visible(False)
        return

    x_domain = sp.x_domain
    curves = state.get_curves_for_subplot(subplot_key)

    # 1. Draw spectrum backgrounds (behind curves)
    _last_im = None
    _last_curve_for_colorbar = None
    for curve in curves:
        if curve.spectrum_uid and curve.spectrum_visible:
            spec = state.spectra.get(curve.spectrum_uid)
            if spec and spec.has_data:
                im = spectrum_drawer.draw(
                    ax, spec, x_domain, style,
                    curve=curve, quality=quality,
                )
                if im is not None:
                    _last_im = im
                    _last_curve_for_colorbar = curve

    # 2. Draw aggregated average + uncertainty (if linked)
    if sp.aggregated_uid:
        agg = state.aggregated.get(sp.aggregated_uid)
        if agg and agg.has_data:
            shadow_curves = [
                state.curves[uid]
                for uid in agg.shadow_curve_uids
                if uid in state.curves
            ]
            aggregated_drawer.draw(
                ax, agg, shadow_curves, x_domain, style,
            )

    # 3. Draw dispersion curves (non-shadow or explicit visible)
    for curve in curves:
        if curve.visible:
            curve_drawer.draw(
                ax, curve, x_domain, style,
                highlight=(curve.uid == selected_uid),
            )

    # 3b. Per-curve λ guide lines (from PKL / project)
    for curve in curves:
        if curve.visible and curve.lambda_lines:
            lambda_drawer.draw(ax, curve, x_domain, style)

    nf_legend_seen: set = set()
    for nf_uid in sp.nf_uids:
        nf = state.nf_analyses.get(nf_uid)
        if nf is not None:
            nf_drawer.draw(
                ax, nf, curves, x_domain, style, legend_seen=nf_legend_seen,
            )

    # 4. Configure axes
    _configure_axes(ax, sp, state, style, x_domain, subplot_key, curves=curves)

    # 5. Legend (delegated to legend.builder so all settings live in one place).
    #    Per-subplot ``SubplotLegendConfig`` (sp.legend) is the source of
    #    truth; outside_* placements are picked up by the combined legend
    #    pass in :func:`render_sheet` after every subplot is drawn.
    try:
        legend_builder.build_legend(ax, sp, state, style)
    except Exception:
        pass

    # 6. Colorbar bookkeeping — defer actual drawing to the post-loop
    #    pass in :func:`_draw_spectrum_colorbars` so we can decide
    #    between per-subplot bars and one combined figure-level bar
    #    once every spectrum has been rendered.
    if (
        bars_info is not None
        and _last_im is not None
        and _last_curve_for_colorbar is not None
    ):
        try:
            cmap_name = _last_im.get_cmap().name
        except Exception:
            cmap_name = ""
        try:
            vmin, vmax = _last_im.get_clim()
        except Exception:
            vmin, vmax = (None, None)
        bars_info.append({
            "key": subplot_key,
            "ax": ax,
            "im": _last_im,
            "curve": _last_curve_for_colorbar,
            "cmap": cmap_name,
            "vmin": vmin,
            "vmax": vmax,
        })

    # 7. Title
    if sp.display_name:
        title_size = sp.title_font_size if sp.title_font_size > 0 else style.title_size
        title_font = sp.font_family if sp.font_family else style.font_family
        title_weight = getattr(style, "font_weight", "normal")
        ax.set_title(
            sp.display_name,
            fontsize=title_size,
            fontfamily=title_font,
            fontweight=title_weight,
        )


def _append_spectrum_extent(
    all_x: List[np.ndarray],
    all_y: List[np.ndarray],
    spec: "SpectrumData",
    x_domain: str,
) -> None:
    """Collect1D x/y samples from spectrum axes for auto-ranging."""
    f = np.asarray(spec.frequencies, dtype=float)
    v = np.asarray(spec.velocities, dtype=float)
    if f.size == 0 or v.size == 0:
        return
    if x_domain == "frequency":
        all_x.append(f.reshape(-1))
        all_y.append(v.reshape(-1))
        return
    if f.ndim == 1 and v.ndim == 1:
        ff, vv = np.meshgrid(f, v)
        with np.errstate(divide="ignore", invalid="ignore"):
            wl = vv / ff
        wl = wl[np.isfinite(wl) & (wl > 0)]
        if wl.size:
            all_x.append(wl.ravel())
    all_y.append(v.reshape(-1))


def _visible_data_extent(
    sp,
    state: "SheetState",
    subplot_key: str,
    x_domain: str,
    curves: Optional[List["OffsetCurve"]],
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Union of visible curve + visible spectrum samples (no padding)."""
    all_x: List[np.ndarray] = []
    all_y: List[np.ndarray] = []
    if not curves:
        return None, None
    for c in curves:
        if not c.visible or c.frequency.size == 0:
            continue
        if x_domain == "wavelength" and c.wavelength.size > 0:
            all_x.append(np.asarray(c.wavelength, dtype=float))
        else:
            all_x.append(np.asarray(c.frequency, dtype=float))
        all_y.append(np.asarray(c.velocity, dtype=float))
    for c in curves:
        if not c.visible or not c.spectrum_uid or not c.spectrum_visible:
            continue
        spec = state.spectra.get(c.spectrum_uid)
        if spec and spec.has_data:
            _append_spectrum_extent(all_x, all_y, spec, x_domain)
    if not all_x or not all_y:
        return None, None
    return np.concatenate(all_x), np.concatenate(all_y)


def _configure_axes(
    ax,
    sp,
    state: "SheetState",
    style: StyleConfig,
    x_domain: str,
    subplot_key: str,
    curves=None,
):
    """Set axis labels, limits, scales, tick formats, and styling."""
    import matplotlib.ticker as ticker

    # Per-subplot font overrides
    label_size = sp.axis_label_font_size if sp.axis_label_font_size > 0 else style.axis_label_size
    tick_size = sp.tick_label_font_size if sp.tick_label_font_size > 0 else style.tick_label_size
    font = sp.font_family if sp.font_family else style.font_family
    weight = getattr(style, "font_weight", "normal")

    # Labels (per-subplot override > default)
    x_label = sp.x_label if sp.x_label else style.get_x_label(x_domain)
    y_label = sp.y_label if sp.y_label else style.get_y_label()
    ax.set_xlabel(x_label, fontsize=label_size, fontfamily=font, fontweight=weight)
    ax.set_ylabel(y_label, fontsize=label_size, fontfamily=font, fontweight=weight)

    # Axis scales
    ax.set_xscale(sp.x_scale)
    ax.set_yscale(sp.y_scale)

    # Tick label formatting
    _apply_tick_format(ax.xaxis, sp.x_tick_format)
    _apply_tick_format(ax.yaxis, sp.y_tick_format)

    # Common styling
    ax.tick_params(labelsize=tick_size)
    # Sync tick label font with subplot/global font setting
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(font)
        label.set_fontsize(tick_size)
        label.set_fontweight(weight)
    ax.grid(style.grid_visible, alpha=style.grid_alpha, linestyle=style.grid_style)
    for spine in ax.spines.values():
        spine.set_linewidth(style.spine_width)
    ax.set_facecolor(style.subplot_facecolor)

    # Auto-range: tight union of curves + visible spectra (no extra padding)
    if curves and (sp.auto_x or sp.auto_y):
        x_all, y_all = _visible_data_extent(sp, state, subplot_key, x_domain, curves)
        if x_all is not None and y_all is not None and x_all.size > 0 and y_all.size > 0:
            if sp.auto_x:
                x_min, x_max = float(np.nanmin(x_all)), float(np.nanmax(x_all))
                if np.isfinite(x_min) and np.isfinite(x_max) and x_max > x_min:
                    ax.set_xlim(x_min, x_max)
            if sp.auto_y:
                y_min, y_max = float(np.nanmin(y_all)), float(np.nanmax(y_all))
                if np.isfinite(y_min) and np.isfinite(y_max) and y_max > y_min:
                    ax.set_ylim(y_min, y_max)

    # Apply manual limits if set
    if not sp.auto_x and sp.x_range:
        ax.set_xlim(sp.x_range)
    if not sp.auto_y and sp.y_range:
        ax.set_ylim(sp.y_range)

    # Cache the current rendered limits on the subplot so the settings
    # panel can seed its manual spinboxes with the value the user is
    # actually seeing when they uncheck "Auto".
    try:
        sp.last_auto_xlim = tuple(float(v) for v in ax.get_xlim())
        sp.last_auto_ylim = tuple(float(v) for v in ax.get_ylim())
    except Exception:
        pass

    # Frequency-axis tick style (decades / one-two-five / ruler /
    # custom). Applied AFTER set_xlim so the tick generator sees the
    # final bounds. Only meaningful when the X axis is frequency.
    if x_domain == "frequency":
        _apply_freq_tick_style(ax, sp)


def _apply_freq_tick_style(ax, sp):
    """Drive matplotlib ticks from ``sp.freq_tick_style``.

    Mirrors dc_cut's :func:`core.processing.ticks.make_freq_ticks` so
    Report Studio offers the same choices as the DC Cut properties
    panel: decades, one-two-five, custom (Hz list), and ruler.
    """
    style_name = str(getattr(sp, "freq_tick_style", "one-two-five"))
    # Historical alias from older prefs: "one_two_five".
    if style_name == "one_two_five":
        style_name = "one-two-five"
    if style_name not in ("decades", "one-two-five", "custom", "ruler"):
        return
    try:
        from dc_cut.core.processing.ticks import make_freq_ticks
    except ImportError:
        return
    import matplotlib.ticker as ticker

    try:
        xmin, xmax = (float(v) for v in ax.get_xlim())
    except (TypeError, ValueError):
        return
    if not (xmax > xmin) or xmin <= 0:
        # ``make_freq_ticks`` requires a positive log-friendly range.
        return
    custom = list(getattr(sp, "freq_custom_ticks", None) or [])
    ticks, labels = make_freq_ticks(style_name, xmin, xmax, custom=custom)
    if not ticks:
        return
    ax.xaxis.set_major_locator(ticker.FixedLocator(ticks))
    ax.xaxis.set_major_formatter(ticker.FixedFormatter(labels))


def _apply_tick_format(axis, fmt: str):
    """Apply tick label format: plain, sci, or eng."""
    import matplotlib.ticker as ticker
    if fmt == "sci":
        axis.set_major_formatter(ticker.ScalarFormatter(useMathText=True))
        axis.get_major_formatter().set_scientific(True)
    elif fmt == "eng":
        axis.set_major_formatter(ticker.EngFormatter())
    # "plain" — use default


# ── Spectrum colorbars ────────────────────────────────────────────────────

def _draw_spectrum_colorbars(
    fig: Figure,
    state: "SheetState",
    style: StyleConfig,
    bars_info: List[Dict],
) -> None:
    """Draw every spectrum colorbar after all subplots are finalised.

    Two modes:

    * **Combined figure-level bar** — when
      ``state.combined_spectrum_bar.enabled`` is ``True`` and every
      ``bars_info`` entry shares the same ``cmap``/``vmin``/``vmax``.
      One bar is attached to the side of the figure (growing the figure
      the same way the outside legend does).
    * **Per-subplot bars** — each curve's ``spectrum_colorbar*`` fields
      drive one cax attached to its own axes (legacy behaviour with
      global-typography sync and a scale knob).

    When the combined bar is requested but scales differ, a human-
    readable warning is pushed onto ``state._last_render_warnings`` so
    the main window can surface it in the status bar, and the per-
    subplot bars are drawn as the graceful fallback.
    """
    if not bars_info:
        return
    cfg = getattr(state, "combined_spectrum_bar", None)
    if cfg is not None and getattr(cfg, "enabled", False) and len(bars_info) >= 2:
        if _combined_bar_scales_match(bars_info):
            try:
                _build_combined_spectrum_bar(fig, cfg, bars_info, style)
                return
            except Exception:
                # Fall through to per-subplot bars if anything goes wrong.
                pass
        else:
            try:
                state._last_render_warnings.append(
                    "Combined spectrum colorbar skipped: the selected "
                    "spectra use different cmap / value ranges. "
                    "Per-subplot bars drawn instead."
                )
            except Exception:
                pass
    for info in bars_info:
        _draw_per_subplot_colorbar(info, style)


def _combined_bar_scales_match(bars_info: List[Dict]) -> bool:
    """Return ``True`` iff every bar has the same cmap + vmin + vmax."""
    import math
    cmap0 = bars_info[0].get("cmap", "")
    vmin0 = bars_info[0].get("vmin")
    vmax0 = bars_info[0].get("vmax")
    for info in bars_info[1:]:
        if str(info.get("cmap", "")) != str(cmap0):
            return False
        vmin = info.get("vmin")
        vmax = info.get("vmax")
        if vmin is None or vmax is None or vmin0 is None or vmax0 is None:
            return False
        try:
            if not math.isclose(float(vmin), float(vmin0), rel_tol=1e-9,
                                abs_tol=1e-12):
                return False
            if not math.isclose(float(vmax), float(vmax0), rel_tol=1e-9,
                                abs_tol=1e-12):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _resolve_bar_orientation(placement: str, orientation: str) -> str:
    """Map ("placement","orientation") → matplotlib orientation string."""
    if orientation in ("vertical", "horizontal"):
        return orientation
    # auto
    if placement in ("outside_top", "outside_bottom", "top", "bottom"):
        return "horizontal"
    return "vertical"


def _draw_per_subplot_colorbar(info: Dict, style: StyleConfig) -> None:
    """Attach one colorbar to the info['ax'] divider, font-synced."""
    curve = info.get("curve")
    im = info.get("im")
    ax = info.get("ax")
    if curve is None or im is None or ax is None:
        return
    if not getattr(curve, "spectrum_colorbar", False):
        return
    orient = getattr(curve, "spectrum_colorbar_orient", "vertical")
    position = getattr(curve, "spectrum_colorbar_position", "right")
    cb_label = getattr(curve, "spectrum_colorbar_label", "")
    scale = float(getattr(curve, "spectrum_colorbar_scale", 1.0) or 1.0)
    # Clamp to a sane range so a 0 or negative never explodes mpl.
    scale = max(0.1, min(scale, 5.0))

    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    base_pct = 3.0 if orient == "vertical" else 5.0
    size = f"{base_pct * scale:.2f}%"
    pad = 0.05 * scale
    cax = divider.append_axes(position, size=size, pad=pad)
    cb = ax.figure.colorbar(im, cax=cax, orientation=orient)

    font = getattr(style, "font_family", "sans-serif") or "sans-serif"
    weight = getattr(style, "font_weight", "normal") or "normal"
    base_fs = float(getattr(style, "legend_font_size", 9) or 9)
    fs = max(4.0, base_fs * scale)

    if cb_label:
        cb.set_label(
            cb_label, fontsize=fs, fontfamily=font, fontweight=weight,
        )
    cax.tick_params(labelsize=fs)
    for lbl in cax.get_xticklabels() + cax.get_yticklabels():
        lbl.set_fontfamily(font)
        lbl.set_fontsize(fs)
        lbl.set_fontweight(weight)


def _build_combined_spectrum_bar(
    fig: Figure,
    cfg,
    bars_info: List[Dict],
    style: StyleConfig,
) -> None:
    """Grow the figure and attach a single shared colorbar on the side.

    Mirrors :func:`packages.report_studio.legend.builder.build_combined_outside_legend`:
    add space on the chosen side, reposition existing axes, then add a
    figure-level cax occupying the new strip.
    """
    placement = str(getattr(cfg, "placement", "outside_right"))
    side = (
        placement.split("_", 1)[1]
        if placement.startswith("outside_")
        else placement
    )
    if side not in ("right", "left", "top", "bottom"):
        side = "right"
    orientation = _resolve_bar_orientation(
        placement, str(getattr(cfg, "orientation", "auto")),
    )
    scale = float(getattr(cfg, "scale", 1.0) or 1.0)
    scale = max(0.3, min(scale, 4.0))
    label = str(getattr(cfg, "label", "") or "")

    # How much of the figure the new bar strip should take.
    base_strip = 0.06  # 6% of the figure side for the cax + padding
    strip = base_strip * scale

    w, h = fig.get_size_inches()
    if side in ("right", "left"):
        grow = w * strip
        new_w = w + grow
        frac = grow / new_w
        fig.set_size_inches(new_w, h)
        # Shift existing axes to leave space on ``side``.
        _shift_existing_axes_horizontal(fig, frac, side)
        if side == "right":
            cax_rect = [1.0 - frac * 0.6, 0.15, frac * 0.35, 0.7]
        else:
            cax_rect = [frac * 0.25, 0.15, frac * 0.35, 0.7]
    else:  # top / bottom
        grow = h * strip
        new_h = h + grow
        frac = grow / new_h
        fig.set_size_inches(w, new_h)
        _shift_existing_axes_vertical(fig, frac, side)
        if side == "bottom":
            cax_rect = [0.15, frac * 0.25, 0.7, frac * 0.35]
        else:
            cax_rect = [0.15, 1.0 - frac * 0.6, 0.7, frac * 0.35]

    cax = fig.add_axes(cax_rect)
    im = bars_info[0]["im"]
    cb = fig.colorbar(im, cax=cax, orientation=orientation)

    font = getattr(style, "font_family", "sans-serif") or "sans-serif"
    weight = getattr(style, "font_weight", "normal") or "normal"
    base_fs = float(getattr(style, "legend_font_size", 9) or 9)
    fs = max(4.0, base_fs * scale)

    if label:
        cb.set_label(label, fontsize=fs, fontfamily=font, fontweight=weight)
    cax.tick_params(labelsize=fs)
    for lbl in cax.get_xticklabels() + cax.get_yticklabels():
        lbl.set_fontfamily(font)
        lbl.set_fontsize(fs)
        lbl.set_fontweight(weight)

    # Tag the cax so tests and later passes can identify it.
    try:
        cax._is_combined_spectrum_bar = True
    except Exception:
        pass


def _shift_existing_axes_horizontal(fig: Figure, frac: float, side: str) -> None:
    """Shrink every existing non-cax axes horizontally to free a strip.

    ``frac`` is the fraction of the NEW figure width the strip occupies.
    ``side`` is ``"right"`` or ``"left"``.
    """
    for ax in list(fig.axes):
        if getattr(ax, "_is_combined_spectrum_bar", False):
            continue
        try:
            pos = ax.get_position()
        except Exception:
            continue
        # Map the existing [x0, x1] window to the new width so subplots
        # keep their relative spacing and shrink by ``frac``.
        if side == "right":
            new_x0 = pos.x0 * (1.0 - frac)
            new_w = pos.width * (1.0 - frac)
        else:  # left
            new_x0 = frac + pos.x0 * (1.0 - frac)
            new_w = pos.width * (1.0 - frac)
        ax.set_position([new_x0, pos.y0, new_w, pos.height])


def _shift_existing_axes_vertical(fig: Figure, frac: float, side: str) -> None:
    """Shrink every existing non-cax axes vertically to free a strip."""
    for ax in list(fig.axes):
        if getattr(ax, "_is_combined_spectrum_bar", False):
            continue
        try:
            pos = ax.get_position()
        except Exception:
            continue
        if side == "top":
            new_y0 = pos.y0 * (1.0 - frac)
            new_h = pos.height * (1.0 - frac)
        else:  # bottom
            new_y0 = frac + pos.y0 * (1.0 - frac)
            new_h = pos.height * (1.0 - frac)
        ax.set_position([pos.x0, new_y0, pos.width, new_h])
