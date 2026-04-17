"""Reusable NF limit-line drawing helpers.

Draws constant-wavelength curves (``V = \u03bb \u00d7 f``) and vertical
frequency-band boundaries on the frequency and wavelength axes, with
per-line visibility and color.  The modern entry point is
:func:`draw_nf_limits_from_set`, which consumes a
:class:`~dc_cut.core.processing.nearfield.range_derivation.DerivedLimitSet`
and a ``LimitsStyleFn`` callable supplying ``(visible, color)`` per line
key.

The legacy :func:`draw_nf_limit_lines` helper is kept as a thin wrapper
so existing call-sites that haven't migrated to the set-based API keep
working.

Artists are tagged with ``artist.nf_key = (band_index, kind, role)`` so
the UI can hide/show a single line without a full redraw.
"""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import numpy as np

try:
    from dc_cut.core.processing.nearfield.range_derivation import (
        DerivedLimitSet,
        DerivedLine,
    )
except Exception:  # pragma: no cover -- module may not exist yet
    DerivedLimitSet = None  # type: ignore[assignment]
    DerivedLine = None  # type: ignore[assignment]


LimitsStyleFn = Callable[[Tuple[int, str, str]], Tuple[bool, str]]


# ─── public: set-based API ──────────────────────────────────────────

def draw_nf_limits_from_set(
    ax_freq,
    ax_wave,
    limit_set: "DerivedLimitSet",
    style_fn: Optional[LimitsStyleFn] = None,
    *,
    linestyle: str = "--",
    linewidth: float = 1.5,
    alpha: float = 0.85,
    show_labels: bool = True,
    label_fontsize: int = 10,
    zorder: int = 5,
    default_color: str = "black",
) -> list:
    """Draw every visible line in ``limit_set``.

    Parameters
    ----------
    ax_freq, ax_wave
        Matplotlib axes for the frequency and wavelength views.
    limit_set
        The derived limit set (see
        :mod:`dc_cut.core.processing.nearfield.range_derivation`).
    style_fn
        Optional callable that, given the line's ``(band_index, kind,
        role)`` tuple, returns ``(visible: bool, color: str)``.  When
        ``None``, every valid line is drawn with ``default_color``.
    """
    artists: list = []
    if limit_set is None or not limit_set.lines:
        try:
            ax_freq.figure.canvas.draw_idle()
        except Exception:
            pass
        return artists

    for ln in limit_set.lines:
        if not ln.valid or ln.value <= 0:
            continue
        key = (ln.band_index, ln.kind, ln.role)
        if style_fn is not None:
            try:
                visible, color = style_fn(key)
            except Exception:
                visible, color = True, default_color
        else:
            visible, color = True, default_color
        if not visible:
            continue
        if ln.kind == "lambda":
            _draw_single_limit(
                ax_freq, ax_wave, float(ln.value),
                color=color, linestyle=linestyle, linewidth=linewidth,
                alpha=alpha, show_labels=show_labels,
                label_fontsize=label_fontsize, zorder=zorder,
                artists_out=artists, nf_key=key,
            )
        else:  # "freq"
            _draw_freq_marker(
                ax_freq, float(ln.value),
                tag=f"f_{ln.role}",
                color=color,
                linestyle=":" if ln.source == "user" else linestyle,
                linewidth=max(1.0, linewidth - 0.3),
                alpha=min(alpha, 0.75),
                show_labels=show_labels,
                label_fontsize=max(8, label_fontsize - 1),
                zorder=zorder,
                artists_out=artists, nf_key=key,
            )

    try:
        ax_freq.figure.canvas.draw_idle()
    except Exception:
        pass
    return artists


# ─── public: legacy scalar API (kept for callers not yet migrated) ──

def draw_nf_limit_lines(
    ax_freq,
    ax_wave,
    lambda_max: float,
    lambda_min: Optional[float] = None,
    *,
    freq_bands: Optional[List[Tuple[float, float]]] = None,
    color: str = "black",
    linestyle: str = "--",
    linewidth: float = 1.5,
    alpha: float = 0.85,
    show_labels: bool = True,
    label_fontsize: int = 10,
    zorder: int = 5,
) -> list:
    """Scalar-value entry point (legacy).

    Prefer :func:`draw_nf_limits_from_set` for new code.
    """
    artists: list = []
    for lam in [lambda_max, lambda_min]:
        if lam is None or lam <= 0:
            continue
        _draw_single_limit(
            ax_freq, ax_wave, float(lam),
            color=color, linestyle=linestyle, linewidth=linewidth,
            alpha=alpha, show_labels=show_labels,
            label_fontsize=label_fontsize, zorder=zorder,
            artists_out=artists, nf_key=None,
        )
    if freq_bands:
        for bi, (lo, hi) in enumerate(freq_bands):
            for role, f_edge in (("min", lo), ("max", hi)):
                if f_edge is None or f_edge <= 0:
                    continue
                _draw_freq_marker(
                    ax_freq, float(f_edge), tag=f"f_{role}",
                    color=color, linestyle=":",
                    linewidth=max(1.0, linewidth - 0.3),
                    alpha=min(alpha, 0.7),
                    show_labels=show_labels,
                    label_fontsize=max(8, label_fontsize - 1),
                    zorder=zorder,
                    artists_out=artists, nf_key=(bi, "freq", role),
                )
    try:
        ax_freq.figure.canvas.draw_idle()
    except Exception:
        pass
    return artists


# ─── internals ──────────────────────────────────────────────────────

def _tag(artist, key) -> None:
    if key is not None:
        try:
            setattr(artist, "nf_key", key)
        except Exception:
            pass


def _draw_freq_marker(
    ax_freq,
    f_edge: float,
    *,
    tag: str,
    color: str,
    linestyle: str,
    linewidth: float,
    alpha: float,
    zorder: int,
    show_labels: bool,
    label_fontsize: int,
    artists_out: list,
    nf_key,
) -> None:
    """Draw a single vertical f-line on ``ax_freq`` spanning the full
    current y-range.  The y-span is set 10× wider than the current
    ``ylim`` so later autoscaling can't shrink the line short of the
    axis edges (clip_on=True at the axes handles the visible trim).
    """
    y_lo, y_hi = ax_freq.get_ylim()
    y_span = max(y_hi - y_lo, 1.0)
    y_lo_ext = y_lo - 5 * y_span
    y_hi_ext = y_hi + 5 * y_span
    ln = ax_freq.plot(
        [f_edge, f_edge], [y_lo_ext, y_hi_ext],
        linestyle=linestyle, color=color,
        lw=linewidth, alpha=alpha,
        zorder=zorder, label="_nf_limit",
        scalex=False, scaley=False,
    )[0]
    _tag(ln, nf_key)
    artists_out.append(ln)
    if show_labels:
        txt = ax_freq.text(
            f_edge, y_lo + 0.04 * (y_hi - y_lo),
            f" {tag}={f_edge:g} Hz",
            fontsize=label_fontsize, color=color,
            alpha=min(1.0, alpha + 0.2),
            rotation=90, ha="left", va="bottom",
            zorder=zorder + 1,
        )
        _tag(txt, nf_key)
        artists_out.append(txt)


def _draw_single_limit(
    ax_freq,
    ax_wave,
    lam: float,
    *,
    color: str,
    linestyle: str,
    linewidth: float,
    alpha: float,
    show_labels: bool,
    label_fontsize: int,
    zorder: int,
    artists_out: list,
    nf_key,
) -> None:
    """Draw one constant-wavelength hyperbola on ``ax_freq`` and the
    matching vertical on ``ax_wave``.

    The ``f`` domain is padded one decade past the current ``xlim``
    on each side and ``scalex=scaley=False`` is passed to ``plot`` so
    the curve always reaches the visible frame even after later
    autoscaling.  Clip-on at the axes trims the excess for display.
    """
    fmin, fmax = ax_freq.get_xlim()
    fmin = max(fmin, 1e-6)
    fmax = max(fmax, fmin * 1.1)
    f_lo = fmin / 10.0
    f_hi = fmax * 10.0
    f_curve = np.logspace(np.log10(f_lo), np.log10(f_hi), 600)
    v_curve = lam * f_curve

    ln_f = ax_freq.plot(
        f_curve, v_curve, linestyle=linestyle,
        color=color, lw=linewidth, alpha=alpha,
        zorder=zorder, label="_nf_limit",
        scalex=False, scaley=False,
    )[0]
    _tag(ln_f, nf_key)
    artists_out.append(ln_f)

    y_lo, y_hi = ax_wave.get_ylim()
    y_span = max(y_hi - y_lo, 1.0)
    y_lo_ext = y_lo - 5 * y_span
    y_hi_ext = y_hi + 5 * y_span
    ln_w = ax_wave.plot(
        [lam, lam], [y_lo_ext, y_hi_ext], linestyle=linestyle,
        color=color, lw=linewidth, alpha=alpha,
        zorder=zorder, label="_nf_limit",
        scalex=False, scaley=False,
    )[0]
    _tag(ln_w, nf_key)
    artists_out.append(ln_w)

    if show_labels:
        y_lo_f, y_hi_f = ax_freq.get_ylim()
        vis = (v_curve >= y_lo_f) & (v_curve <= y_hi_f)
        if np.any(vis):
            vis_idx = np.where(vis)[0]
            pick = vis_idx[len(vis_idx) // 4]
            f_pos = f_curve[pick]
            v_pos = v_curve[pick]
        else:
            f_pos = f_curve[len(f_curve) // 5]
            v_pos = v_curve[len(v_curve) // 5]
        txt_f = ax_freq.text(
            f_pos, v_pos, f"  \u03bb={lam:.0f} m",
            fontsize=label_fontsize, color=color, alpha=0.95,
            rotation=30, rotation_mode="anchor",
            ha="left", va="bottom", zorder=zorder + 1,
            fontweight="bold",
        )
        _tag(txt_f, nf_key)
        artists_out.append(txt_f)

        txt_w = ax_wave.text(
            lam, y_lo + 0.92 * (y_hi - y_lo),
            f"  \u03bb={lam:.0f} m",
            fontsize=label_fontsize, color=color, alpha=0.95,
            rotation=90, ha="left", va="top", zorder=zorder + 1,
            fontweight="bold",
        )
        _tag(txt_w, nf_key)
        artists_out.append(txt_w)


def clear_nf_limit_lines(artists: list) -> None:
    """Remove every NF limit-line artist from the canvas."""
    for art in artists:
        try:
            art.remove()
        except Exception:
            pass
    artists.clear()


def set_nf_limit_visibility(artists: list, key, visible: bool) -> None:
    """Set visibility for every artist tagged with ``nf_key == key``."""
    for art in artists:
        if getattr(art, "nf_key", None) == key:
            try:
                art.set_visible(bool(visible))
            except Exception:
                pass


__all__ = [
    "draw_nf_limits_from_set",
    "draw_nf_limit_lines",
    "clear_nf_limit_lines",
    "set_nf_limit_visibility",
    "LimitsStyleFn",
]
