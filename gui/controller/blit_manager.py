"""Matplotlib blitting helper for the DC-cut canvas.

Interactive tools (line cut, inclined rectangle cut, add-mode preview)
make the canvas feel heavy when a spectrum is loaded because every
mouse-move triggers a full :meth:`Figure.canvas.draw_idle` — which in
turn re-renders the spectrum heatmap even though only the preview
geometry changed.

This manager implements the standard matplotlib
"restore background + draw animated artists + blit" pattern so the
spectrum, axes, and ticks are captured once and reused for every
preview update until something static actually changes (resize, axis
limit change, background redraw).

Activation is fully driven by the preferences:

* ``spectrum_perf_use_blitting`` toggles the fast path at runtime.
* ``spectrum_perf_draw_throttle_ms`` collapses bursts of ``draw_idle``
  requests into a single deferred redraw via :class:`QTimer`.

Callers only need to:

1. Register the preview artists they want to animate
   (:meth:`register_animated`).
2. Call :meth:`blit_update` after each motion event instead of
   :meth:`Figure.canvas.draw_idle`.
3. Call :meth:`unregister_animated` on cancel / confirm so the artist
   stops being treated as dynamic.

Everything degrades gracefully: when the backend doesn't support
``copy_from_bbox`` or an exception escapes the fast path, the manager
falls back to a throttled ``draw_idle`` so the visible state is always
correct even if it's not blazing fast.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Set

try:
    from PySide6 import QtCore

    _HAS_QT = True
except Exception:  # pragma: no cover - Qt is expected but we stay tolerant
    QtCore = None  # type: ignore[assignment]
    _HAS_QT = False


class BlitManager:
    """Manage a cached canvas background + animated artists for fast
    preview redraws.

    Parameters
    ----------
    canvas
        The matplotlib ``FigureCanvas`` owning the paint surface. Must
        expose ``copy_from_bbox``, ``restore_region``, ``blit`` and
        ``draw_idle`` for the blitting path to work; anything missing
        disables the manager automatically.
    axes
        Iterable of axes whose artists should be captured as the static
        background. The union of their bounding boxes is captured on
        every ``draw_event``.
    """

    def __init__(self, canvas, axes: Iterable) -> None:
        self.canvas = canvas
        self.axes: List = [ax for ax in axes if ax is not None]
        self._background = None
        self._animated: "Set" = set()
        self._enabled: bool = True
        self._throttle_ms: int = 0
        self._pending_timer: Optional["QtCore.QTimer"] = None

        self._cids: List[int] = []
        self._ax_cids: List = []

        try:
            self._cids.append(canvas.mpl_connect("draw_event", self._on_draw))
        except Exception:
            # Non-Agg backends without draw_event still work via the
            # fallback path in blit_update.
            pass
        try:
            self._cids.append(canvas.mpl_connect("resize_event", self._on_resize))
        except Exception:
            pass

        for ax in self.axes:
            try:
                self._ax_cids.append(
                    (ax, ax.callbacks.connect("xlim_changed", self._on_axes_changed))
                )
                self._ax_cids.append(
                    (ax, ax.callbacks.connect("ylim_changed", self._on_axes_changed))
                )
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_enabled(self, enabled: bool) -> None:
        """Flip the fast path on or off live. When disabled every call to
        :meth:`blit_update` falls back to ``draw_idle``.
        """
        self._enabled = bool(enabled)
        if not self._enabled:
            self._background = None

    def is_enabled(self) -> bool:
        return bool(self._enabled)

    def set_throttle_ms(self, ms: int) -> None:
        """Coalesce ``draw_idle`` bursts to at most one every ``ms``
        milliseconds. ``0`` disables throttling.
        """
        ms = max(0, int(ms or 0))
        self._throttle_ms = ms
        if ms == 0:
            timer = self._pending_timer
            if timer is not None:
                try:
                    timer.stop()
                except Exception:
                    pass
            self._pending_timer = None
            return

        if _HAS_QT and self._pending_timer is None:
            timer = QtCore.QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_draw_idle)
            self._pending_timer = timer

        if self._pending_timer is not None:
            try:
                self._pending_timer.setInterval(ms)
            except Exception:
                pass

    def register_animated(self, artist) -> None:
        """Mark ``artist`` as animated so it is drawn on top of the
        cached background on every :meth:`blit_update`.
        """
        if artist is None:
            return
        try:
            artist.set_animated(True)
        except Exception:
            pass
        self._animated.add(artist)

    def unregister_animated(self, artist) -> None:
        """Stop treating ``artist`` as animated and restore the static
        paint path.
        """
        if artist is None:
            return
        self._animated.discard(artist)
        try:
            artist.set_animated(False)
        except Exception:
            pass

    def clear_animated(self) -> None:
        """Forget every registered animated artist (best-effort)."""
        for artist in list(self._animated):
            self.unregister_animated(artist)

    def invalidate(self) -> None:
        """Drop the cached background. The next real draw will recapture
        it.
        """
        self._background = None

    def update_background(self) -> None:
        """Capture the static background right now. Called automatically
        on ``draw_event``; callers can also invoke it directly when
        they know the static content just changed (e.g. spectrum
        re-render).
        """
        if not self._enabled:
            return
        try:
            self._background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        except Exception:
            self._background = None

    def blit_update(self) -> bool:
        """Restore the background and redraw animated artists. Returns
        ``True`` when the fast path succeeded; ``False`` falls back to
        a ``draw_idle`` (optionally throttled).

        Any exception inside matplotlib flips the return value to
        ``False`` so the caller knows to fall back.
        """
        if not self._enabled or self._background is None:
            self._schedule_draw_idle()
            return False

        try:
            self.canvas.restore_region(self._background)
            for artist in self._animated:
                try:
                    ax = getattr(artist, "axes", None)
                    if ax is not None and hasattr(ax, "draw_artist"):
                        ax.draw_artist(artist)
                except Exception:
                    continue
            self.canvas.blit(self.canvas.figure.bbox)
            return True
        except Exception:
            self._background = None
            self._schedule_draw_idle()
            return False

    def request_draw_idle(self) -> None:
        """Public shortcut for callers that want the throttled draw path
        regardless of blitting state — useful after preference changes.
        """
        self._schedule_draw_idle()

    def dispose(self) -> None:
        """Disconnect matplotlib callbacks. Called on controller teardown."""
        for cid in self._cids:
            try:
                self.canvas.mpl_disconnect(cid)
            except Exception:
                pass
        for ax, cid in self._ax_cids:
            try:
                ax.callbacks.disconnect(cid)
            except Exception:
                pass
        self._cids.clear()
        self._ax_cids.clear()
        if self._pending_timer is not None:
            try:
                self._pending_timer.stop()
            except Exception:
                pass
            self._pending_timer = None
        self._background = None
        self._animated.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_draw(self, event) -> None:  # pragma: no cover - matplotlib cb
        # A full draw just happened; stash the new background so the
        # next blit reuses it.
        try:
            self._background = self.canvas.copy_from_bbox(self.canvas.figure.bbox)
        except Exception:
            self._background = None

    def _on_resize(self, event) -> None:  # pragma: no cover - matplotlib cb
        self._background = None

    def _on_axes_changed(self, *_args, **_kwargs) -> None:  # pragma: no cover
        # Axis limits drive pixel coordinates, so the cached region is
        # invalid after a zoom / pan.
        self._background = None

    def _schedule_draw_idle(self) -> None:
        if self._throttle_ms > 0 and self._pending_timer is not None:
            try:
                if not self._pending_timer.isActive():
                    self._pending_timer.start(self._throttle_ms)
                return
            except Exception:
                # Fall through to immediate draw.
                pass
        self._flush_draw_idle()

    def _flush_draw_idle(self) -> None:
        try:
            self.canvas.draw_idle()
        except Exception:
            pass


__all__ = ["BlitManager"]
