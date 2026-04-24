"""Line selection tool for dispersion curve editing.

Provides interactive 2-click line drawing with directional deletion
(remove points above or below the drawn line).
"""
from __future__ import annotations

from typing import Optional, Callable, Tuple, List
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrow
from matplotlib.backend_bases import MouseEvent


class LineSelector:
    """Interactive two-click line selector with direction indicator.
    
    User clicks two points to define a line. An arrow indicator shows
    which side of the line will be affected (deleted). Third click or
    keyboard confirms the operation.
    
    Parameters
    ----------
    ax : Axes
        The matplotlib axes to attach to.
    on_select : callable
        Callback with signature (x1, y1, x2, y2, side) where side is
        'above' or 'below' indicating which side to delete.
    line_color : str
        Color of the preview line.
    arrow_color : str
        Color of the direction arrow.
    """
    
    def __init__(
        self,
        ax: Axes,
        on_select: Callable[[float, float, float, float, str], None],
        line_color: str = "#e74c3c",
        arrow_color: str = "#e74c3c",
        controller=None,
    ):
        self.ax = ax
        self.on_select = on_select
        self.line_color = line_color
        self.arrow_color = arrow_color
        # Optional back-reference to the controller so we can reach
        # ``controller.blit_manager`` for fast preview redraws. When
        # ``None`` we silently fall back to ``canvas.draw_idle``.
        self.controller = controller
        
        self._active = False
        self._p1: Optional[Tuple[float, float]] = None
        self._p2: Optional[Tuple[float, float]] = None
        self._side: str = "above"
        
        self._preview_line: Optional[Line2D] = None
        self._arrow: Optional[FancyArrow] = None
        self._arrow_keep: Optional[FancyArrow] = None
        self._endpoint_markers: List[Line2D] = []
        # Hidden spectrum reference for the hide-during-gesture fallback
        # (active only when blitting is turned off).
        self._hidden_spectrum = None
        
        self._cid_press: Optional[int] = None
        self._cid_motion: Optional[int] = None
        self._cid_key: Optional[int] = None

    # ------------------------------------------------------------------
    # Performance helpers
    # ------------------------------------------------------------------
    def _blit_manager(self):
        bm = getattr(self.controller, "blit_manager", None)
        if bm is None:
            return None
        try:
            from dc_cut.services.prefs import get_pref

            if not bool(get_pref("spectrum_perf_use_blitting", True)):
                return None
        except Exception:
            pass
        return bm if bm.is_enabled() else None

    def _register_animated(self, artist) -> None:
        bm = self._blit_manager()
        if bm is not None and artist is not None:
            bm.register_animated(artist)

    def _unregister_animated(self, artist) -> None:
        bm = getattr(self.controller, "blit_manager", None)
        if bm is not None and artist is not None:
            bm.unregister_animated(artist)

    def _request_redraw(self) -> None:
        """Repaint the canvas via blitting when enabled, else fall back
        to ``draw_idle`` (optionally throttled by the blit manager).
        """
        bm = self._blit_manager()
        if bm is not None and bm.blit_update():
            return
        # Fall back to draw_idle; use the throttled variant if available
        # so the non-blitting path still feels snappy.
        manager = getattr(self.controller, "blit_manager", None)
        if manager is not None:
            manager.request_draw_idle()
            return
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass

    def _begin_gesture(self) -> None:
        """Hide the spectrum for the duration of a drag when blitting
        is unavailable but the user still opted into the fallback.
        Re-shown by :meth:`_end_gesture`.
        """
        if self._blit_manager() is not None:
            return  # Blitting handles this automatically.
        try:
            from dc_cut.services.prefs import get_pref

            if not bool(get_pref("spectrum_perf_hide_during_gesture", True)):
                return
        except Exception:
            return
        layer = self._find_active_spectrum_layer()
        if layer is None or layer.spectrum_image is None:
            return
        try:
            if layer.spectrum_image.get_visible():
                layer.spectrum_image.set_visible(False)
                self._hidden_spectrum = layer.spectrum_image
                try:
                    self.ax.figure.canvas.draw_idle()
                except Exception:
                    pass
        except Exception:
            self._hidden_spectrum = None

    def _end_gesture(self) -> None:
        if self._hidden_spectrum is None:
            return
        try:
            self._hidden_spectrum.set_visible(True)
        except Exception:
            pass
        self._hidden_spectrum = None
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass

    def _find_active_spectrum_layer(self):
        ctrl = self.controller
        if ctrl is None:
            return None
        try:
            model = getattr(ctrl, "_layers_model", None)
            if model is None:
                return None
            for layer in getattr(model, "layers", []):
                if getattr(layer, "spectrum_visible", False) and getattr(
                    layer, "spectrum_image", None
                ) is not None:
                    return layer
        except Exception:
            return None
        return None
    
    @property
    def active(self) -> bool:
        return self._active
    
    def activate(self) -> None:
        """Enable the line selector tool."""
        if self._active:
            return
        self._active = True
        self._p1 = None
        self._p2 = None
        canvas = self.ax.figure.canvas
        self._cid_press = canvas.mpl_connect("button_press_event", self._on_press)
        self._cid_motion = canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._cid_key = canvas.mpl_connect("key_press_event", self._on_key)
    
    def deactivate(self) -> None:
        """Disable the line selector tool."""
        if not self._active:
            return
        self._active = False
        canvas = self.ax.figure.canvas
        if self._cid_press is not None:
            canvas.mpl_disconnect(self._cid_press)
        if self._cid_motion is not None:
            canvas.mpl_disconnect(self._cid_motion)
        if self._cid_key is not None:
            canvas.mpl_disconnect(self._cid_key)
        self._cid_press = None
        self._cid_motion = None
        self._cid_key = None
        self._clear_preview()
        self._p1 = None
        self._p2 = None
    
    def cancel(self) -> None:
        """Cancel current selection without triggering callback."""
        self._clear_preview()
        self._p1 = None
        self._p2 = None
        self._end_gesture()
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass
    
    def toggle_side(self) -> None:
        """Toggle between 'above' and 'below' deletion direction."""
        self._side = "below" if self._side == "above" else "above"
        if self._p1 is not None and self._p2 is not None:
            self._update_arrow()
            self._request_redraw()
    
    def _on_press(self, event: MouseEvent) -> None:
        if event.inaxes != self.ax:
            return
        if event.button != 1:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        if self._p1 is None:
            self._p1 = (x, y)
            self._begin_gesture()
            self._draw_endpoint(x, y)
        elif self._p2 is None:
            self._p2 = (x, y)
            self._draw_endpoint(x, y)
            self._draw_line()
            self._update_arrow()
        else:
            self._confirm_selection()
    
    def _on_motion(self, event: MouseEvent) -> None:
        if not self._active or self._p1 is None or self._p2 is not None:
            return
        if event.inaxes != self.ax:
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        self._draw_preview_line(self._p1[0], self._p1[1], x, y)
    
    def _on_key(self, event) -> None:
        if not self._active:
            return
        key = getattr(event, "key", "")
        if key == "escape":
            self.cancel()
        elif key in ("up", "down", "d"):
            self.toggle_side()
        elif key in ("enter", "return", " "):
            if self._p1 is not None and self._p2 is not None:
                self._confirm_selection()
    
    def _confirm_selection(self) -> None:
        if self._p1 is None or self._p2 is None:
            return
        x1, y1 = self._p1
        x2, y2 = self._p2
        side = self._side
        self._clear_preview()
        self._p1 = None
        self._p2 = None
        self._end_gesture()
        if self.on_select is not None:
            self.on_select(x1, y1, x2, y2, side)
    
    def _draw_endpoint(self, x: float, y: float) -> None:
        marker = self.ax.plot(
            x, y, "o",
            color=self.line_color,
            markersize=8,
            markerfacecolor="white",
            markeredgewidth=2,
            zorder=100,
        )[0]
        self._endpoint_markers.append(marker)
        self._register_animated(marker)
        self._request_redraw()
    
    def _draw_preview_line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        if self._preview_line is not None:
            self._preview_line.set_data([x1, x2], [y1, y2])
        else:
            self._preview_line = self.ax.plot(
                [x1, x2], [y1, y2],
                color=self.line_color,
                linestyle="--",
                linewidth=2,
                zorder=99,
            )[0]
            self._register_animated(self._preview_line)
        self._request_redraw()
    
    def _draw_line(self) -> None:
        if self._p1 is None or self._p2 is None:
            return
        x1, y1 = self._p1
        x2, y2 = self._p2
        if self._preview_line is not None:
            self._preview_line.set_data([x1, x2], [y1, y2])
            self._preview_line.set_linestyle("-")
        else:
            self._preview_line = self.ax.plot(
                [x1, x2], [y1, y2],
                color=self.line_color,
                linestyle="-",
                linewidth=2,
                zorder=99,
            )[0]
            self._register_animated(self._preview_line)
        self._request_redraw()
    
    def _update_arrow(self) -> None:
        """Draw arrows perpendicular to line indicating deletion direction.
        
        Shows two arrows: solid red for delete side, faded gray for keep side.
        Uses display coordinates for proper perpendicular appearance.
        """
        if self._p1 is None or self._p2 is None:
            return
        
        # Clear existing arrows
        if self._arrow is not None:
            try:
                self._arrow.remove()
            except Exception:
                pass
            self._arrow = None
        if hasattr(self, '_arrow_keep') and self._arrow_keep is not None:
            try:
                self._arrow_keep.remove()
            except Exception:
                pass
            self._arrow_keep = None
        
        x1, y1 = self._p1
        x2, y2 = self._p2
        
        # Convert to display coordinates for proper perpendicular
        trans = self.ax.transData
        p1_disp = trans.transform((x1, y1))
        p2_disp = trans.transform((x2, y2))
        
        mid_disp = ((p1_disp[0] + p2_disp[0]) / 2, (p1_disp[1] + p2_disp[1]) / 2)
        
        # Perpendicular in display space
        dx_disp = p2_disp[0] - p1_disp[0]
        dy_disp = p2_disp[1] - p1_disp[1]
        length_disp = np.sqrt(dx_disp**2 + dy_disp**2)
        if length_disp < 1e-10:
            return
        
        # Unit perpendicular vector (rotate 90 degrees)
        nx_disp = -dy_disp / length_disp
        ny_disp = dx_disp / length_disp
        
        # Arrow length in pixels
        arrow_len_px = 40
        
        # Compute arrow endpoints in display coords
        if self._side == "above":
            # Delete direction (solid red)
            del_end_disp = (mid_disp[0] + nx_disp * arrow_len_px, mid_disp[1] + ny_disp * arrow_len_px)
            # Keep direction (faded)
            keep_end_disp = (mid_disp[0] - nx_disp * arrow_len_px, mid_disp[1] - ny_disp * arrow_len_px)
        else:
            # Delete direction (solid red)
            del_end_disp = (mid_disp[0] - nx_disp * arrow_len_px, mid_disp[1] - ny_disp * arrow_len_px)
            # Keep direction (faded)
            keep_end_disp = (mid_disp[0] + nx_disp * arrow_len_px, mid_disp[1] + ny_disp * arrow_len_px)
        
        # Convert back to data coordinates
        inv_trans = trans.inverted()
        mid_data = inv_trans.transform(mid_disp)
        del_end_data = inv_trans.transform(del_end_disp)
        keep_end_data = inv_trans.transform(keep_end_disp)
        
        # Draw delete arrow (solid red)
        self._arrow = self.ax.annotate(
            "",
            xy=del_end_data,
            xytext=mid_data,
            arrowprops=dict(
                arrowstyle="-|>",
                color=self.arrow_color,
                lw=2.5,
                mutation_scale=18,
            ),
            zorder=100,
        )
        
        # Draw keep arrow (faded gray, thinner)
        self._arrow_keep = self.ax.annotate(
            "",
            xy=keep_end_data,
            xytext=mid_data,
            arrowprops=dict(
                arrowstyle="-|>",
                color="#888888",
                lw=1.5,
                mutation_scale=12,
                alpha=0.5,
            ),
            zorder=99,
        )

        self._register_animated(self._arrow)
        self._register_animated(self._arrow_keep)
        self._request_redraw()
    
    def _clear_preview(self) -> None:
        if self._preview_line is not None:
            self._unregister_animated(self._preview_line)
            try:
                self._preview_line.remove()
            except Exception:
                pass
            self._preview_line = None
        
        if self._arrow is not None:
            self._unregister_animated(self._arrow)
            try:
                self._arrow.remove()
            except Exception:
                pass
            self._arrow = None
        
        if hasattr(self, '_arrow_keep') and self._arrow_keep is not None:
            self._unregister_animated(self._arrow_keep)
            try:
                self._arrow_keep.remove()
            except Exception:
                pass
            self._arrow_keep = None
        
        for marker in self._endpoint_markers:
            self._unregister_animated(marker)
            try:
                marker.remove()
            except Exception:
                pass
        self._endpoint_markers.clear()
