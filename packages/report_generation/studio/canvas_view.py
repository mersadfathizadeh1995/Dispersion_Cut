"""Matplotlib canvas widget for the Report Studio.

Wraps a Figure + FigureCanvasQTAgg + NavigationToolbar inside a QScrollArea
so the preview renders at exact configured dimensions and scrolls if needed.
"""
from __future__ import annotations

from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure

from .qt_compat import (
    QtWidgets, AlignCenter, ScrollBarAsNeeded,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QScrollArea = QtWidgets.QScrollArea


PREVIEW_DPI = 100


class CanvasView(QWidget):
    """Central canvas widget: toolbar on top, scrollable matplotlib canvas below."""

    def __init__(self, width_in: float = 8.0, height_in: float = 6.0,
                 parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._figure = Figure(
            figsize=(width_in, height_in),
            dpi=PREVIEW_DPI,
            facecolor="white",
        )
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setFixedSize(
            int(width_in * PREVIEW_DPI),
            int(height_in * PREVIEW_DPI),
        )

        self._toolbar = NavigationToolbar(self._canvas, self)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(AlignCenter)
        self._scroll.setHorizontalScrollBarPolicy(ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(ScrollBarAsNeeded)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._scroll, stretch=1)

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvas:
        return self._canvas

    def update_size(self, width_in: float, height_in: float) -> None:
        """Resize the figure and canvas widget to match new dimensions."""
        self._figure.set_size_inches(width_in, height_in)
        self._figure.set_dpi(PREVIEW_DPI)
        w_px = max(int(width_in * PREVIEW_DPI), 200)
        h_px = max(int(height_in * PREVIEW_DPI), 150)
        self._canvas.setFixedSize(w_px, h_px)

    def refresh(self) -> None:
        """Redraw the canvas after the figure has been modified."""
        actual_w, actual_h = self._figure.get_size_inches()
        w_px = max(int(actual_w * PREVIEW_DPI), 200)
        h_px = max(int(actual_h * PREVIEW_DPI), 150)
        self._canvas.setFixedSize(w_px, h_px)
        self._canvas.draw_idle()
