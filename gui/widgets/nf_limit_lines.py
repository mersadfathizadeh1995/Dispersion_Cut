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
from matplotlib.transforms import blended_transform_factory

try:
    from dc_cut.core.processing.nearfield.range_derivation import (
        DerivedLimitSet,
        DerivedLine,
    )
except Exception:  # pragma: no cover -- module may not exist yet
    DerivedLimitSet = None  # type: ignore[assignment]
    DerivedLine = None  # type: ignore[assignment]


LimitsStyleFn = Callable[[Tuple[int, str, str]], Tuple[bool, str]]


# ─── internal: preserve axes limits across overlay draws ────────────
#
# The λ-hyperbola curve ``V = λ * f`` is sampled across a frequency
# range padded one decade past the current xlim (so it reaches the
# visible frame even after later zooms).  On a fresh or nearly-empty
# axes, matplotlib's autoscale can pick up those padded endpoints and
# blow the y-axis up to values like 200 000 m/s.  Callers wrap the
# overlay pass in :func:`_preserve_limits` to snapshot both axes'
# limits and autoscale state on entry, then restore them on exit.

from contextlib import contextmanager


@contextmanager
def _preserve_limits(*axes):
    """Freeze ``(xlim, ylim, autoscale_on_x, autoscale_on_y)`` for every
    given axes while overlays are drawn, then restore on exit.

    Any axes that is ``None`` is skipped so callers can pass a pair
    like ``(ax_freq, ax_wave)`` without guarding for missing axes.
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


# ─── internal: smart-label placement after zoom / pan ───────────────
#
# λ-curve labels on ax_freq must track ``V = λ * f``, so they cannot
# use a blended transform.  Instead we tag the text artist with the
# info we need (``_nf_lam``) and wire a one-time xlim/ylim callback on
# the axes that recomputes the position whenever the view changes.
# The vertical lines' labels use blended transforms directly so they
# always stay at a fixed fraction of the visible axes.

def _reposition_lambda_labels(ax) -> None:
    """Move every ``_nf_kind='lambda_curve'`` text on *ax* to a good
    spot inside the current ``xlim`` / ``ylim`` rectangle."""
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
        # Solve ``V = λ * f`` inside the visible rectangle, pick the
        # portion that is simultaneously inside ``xlim`` and ``ylim``,
        # and place the label at 30 % along that visible arc.
        f_lo = max(xmin_safe, ymin / lam if ymin > 0 else xmin_safe)
        f_hi = min(xmax, ymax / lam)
        if f_hi <= f_lo:
            # Curve doesn't intersect the visible rectangle; pin the
            # label to the nearer corner so it stays on-screen.
            f_pick = 0.5 * (xmin_safe + xmax)
            v_pick = np.clip(lam * f_pick, ymin, ymax)
        else:
            # Log-space 30 % (closer to the top-left where curves start).
            t = 0.30
            f_pick = float(10.0 ** (
                np.log10(f_lo) + t * (np.log10(f_hi) - np.log10(f_lo))
            ))
            v_pick = float(lam * f_pick)
        try:
            txt.set_position((f_pick, v_pick))
        except Exception:
            pass


def _ensure_lambda_label_callback(ax) -> None:
    """Attach ``_reposition_lambda_labels`` to *ax* at most once."""
    if getattr(ax, "_nf_lambda_cb_attached", False):
        return
    try:
        ax.callbacks.connect("xlim_changed", lambda a: _reposition_lambda_labels(a))
        ax.callbacks.connect("ylim_changed", lambda a: _reposition_lambda_labels(a))
        ax._nf_lambda_cb_attached = True
    except Exception:
        pass


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

    # Guard against autoscale blow-up caused by the padded λ-hyperbola
    # sample range (see :func:`_preserve_limits` docstring).
    with _preserve_limits(ax_freq, ax_wave):
        for ln in limit_set.lines:
            # Zone entries are rendered separately by ``draw_zone_bands``
            # / ``draw_zone_labels``.  The Limit Lines tree still owns
            # their visibility / color state, but this line drawer skips
            # them entirely.
            if ln.kind == "zone":
                continue
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
                custom = (getattr(ln, "custom_label", "") or "").strip()
                _draw_single_limit(
                    ax_freq, ax_wave, float(ln.value),
                    color=color, linestyle=linestyle, linewidth=linewidth,
                    alpha=alpha, show_labels=show_labels,
                    label_fontsize=label_fontsize, zorder=zorder,
                    artists_out=artists, nf_key=key,
                    custom_label=custom or None,
                )
            else:  # "freq"
                custom = (getattr(ln, "custom_label", "") or "").strip()
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
                    custom_label=custom or None,
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
    with _preserve_limits(ax_freq, ax_wave):
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
    custom_label: Optional[str] = None,
) -> None:
    """Draw a single vertical f-line on ``ax_freq``.

    We use ``ax_freq.axvline`` (spans the whole axes regardless of
    ``ylim``) and place the label with a blended transform whose x is
    in data coordinates and y in axes coordinates (0–1).  This pins
    the label to a fixed fraction of the visible height, so it always
    stays on-screen when the user pans or zooms.
    """
    ln = ax_freq.axvline(
        f_edge,
        linestyle=linestyle, color=color,
        lw=linewidth, alpha=alpha,
        zorder=zorder, label="_nf_limit",
    )
    _tag(ln, nf_key)
    artists_out.append(ln)
    if show_labels:
        trans = blended_transform_factory(ax_freq.transData, ax_freq.transAxes)
        label_text = (
            f" {custom_label}"
            if custom_label
            else f" {tag}={f_edge:g} Hz"
        )
        txt = ax_freq.text(
            f_edge, 0.04,
            label_text,
            fontsize=label_fontsize, color=color,
            alpha=min(1.0, alpha + 0.2),
            rotation=90, ha="left", va="bottom",
            zorder=zorder + 1,
            transform=trans,
        )
        _tag(txt, nf_key)
        artists_out.append(txt)
        # When a NACD-style custom label is present (e.g. "NACD = 1"),
        # mirror the actual frequency value on the OPPOSITE side of
        # the vertical line so the user can read both the criterion
        # and the resulting f at a glance.  Per user request — see
        # plan.md Phase A.
        if custom_label:
            txt_freq = ax_freq.text(
                f_edge, 0.04,
                f" f={f_edge:g} Hz ",
                fontsize=label_fontsize, color=color,
                alpha=min(1.0, alpha + 0.2),
                rotation=90, ha="right", va="bottom",
                zorder=zorder + 1,
                transform=trans,
            )
            _tag(txt_freq, nf_key)
            artists_out.append(txt_freq)


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
    custom_label: Optional[str] = None,
) -> None:
    """Draw one constant-wavelength hyperbola on ``ax_freq`` and the
    matching vertical on ``ax_wave``.

    * The ``f`` domain of the curve is padded one decade past the
      current ``xlim`` on each side and ``scalex=scaley=False`` is
      passed to ``plot`` so the curve always reaches the visible
      frame even after later autoscaling.  Clip-on at the axes trims
      the excess for display.
    * The λ-curve label is tagged with ``_nf_kind='lambda_curve'``
      and ``_nf_lam=lam`` so a single pair of axes callbacks can
      reposition every such label on zoom / pan (see
      :func:`_ensure_lambda_label_callback`).
    * The vertical λ-line on ``ax_wave`` uses
      :func:`matplotlib.transforms.blended_transform_factory` to pin
      its label to a fixed fraction of the visible height.
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

    ln_w = ax_wave.axvline(
        lam, linestyle=linestyle,
        color=color, lw=linewidth, alpha=alpha,
        zorder=zorder, label="_nf_limit",
    )
    _tag(ln_w, nf_key)
    artists_out.append(ln_w)

    if show_labels:
        # Initial seed position: 30 % along the visible arc.  The
        # xlim/ylim callback keeps it inside the viewport on pan/zoom.
        y_lo_f, y_hi_f = ax_freq.get_ylim()
        f_lo_vis = max(fmin, y_lo_f / lam if y_lo_f > 0 else fmin)
        f_hi_vis = min(fmax, y_hi_f / lam) if y_hi_f > 0 else fmax
        if f_hi_vis > f_lo_vis:
            t = 0.30
            f_pos = float(10.0 ** (
                np.log10(f_lo_vis) + t * (np.log10(f_hi_vis) - np.log10(f_lo_vis))
            ))
        else:
            f_pos = float(np.sqrt(fmin * fmax))
        v_pos = float(lam * f_pos)

        lam_label = (
            f"  \u03bb={lam:.0f} m ({custom_label})"
            if custom_label
            else f"  \u03bb={lam:.0f} m"
        )
        txt_f = ax_freq.text(
            f_pos, v_pos, lam_label,
            fontsize=label_fontsize, color=color, alpha=0.95,
            rotation=30, rotation_mode="anchor",
            ha="left", va="bottom", zorder=zorder + 1,
            fontweight="bold",
        )
        # Tag the text so the view-change callback can find it.
        try:
            setattr(txt_f, "_nf_kind", "lambda_curve")
            setattr(txt_f, "_nf_lam", float(lam))
        except Exception:
            pass
        _tag(txt_f, nf_key)
        artists_out.append(txt_f)
        _ensure_lambda_label_callback(ax_freq)

        trans_w = blended_transform_factory(
            ax_wave.transData, ax_wave.transAxes
        )
        wav_label = (
            f"  \u03bb={lam:.0f} m ({custom_label})"
            if custom_label
            else f"  \u03bb={lam:.0f} m"
        )
        txt_w = ax_wave.text(
            lam, 0.96,
            wav_label,
            fontsize=label_fontsize, color=color, alpha=0.95,
            rotation=90, ha="left", va="top", zorder=zorder + 1,
            fontweight="bold",
            transform=trans_w,
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
