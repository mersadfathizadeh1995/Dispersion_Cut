"""Matplotlib canvas widget for the Report Studio.

Wraps a Figure + FigureCanvasQTAgg + NavigationToolbar inside a QScrollArea
so the preview renders at exact configured dimensions and scrolls if needed.
Supports mouse-wheel zoom and adjustable preview DPI.
"""
from __future__ import annotations

from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure

from .qt_compat import (
    QtWidgets, QtCore, Signal,
    AlignCenter, ScrollBarAsNeeded,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QScrollArea = QtWidgets.QScrollArea
QComboBox = QtWidgets.QComboBox
QLabel = QtWidgets.QLabel

DEFAULT_PREVIEW_DPI = 100
_ZOOM_FACTOR_IN = 0.85
_ZOOM_FACTOR_OUT = 1.0 / _ZOOM_FACTOR_IN


class CanvasView(QWidget):
    """Central canvas widget: toolbar on top, scrollable matplotlib canvas below.

    Features:
    - Mouse-wheel zoom around cursor position on all axes
    - Adjustable preview DPI via a dropdown in the toolbar row
    """

    preview_dpi_changed = Signal(int)

    def __init__(self, width_in: float = 8.0, height_in: float = 6.0,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._preview_dpi = DEFAULT_PREVIEW_DPI

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._figure = Figure(
            figsize=(width_in, height_in),
            dpi=self._preview_dpi,
            facecolor="white",
        )
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setFixedSize(
            int(width_in * self._preview_dpi),
            int(height_in * self._preview_dpi),
        )

        self._toolbar = NavigationToolbar(self._canvas, self)

        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(4)
        toolbar_row.addWidget(self._toolbar, stretch=1)

        toolbar_row.addWidget(QLabel("Preview:"))
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(["50", "75", "100", "150"])
        self._dpi_combo.setCurrentText(str(self._preview_dpi))
        self._dpi_combo.setFixedWidth(60)
        self._dpi_combo.setToolTip("Preview DPI (lower = faster rendering)")
        self._dpi_combo.currentTextChanged.connect(self._on_dpi_changed)
        toolbar_row.addWidget(self._dpi_combo)
        toolbar_row.addWidget(QLabel("DPI"))

        toolbar_container = QWidget()
        toolbar_container.setLayout(toolbar_row)
        layout.addWidget(toolbar_container)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(AlignCenter)
        self._scroll.setHorizontalScrollBarPolicy(ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(ScrollBarAsNeeded)

        layout.addWidget(self._scroll, stretch=1)

        self._canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvas:
        return self._canvas

    @property
    def preview_dpi(self) -> int:
        return self._preview_dpi

    def set_preview_dpi(self, dpi: int) -> None:
        """Change the preview DPI and resize accordingly."""
        if dpi == self._preview_dpi:
            return
        self._preview_dpi = dpi
        self._dpi_combo.blockSignals(True)
        self._dpi_combo.setCurrentText(str(dpi))
        self._dpi_combo.blockSignals(False)
        w, h = self._figure.get_size_inches()
        self._figure.set_dpi(dpi)
        self._canvas.setFixedSize(
            max(int(w * dpi), 200),
            max(int(h * dpi), 150),
        )
        self._canvas.draw_idle()

    def update_size(self, width_in: float, height_in: float) -> None:
        """Resize the figure and canvas widget to match new dimensions."""
        dpi = self._preview_dpi
        self._figure.set_size_inches(width_in, height_in)
        self._figure.set_dpi(dpi)
        w_px = max(int(width_in * dpi), 200)
        h_px = max(int(height_in * dpi), 150)
        self._canvas.setFixedSize(w_px, h_px)

    def refresh(self) -> None:
        """Redraw the canvas after the figure has been modified."""
        dpi = self._preview_dpi
        actual_w, actual_h = self._figure.get_size_inches()
        w_px = max(int(actual_w * dpi), 200)
        h_px = max(int(actual_h * dpi), 150)
        self._canvas.setFixedSize(w_px, h_px)
        self._canvas.draw_idle()

    # ── Internal slots ────────────────────────────────────────────

    def _on_dpi_changed(self, text: str) -> None:
        try:
            dpi = int(text)
        except ValueError:
            return
        if dpi < 10:
            return
        self._preview_dpi = dpi
        w, h = self._figure.get_size_inches()
        self._figure.set_dpi(dpi)
        self._canvas.setFixedSize(
            max(int(w * dpi), 200),
            max(int(h * dpi), 150),
        )
        self._canvas.draw_idle()
        self.preview_dpi_changed.emit(dpi)

    def _on_scroll_zoom(self, event) -> None:
        """Zoom in/out around cursor position on all axes."""
        if event.inaxes is None:
            return
        ax = event.inaxes
        factor = _ZOOM_FACTOR_IN if event.button == "up" else _ZOOM_FACTOR_OUT

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        x_scale = ax.get_xscale()
        y_scale = ax.get_yscale()

        if x_scale == "log" and xdata > 0:
            import math
            log_xmin = math.log10(xlim[0]) if xlim[0] > 0 else 0
            log_xmax = math.log10(xlim[1]) if xlim[1] > 0 else 1
            log_xc = math.log10(xdata)
            new_log_xmin = log_xc - (log_xc - log_xmin) * factor
            new_log_xmax = log_xc + (log_xmax - log_xc) * factor
            ax.set_xlim(10 ** new_log_xmin, 10 ** new_log_xmax)
        else:
            new_xmin = xdata - (xdata - xlim[0]) * factor
            new_xmax = xdata + (xlim[1] - xdata) * factor
            ax.set_xlim(new_xmin, new_xmax)

        if y_scale == "log" and ydata > 0:
            import math
            log_ymin = math.log10(ylim[0]) if ylim[0] > 0 else 0
            log_ymax = math.log10(ylim[1]) if ylim[1] > 0 else 1
            log_yc = math.log10(ydata)
            new_log_ymin = log_yc - (log_yc - log_ymin) * factor
            new_log_ymax = log_yc + (log_ymax - log_yc) * factor
            ax.set_ylim(10 ** new_log_ymin, 10 ** new_log_ymax)
        else:
            new_ymin = ydata - (ydata - ylim[0]) * factor
            new_ymax = ydata + (ylim[1] - ydata) * factor
            ax.set_ylim(new_ymin, new_ymax)

        self._canvas.draw_idle()
