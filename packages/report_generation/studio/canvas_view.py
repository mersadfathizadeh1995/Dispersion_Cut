"""Matplotlib canvas widget for the Report Studio.

Wraps a Figure + FigureCanvasQTAgg + NavigationToolbar inside a QScrollArea.
Explicit +/- buttons control image-level zoom. Middle-click drag pans the
scroll area. Matplotlib toolbar handles per-axis data zoom/pan as usual.
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
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel

DEFAULT_PREVIEW_DPI = 100

try:
    _MID_BUTTON = QtCore.Qt.MiddleButton
except AttributeError:
    _MID_BUTTON = QtCore.Qt.MouseButton.MiddleButton

try:
    _MOUSE_MOVE = QtCore.QEvent.MouseMove
except AttributeError:
    _MOUSE_MOVE = QtCore.QEvent.Type.MouseMove

try:
    _MOUSE_PRESS = QtCore.QEvent.MouseButtonPress
except AttributeError:
    _MOUSE_PRESS = QtCore.QEvent.Type.MouseButtonPress

try:
    _MOUSE_RELEASE = QtCore.QEvent.MouseButtonRelease
except AttributeError:
    _MOUSE_RELEASE = QtCore.QEvent.Type.MouseButtonRelease


class CanvasView(QWidget):
    """Central canvas widget: toolbar on top, scrollable matplotlib canvas below.

    Zoom is controlled via explicit +/- buttons in the toolbar.
    Middle-click drag pans the scroll area.
    Matplotlib NavigationToolbar handles per-axis data zoom/pan.
    """

    preview_dpi_changed = Signal(int)

    def __init__(self, width_in: float = 8.0, height_in: float = 6.0,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._preview_dpi = DEFAULT_PREVIEW_DPI
        self._zoom_level = 1.0
        self._mid_drag = False
        self._mid_drag_origin = QtCore.QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._figure = Figure(
            figsize=(width_in, height_in),
            dpi=self._preview_dpi,
            facecolor="white",
        )
        self._canvas = FigureCanvas(self._figure)
        self._update_canvas_pixel_size()

        self._toolbar = NavigationToolbar(self._canvas, self)

        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(4)
        toolbar_row.addWidget(self._toolbar, stretch=1)

        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setFixedSize(26, 26)
        self._zoom_out_btn.setToolTip("Zoom out (image)")
        self._zoom_out_btn.clicked.connect(lambda: self._apply_zoom(1.0 / 1.25))
        toolbar_row.addWidget(self._zoom_out_btn)

        self._zoom_reset_btn = QPushButton("1:1")
        self._zoom_reset_btn.setFixedSize(32, 26)
        self._zoom_reset_btn.setToolTip("Reset zoom to 100%")
        self._zoom_reset_btn.clicked.connect(self.reset_zoom)
        toolbar_row.addWidget(self._zoom_reset_btn)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedSize(26, 26)
        self._zoom_in_btn.setToolTip("Zoom in (image)")
        self._zoom_in_btn.clicked.connect(lambda: self._apply_zoom(1.25))
        toolbar_row.addWidget(self._zoom_in_btn)

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

        self._scroll.viewport().installEventFilter(self)
        layout.addWidget(self._scroll, stretch=1)

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
        if dpi == self._preview_dpi:
            return
        self._preview_dpi = dpi
        self._dpi_combo.blockSignals(True)
        self._dpi_combo.setCurrentText(str(dpi))
        self._dpi_combo.blockSignals(False)
        self._figure.set_dpi(dpi)
        self._update_canvas_pixel_size()
        self._canvas.draw_idle()

    def update_size(self, width_in: float, height_in: float) -> None:
        self._figure.set_size_inches(width_in, height_in)
        self._figure.set_dpi(self._preview_dpi)
        self._update_canvas_pixel_size()

    def refresh(self) -> None:
        self._update_canvas_pixel_size()
        self._canvas.draw_idle()

    def reset_zoom(self) -> None:
        self._zoom_level = 1.0
        self._update_canvas_pixel_size()

    def _apply_zoom(self, factor: float) -> None:
        self._zoom_level = max(0.25, min(4.0, self._zoom_level * factor))
        self._update_canvas_pixel_size()

    def _update_canvas_pixel_size(self) -> None:
        w, h = self._figure.get_size_inches()
        dpi = self._preview_dpi
        z = self._zoom_level
        self._canvas.setFixedSize(
            max(int(w * dpi * z), 200),
            max(int(h * dpi * z), 150),
        )

    def eventFilter(self, obj, event) -> bool:
        """Middle-click drag to pan the scroll area."""
        if obj is not self._scroll.viewport():
            return super().eventFilter(obj, event)

        etype = event.type()
        if etype == _MOUSE_PRESS and event.button() == _MID_BUTTON:
            self._mid_drag = True
            self._mid_drag_origin = event.globalPos()
            return True
        if etype == _MOUSE_RELEASE and event.button() == _MID_BUTTON:
            self._mid_drag = False
            return True
        if etype == _MOUSE_MOVE and self._mid_drag:
            delta = event.globalPos() - self._mid_drag_origin
            self._mid_drag_origin = event.globalPos()
            h_bar = self._scroll.horizontalScrollBar()
            v_bar = self._scroll.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            return True

        return super().eventFilter(obj, event)

    def _on_dpi_changed(self, text: str) -> None:
        try:
            dpi = int(text)
        except ValueError:
            return
        if dpi < 10:
            return
        self._preview_dpi = dpi
        self._figure.set_dpi(dpi)
        self._update_canvas_pixel_size()
        self._canvas.draw_idle()
        self.preview_dpi_changed.emit(dpi)
