"""
Plot canvas — QGraphicsView-based canvas with smooth zoom/pan.

Renders matplotlib Figure to a QPixmap and displays it in a
QGraphicsView for canvas-level zoom, pan, and fit modes.
"""

from __future__ import annotations

import io
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import numpy as np
import matplotlib
matplotlib.use("Agg")  # headless rendering — no Qt backend needed
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Vertical, PolicyExpanding,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from ...core.models import SheetState
    from ...rendering.style import StyleConfig


_ZOOM_STEP = 1.08   # per wheel-notch scale factor
_MIN_SCALE = 0.05
_MAX_SCALE = 20.0
_DEFAULT_CANVAS_DPI = 72  # low DPI for fast interactive rendering


# ── Qt compat helpers ─────────────────────────────────────────────────────

def _anchor_under_mouse():
    try:
        return QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
    except AttributeError:
        return QtWidgets.QGraphicsView.AnchorUnderMouse

def _no_anchor():
    try:
        return QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor
    except AttributeError:
        return QtWidgets.QGraphicsView.NoAnchor

def _scroll_hand_drag():
    try:
        return QtWidgets.QGraphicsView.DragMode.ScrollHandDrag
    except AttributeError:
        return QtWidgets.QGraphicsView.ScrollHandDrag

def _no_drag():
    try:
        return QtWidgets.QGraphicsView.DragMode.NoDrag
    except AttributeError:
        return QtWidgets.QGraphicsView.NoDrag

def _rubber_band_drag():
    try:
        return QtWidgets.QGraphicsView.DragMode.RubberBandDrag
    except AttributeError:
        return QtWidgets.QGraphicsView.RubberBandDrag

def _keep_aspect():
    try:
        return QtCore.Qt.AspectRatioMode.KeepAspectRatio
    except AttributeError:
        return QtCore.Qt.KeepAspectRatio

def _smooth_transform():
    try:
        return QtCore.Qt.TransformationMode.SmoothTransformation
    except AttributeError:
        return QtCore.Qt.SmoothTransformation


# ── Canvas toolbar ────────────────────────────────────────────────────────

class CanvasToolbar(QtWidgets.QToolBar):
    """Toolbar with canvas-level zoom/pan/fit buttons."""

    fit_all = Signal()
    fit_width = Signal()
    fit_height = Signal()
    zoom_in = Signal()
    zoom_out = Signal()
    home = Signal()
    export = Signal()

    def __init__(self, parent=None):
        super().__init__("Canvas", parent)
        self.setIconSize(QtCore.QSize(18, 18))

        self._add_btn("Fit All", "Fit figure to view", self.fit_all)
        self._add_btn("Fit W", "Fit to width", self.fit_width)
        self._add_btn("Fit H", "Fit to height", self.fit_height)
        self.addSeparator()
        self._add_btn("Zoom +", "Zoom in", self.zoom_in)
        self._add_btn("Zoom −", "Zoom out", self.zoom_out)
        self._add_btn("Home", "Reset view", self.home)
        self.addSeparator()
        self._add_btn("Export", "Export image", self.export)

    def _add_btn(self, text: str, tip: str, signal):
        btn = QtWidgets.QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.clicked.connect(signal.emit)
        self.addWidget(btn)


# ── Graphics view with smooth zoom/pan ────────────────────────────────────

class _ZoomPanView(QtWidgets.QGraphicsView):
    """QGraphicsView with mouse-wheel zoom and middle/right-click pan."""

    subplot_at = Signal(str)  # emitted on left-click with subplot key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing
                           if hasattr(QtGui.QPainter.RenderHint, "Antialiasing")
                           else QtGui.QPainter.Antialiasing, True)
        self.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform
                           if hasattr(QtGui.QPainter.RenderHint, "SmoothPixmapTransform")
                           else QtGui.QPainter.SmoothPixmapTransform, True)

        self.setTransformationAnchor(_anchor_under_mouse())
        self.setResizeAnchor(_anchor_under_mouse())
        self.setDragMode(_scroll_hand_drag())
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                                         if hasattr(QtCore.Qt.ScrollBarPolicy, "ScrollBarAlwaysOff")
                                         else QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
                                           if hasattr(QtCore.Qt.ScrollBarPolicy, "ScrollBarAlwaysOff")
                                           else QtCore.Qt.ScrollBarAlwaysOff)
        self._current_scale = 1.0

    # -- zoom -----------------------------------------------------------------

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = _ZOOM_STEP if delta > 0 else 1.0 / _ZOOM_STEP
        new_scale = self._current_scale * factor
        if _MIN_SCALE <= new_scale <= _MAX_SCALE:
            self.scale(factor, factor)
            self._current_scale = new_scale

    def step_zoom(self, direction: int):
        """Programmatic zoom: direction > 0 → in, < 0 → out."""
        factor = _ZOOM_STEP if direction > 0 else 1.0 / _ZOOM_STEP
        new_scale = self._current_scale * factor
        if _MIN_SCALE <= new_scale <= _MAX_SCALE:
            self.scale(factor, factor)
            self._current_scale = new_scale

    def reset_zoom(self):
        self.resetTransform()
        self._current_scale = 1.0

    def fit_all(self, margin: int = 20):
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            return
        rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(rect, _keep_aspect())
        self._current_scale = self.transform().m11()

    def fit_width(self, margin: int = 20):
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            return
        vp = self.viewport().rect()
        desired_w = vp.width() - 2 * margin
        if rect.width() > 0:
            s = desired_w / rect.width()
            self.resetTransform()
            self.scale(s, s)
            self._current_scale = s

    def fit_height(self, margin: int = 20):
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            return
        vp = self.viewport().rect()
        desired_h = vp.height() - 2 * margin
        if rect.height() > 0:
            s = desired_h / rect.height()
            self.resetTransform()
            self.scale(s, s)
            self._current_scale = s


# ── PlotCanvas (public widget) ────────────────────────────────────────────

class PlotCanvas(QtWidgets.QWidget):
    """
    Central canvas widget: renders matplotlib figure as QPixmap in a
    QGraphicsView with smooth zoom/pan.

    Signals
    -------
    curve_clicked(str)
        Emitted when a curve is clicked (uid).
    subplot_clicked(str)
        Emitted when a subplot area is clicked (subplot key).
    """

    curve_clicked = Signal(str)
    subplot_clicked = Signal(str)

    def __init__(self, parent=None, dpi: int = _DEFAULT_CANVAS_DPI):
        super().__init__(parent)

        self._dpi = dpi
        self._figure = Figure(figsize=(10, 7), dpi=dpi)
        FigureCanvasAgg(self._figure)  # attach Agg backend for rendering

        # Graphics view + scene
        self._scene = QtWidgets.QGraphicsScene(self)
        self._view = _ZoomPanView(self)
        self._view.setScene(self._scene)

        self._pixmap_item: Optional[QtWidgets.QGraphicsPixmapItem] = None

        # Toolbar
        self._toolbar = CanvasToolbar(self)
        self._toolbar.fit_all.connect(self._view.fit_all)
        self._toolbar.fit_width.connect(self._view.fit_width)
        self._toolbar.fit_height.connect(self._view.fit_height)
        self._toolbar.zoom_in.connect(lambda: self._view.step_zoom(1))
        self._toolbar.zoom_out.connect(lambda: self._view.step_zoom(-1))
        self._toolbar.home.connect(self._view.reset_zoom)
        self._toolbar.export.connect(lambda: self.curve_clicked.emit("__export__"))

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._view)

        # Subplot bounding boxes: key → (x, y, w, h) in pixel coords
        self._subplot_boxes: Dict[str, Tuple[float, float, float, float]] = {}
        self._axes: Dict[str, "Axes"] = {}
        self._selected_uid: str = ""

        # Click detection
        self._view.viewport().installEventFilter(self)

    # ── Public API ────────────────────────────────────────────────────

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def axes(self) -> Dict[str, "Axes"]:
        return self._axes

    def set_axes(self, axes: Dict[str, "Axes"]):
        self._axes = axes

    def render(self, sheet: "SheetState", style: "StyleConfig",
               selected_uid: str = "", quality: str = "draft"):
        """Render a SheetState and display as QPixmap."""
        from ...rendering.renderer import render_sheet

        self._selected_uid = selected_uid

        # Use canvas DPI from sheet state for interactive rendering
        canvas_dpi = getattr(sheet, "canvas_dpi", _DEFAULT_CANVAS_DPI) or _DEFAULT_CANVAS_DPI
        self._dpi = canvas_dpi
        self._figure.set_dpi(canvas_dpi)
        self._figure.set_size_inches(sheet.figure_width, sheet.figure_height)
        self._axes = render_sheet(self._figure, sheet, style,
                                  selected_uid=selected_uid,
                                  quality=quality)

        # Record subplot bounding boxes (in figure pixel coords)
        self._store_subplot_boxes()

        # Render figure to QPixmap
        self._update_pixmap()

    def set_selected(self, uid: str):
        self._selected_uid = uid

    def refresh(self):
        """Redraw with current figure state."""
        self._update_pixmap()

    def export_image(self, path: str, dpi: int = 300):
        """Save figure at the specified DPI."""
        self._figure.savefig(path, dpi=dpi, bbox_inches="tight")

    # ── Internal rendering ────────────────────────────────────────────

    def _update_pixmap(self):
        """Render self._figure → QPixmap → scene using direct Agg buffer."""
        try:
            canvas = self._figure.canvas
            canvas.draw()
            buf = canvas.buffer_rgba()
            w, h = canvas.get_width_height()
            qimg = QtGui.QImage(bytes(buf), w, h, 4 * w,
                                QtGui.QImage.Format.Format_RGBA8888)
            pixmap = QtGui.QPixmap.fromImage(qimg)
        except Exception:
            # Fallback to PNG encoding if direct buffer fails
            buf = io.BytesIO()
            self._figure.savefig(buf, format="png", dpi=self._dpi,
                                 bbox_inches="tight",
                                 facecolor=self._figure.get_facecolor())
            buf.seek(0)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(buf.read())

        if self._pixmap_item is not None:
            self._scene.removeItem(self._pixmap_item)
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(QtCore.QRectF(pixmap.rect().toRectF()
                                                if hasattr(pixmap.rect(), "toRectF")
                                                else QtCore.QRectF(pixmap.rect())))

    def _store_subplot_boxes(self):
        """Store each axes' bounding box in figure pixel coords."""
        self._subplot_boxes.clear()
        renderer = self._figure.canvas.get_renderer() if hasattr(self._figure.canvas, "get_renderer") else None
        fig_w, fig_h = self._figure.get_size_inches()
        dpi = self._figure.dpi
        pw, ph = fig_w * dpi, fig_h * dpi

        for key, ax in self._axes.items():
            bbox = ax.get_position()
            x = bbox.x0 * pw
            y = (1 - bbox.y1) * ph   # flip y (figure coords → pixel coords)
            w = bbox.width * pw
            h = bbox.height * ph
            self._subplot_boxes[key] = (x, y, w, h)

    # ── Click detection (event filter on viewport) ────────────────────

    def eventFilter(self, obj, event):
        if obj == self._view.viewport():
            etype = event.type()
            # Qt6 vs Qt5 enum
            press = (QtCore.QEvent.Type.MouseButtonPress
                     if hasattr(QtCore.QEvent.Type, "MouseButtonPress")
                     else QtCore.QEvent.MouseButtonPress)
            if etype == press:
                btn = event.button()
                left = (QtCore.Qt.MouseButton.LeftButton
                        if hasattr(QtCore.Qt.MouseButton, "LeftButton")
                        else QtCore.Qt.LeftButton)
                if btn == left:
                    try:
                        pos = event.position().toPoint()
                    except AttributeError:
                        pos = event.pos()
                    scene_pt = self._view.mapToScene(pos)
                    self._detect_subplot_click(scene_pt.x(), scene_pt.y())
        return super().eventFilter(obj, event)

    def _detect_subplot_click(self, sx: float, sy: float):
        """Map scene pixel to subplot bounding box."""
        for key, (bx, by, bw, bh) in self._subplot_boxes.items():
            if bx <= sx <= bx + bw and by <= sy <= by + bh:
                self.subplot_clicked.emit(key)
                return

    # ── Show event: fit on first display ──────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._pixmap_item is not None:
            QtCore.QTimer.singleShot(50, self._view.fit_all)
