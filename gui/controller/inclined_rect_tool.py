"""Inclined rectangle selection tool for dispersion curve editing.

Provides interactive 3-click rectangle drawing:
1. Click first point (P1) - first corner of one edge
2. Click second point (P2) - second corner of the same edge (defines P1-P2 edge)
3. Move mouse to expand rectangle perpendicular to P1-P2 edge
4. Click third point (P3) - confirms the width/expansion

The rectangle expands from the P1-P2 edge toward the cursor position.
"""
from __future__ import annotations

from typing import Optional, Callable, Tuple, List
import numpy as np
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from matplotlib.backend_bases import MouseEvent


def compute_rect_from_edge_and_cursor(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    cursor: Tuple[float, float],
    ax: Axes,
) -> np.ndarray:
    """Compute rectangle corners from one edge (P1-P2) and cursor position.
    
    The rectangle has P1-P2 as one edge and expands toward the cursor.
    The width is determined by the perpendicular distance from cursor to P1-P2 line.
    
    Parameters
    ----------
    p1, p2 : tuple
        Two points (x, y) in data coordinates defining one edge.
    cursor : tuple
        Cursor position (x, y) in data coordinates - determines expansion direction and width.
    ax : Axes
        The axes for coordinate transformation.
    
    Returns
    -------
    np.ndarray
        Array of shape (4, 2) with corner coordinates in data space.
        Order: [P1, P2, P2+offset, P1+offset] for proper polygon.
    """
    # Transform to display coordinates for consistent visual behavior
    trans = ax.transData
    p1_disp = np.array(trans.transform(p1))
    p2_disp = np.array(trans.transform(p2))
    cursor_disp = np.array(trans.transform(cursor))
    
    # Edge direction vector in display space
    edge_vec = p2_disp - p1_disp
    edge_length = np.linalg.norm(edge_vec)
    
    if edge_length < 1e-10:
        # Degenerate case - return small square around p1
        inv_trans = trans.inverted()
        size = 10.0
        corners_disp = np.array([
            p1_disp + [-size, -size],
            p1_disp + [size, -size],
            p1_disp + [size, size],
            p1_disp + [-size, size],
        ])
        return np.array([inv_trans.transform(c) for c in corners_disp])
    
    # Unit edge direction
    edge_unit = edge_vec / edge_length
    
    # Perpendicular unit vector (rotate 90 degrees counterclockwise)
    perp_unit = np.array([-edge_unit[1], edge_unit[0]])
    
    # Vector from P1 to cursor
    to_cursor = cursor_disp - p1_disp
    
    # Project cursor onto perpendicular direction to get signed distance
    perp_dist = np.dot(to_cursor, perp_unit)
    
    # Offset vector (perpendicular direction * distance)
    offset = perp_unit * perp_dist
    
    # Compute 4 corners in display coordinates
    # P1, P2 are the original edge; P1+offset, P2+offset are the opposite edge
    corners_disp = np.array([
        p1_disp,              # P1
        p2_disp,              # P2
        p2_disp + offset,     # P2 + offset (opposite corner of P2)
        p1_disp + offset,     # P1 + offset (opposite corner of P1)
    ])
    
    # Transform back to data coordinates
    inv_trans = trans.inverted()
    corners_data = np.array([inv_trans.transform(c) for c in corners_disp])
    
    return corners_data


class InclinedRectTool:
    """Interactive three-click inclined rectangle selector.
    
    User clicks two points (P1, P2) to define one edge of the rectangle.
    Then moves mouse to expand the rectangle perpendicular to that edge.
    Third click confirms - the rectangle persists on the figure.
    
    Parameters
    ----------
    ax : Axes
        The matplotlib axes to attach to.
    on_confirm : callable
        Callback with signature (corners: np.ndarray, patch: Polygon) called
        when rectangle is confirmed. corners is shape (4, 2) in data coords.
    line_color : str
        Color of the preview line and rectangle.
    rect_color : str
        Edge color of the confirmed rectangle.
    """
    
    def __init__(
        self,
        ax: Axes,
        on_confirm: Callable[[np.ndarray, Polygon], None],
        line_color: str = "#9b59b6",  # Purple to distinguish from line tool
        rect_color: str = "black",
        controller=None,
    ):
        self.ax = ax
        self.on_confirm = on_confirm
        self.line_color = line_color
        self.rect_color = rect_color
        self.controller = controller
        
        self._active = False
        self._p1: Optional[Tuple[float, float]] = None
        self._p2: Optional[Tuple[float, float]] = None
        self._cursor: Optional[Tuple[float, float]] = None  # Current cursor for preview
        
        # Preview artists (temporary, removed on confirm/cancel)
        self._preview_line: Optional[Line2D] = None
        self._preview_rect: Optional[Polygon] = None
        self._endpoint_markers: List[Line2D] = []
        self._hidden_spectrum = None
        
        # Event connection IDs
        self._cid_press: Optional[int] = None
        self._cid_motion: Optional[int] = None
        self._cid_key: Optional[int] = None

    # ------------------------------------------------------------------
    # Performance helpers (mirrors LineSelector's fast-path wiring)
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
        bm = self._blit_manager()
        if bm is not None and bm.blit_update():
            return
        manager = getattr(self.controller, "blit_manager", None)
        if manager is not None:
            manager.request_draw_idle()
            return
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass

    def _begin_gesture(self) -> None:
        if self._blit_manager() is not None:
            return
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
        """Enable the inclined rectangle tool."""
        if self._active:
            return
        self._active = True
        self._p1 = None
        self._p2 = None
        self._cursor = None
        canvas = self.ax.figure.canvas
        self._cid_press = canvas.mpl_connect("button_press_event", self._on_press)
        self._cid_motion = canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._cid_key = canvas.mpl_connect("key_press_event", self._on_key)
    
    def deactivate(self) -> None:
        """Disable the inclined rectangle tool."""
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
        self._cursor = None
    
    def cancel(self) -> None:
        """Cancel current selection without confirming."""
        self._clear_preview()
        self._p1 = None
        self._p2 = None
        self._cursor = None
        self._end_gesture()
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass
    
    def _on_press(self, event: MouseEvent) -> None:
        if event.inaxes != self.ax:
            return
        if event.button != 1:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        if self._p1 is None:
            # First click - set first corner of the edge
            self._p1 = (x, y)
            self._begin_gesture()
            self._draw_endpoint(x, y)
        elif self._p2 is None:
            # Second click - set second corner of the edge (completes P1-P2 edge)
            self._p2 = (x, y)
            self._draw_endpoint(x, y)
            self._draw_edge_line()
            # Now waiting for mouse movement to show rectangle preview
        else:
            # Third click - confirm the rectangle with current cursor position
            self._cursor = (x, y)
            self._confirm_selection()
    
    def _on_motion(self, event: MouseEvent) -> None:
        if not self._active:
            return
        if event.inaxes != self.ax:
            return
        
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return
        
        if self._p1 is not None and self._p2 is None:
            # First point set, show preview line to cursor
            self._draw_preview_line(self._p1[0], self._p1[1], x, y)
        elif self._p1 is not None and self._p2 is not None:
            # Both edge points set, show rectangle preview expanding toward cursor
            self._cursor = (x, y)
            self._update_preview_rect()
    
    def _on_key(self, event) -> None:
        if not self._active:
            return
        key = getattr(event, "key", "")
        
        if key == "escape":
            self.cancel()
        elif key in ("enter", "return", " "):
            # Confirm with current cursor position
            if self._p1 is not None and self._p2 is not None and self._cursor is not None:
                self._confirm_selection()
    
    def _confirm_selection(self) -> None:
        """Confirm the rectangle and call callback."""
        if self._p1 is None or self._p2 is None or self._cursor is None:
            return
        
        # Compute final corners from edge and cursor position
        corners = compute_rect_from_edge_and_cursor(
            self._p1, self._p2, self._cursor, self.ax
        )
        
        # Create persistent patch (dashed black line like regular rectangles)
        patch = Polygon(
            corners,
            closed=True,
            edgecolor=self.rect_color,
            facecolor='none',
            linestyle='--',
            linewidth=1.5,
            zorder=50,
        )
        self.ax.add_patch(patch)
        
        # Clear preview artists
        self._clear_preview()
        
        # Reset state for next rectangle
        self._p1 = None
        self._p2 = None
        self._cursor = None
        self._end_gesture()
        
        # Call callback with corners and patch
        if self.on_confirm is not None:
            self.on_confirm(corners, patch)
        
        try:
            self.ax.figure.canvas.draw_idle()
        except Exception:
            pass
    
    def _draw_endpoint(self, x: float, y: float) -> None:
        """Draw marker at click point."""
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
        """Draw or update preview line."""
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
    
    def _draw_edge_line(self) -> None:
        """Draw solid line for the confirmed edge (P1-P2)."""
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
    
    def _update_preview_rect(self) -> None:
        """Update or create preview rectangle based on edge and cursor."""
        if self._p1 is None or self._p2 is None or self._cursor is None:
            return
        
        corners = compute_rect_from_edge_and_cursor(
            self._p1, self._p2, self._cursor, self.ax
        )
        
        if self._preview_rect is not None:
            self._preview_rect.set_xy(corners)
        else:
            self._preview_rect = Polygon(
                corners,
                closed=True,
                edgecolor=self.line_color,
                facecolor=self.line_color,
                alpha=0.2,
                linestyle='-',
                linewidth=2,
                zorder=98,
            )
            self.ax.add_patch(self._preview_rect)
            self._register_animated(self._preview_rect)
        
        self._request_redraw()
    
    def _clear_preview(self) -> None:
        """Remove all preview artists."""
        if self._preview_line is not None:
            self._unregister_animated(self._preview_line)
            try:
                self._preview_line.remove()
            except Exception:
                pass
            self._preview_line = None
        
        if self._preview_rect is not None:
            self._unregister_animated(self._preview_rect)
            try:
                self._preview_rect.remove()
            except Exception:
                pass
            self._preview_rect = None
        
        for marker in self._endpoint_markers:
            self._unregister_animated(marker)
            try:
                marker.remove()
            except Exception:
                pass
        self._endpoint_markers.clear()


def polygon_mask(
    x: np.ndarray,
    y: np.ndarray,
    corners: np.ndarray,
) -> np.ndarray:
    """Return boolean mask of points inside a polygon.
    
    Parameters
    ----------
    x, y : np.ndarray
        Point coordinates to test.
    corners : np.ndarray
        Polygon vertices, shape (N, 2).
    
    Returns
    -------
    np.ndarray
        Boolean array, True for points inside polygon.
    """
    from matplotlib.path import Path
    
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    
    if x.size == 0:
        return np.array([], dtype=bool)
    
    points = np.column_stack([x, y])
    path = Path(corners)
    return path.contains_points(points)


def remove_in_polygon_freq(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    corners: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points inside polygon in freq-vel space.
    
    Parameters
    ----------
    v, f, w : np.ndarray
        Velocity, frequency, wavelength arrays.
    corners : np.ndarray
        Polygon vertices in (frequency, velocity) space.
    
    Returns
    -------
    Tuple of filtered (v, f, w) arrays.
    """
    if len(f) == 0:
        return v, f, w
    mask = polygon_mask(f, v, corners)
    keep = ~mask
    return v[keep], f[keep], w[keep]


def remove_in_polygon_wave(
    v: np.ndarray,
    f: np.ndarray,
    w: np.ndarray,
    corners: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Remove points inside polygon in wave-vel space.
    
    Parameters
    ----------
    v, f, w : np.ndarray
        Velocity, frequency, wavelength arrays.
    corners : np.ndarray
        Polygon vertices in (wavelength, velocity) space.
    
    Returns
    -------
    Tuple of filtered (v, f, w) arrays.
    """
    if len(w) == 0:
        return v, f, w
    mask = polygon_mask(w, v, corners)
    keep = ~mask
    return v[keep], f[keep], w[keep]
