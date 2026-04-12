"""Matplotlib canvas widget for the Report Studio.

Wraps a Figure + FigureCanvasQTAgg inside a QScrollArea with:
- Full NavigationToolbar (Home, Back, Forward, Pan, Zoom, Subplots, Save)
- Fit-mode selector: Auto Fit / Fit Width / Fit Height / Manual
- Explicit +/- zoom buttons for image-level zoom
- Middle-click drag to pan the scroll area
- Mouse wheel scrolls the QScrollArea normally (no zoom hijacking)

Matplotlib's native tools handle all data-level interactions (click on
legends, toolbar pan/zoom on axes, etc.).
"""
from __future__ import annotations

from matplotlib.backends.backend_qtagg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure

from .qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    AlignCenter, ScrollBarAsNeeded,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QScrollArea = QtWidgets.QScrollArea
QComboBox = QtWidgets.QComboBox
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QFrame = QtWidgets.QFrame

DEFAULT_PREVIEW_DPI = 100

_ZOOM_MIN = 0.10
_ZOOM_MAX = 5.0
_BUTTON_FACTOR = 1.25

FIT_AUTO = "Auto Fit"
FIT_WIDTH = "Fit Width"
FIT_HEIGHT = "Fit Height"
FIT_MANUAL = "Manual"

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


def _event_global_pos(event):
    """Qt5/Qt6 compat: get global position from a mouse event."""
    try:
        return event.globalPosition().toPoint()
    except AttributeError:
        return event.globalPos()


def _make_separator(parent=None) -> QFrame:
    sep = QFrame(parent)
    try:
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
    except AttributeError:
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep


class CanvasView(QWidget):
    """Central canvas widget: toolbar on top, scrollable matplotlib canvas below.

    Image-level zoom is controlled via +/- buttons and fit-mode selector.
    Middle-click drag pans the scroll area.
    NavigationToolbar provides full matplotlib interaction (Pan, Zoom, etc.).
    """

    preview_dpi_changed = Signal(int)

    def __init__(self, width_in: float = 8.0, height_in: float = 6.0,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._preview_dpi = DEFAULT_PREVIEW_DPI
        self._zoom_level = 1.0
        self._fit_mode = FIT_AUTO
        self._dragging = False
        self._drag_origin = QtCore.QPoint()

        self._resize_timer = QtCore.QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._on_resize_timeout)

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

        toolbar_row.addWidget(_make_separator())

        toolbar_row.addWidget(QLabel("Fit:"))
        self._fit_combo = QComboBox()
        self._fit_combo.addItems([FIT_AUTO, FIT_WIDTH, FIT_HEIGHT, FIT_MANUAL])
        self._fit_combo.setCurrentText(FIT_AUTO)
        self._fit_combo.setFixedWidth(90)
        self._fit_combo.setToolTip("Canvas fit mode")
        self._fit_combo.currentTextChanged.connect(self._on_fit_mode_changed)
        toolbar_row.addWidget(self._fit_combo)

        toolbar_row.addWidget(_make_separator())

        self._zoom_out_btn = QPushButton("\u2212")
        self._zoom_out_btn.setFixedSize(26, 26)
        self._zoom_out_btn.setCheckable(False)
        self._zoom_out_btn.setToolTip("Zoom out (image)")
        self._zoom_out_btn.clicked.connect(self._on_zoom_out_clicked)
        toolbar_row.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(AlignCenter)
        self._zoom_label.setToolTip("Current zoom level")
        toolbar_row.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedSize(26, 26)
        self._zoom_in_btn.setCheckable(False)
        self._zoom_in_btn.setToolTip("Zoom in (image)")
        self._zoom_in_btn.clicked.connect(self._on_zoom_in_clicked)
        toolbar_row.addWidget(self._zoom_in_btn)

        self._zoom_reset_btn = QPushButton("1:1")
        self._zoom_reset_btn.setFixedSize(32, 26)
        self._zoom_reset_btn.setToolTip("Reset zoom to 100%")
        self._zoom_reset_btn.clicked.connect(self.reset_zoom)
        toolbar_row.addWidget(self._zoom_reset_btn)

        toolbar_row.addWidget(_make_separator())

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

        # Only filter viewport for middle-click pan — nothing else.
        self._scroll.viewport().installEventFilter(self)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def figure(self) -> Figure:
        return self._figure

    @property
    def canvas(self) -> FigureCanvas:
        return self._canvas

    @property
    def preview_dpi(self) -> int:
        return self._preview_dpi

    @property
    def zoom_level(self) -> float:
        return self._zoom_level

    @property
    def fit_mode(self) -> str:
        return self._fit_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_preview_dpi(self, dpi: int) -> None:
        if dpi == self._preview_dpi:
            return
        self._preview_dpi = dpi
        self._dpi_combo.blockSignals(True)
        self._dpi_combo.setCurrentText(str(dpi))
        self._dpi_combo.blockSignals(False)
        self._figure.set_dpi(dpi)
        self._apply_fit_or_manual()
        self._canvas.draw_idle()

    def update_size(self, width_in: float, height_in: float) -> None:
        self._figure.set_size_inches(width_in, height_in)
        self._figure.set_dpi(self._preview_dpi)
        self._apply_fit_or_manual()

    def refresh(self) -> None:
        self._apply_fit_or_manual()
        self._canvas.draw_idle()

    def reset_zoom(self) -> None:
        self._zoom_level = 1.0
        self._set_fit_mode(FIT_MANUAL)
        self._update_canvas_pixel_size()
        self._update_zoom_label()

    # ------------------------------------------------------------------
    # Fit mode logic
    # ------------------------------------------------------------------

    def _on_fit_mode_changed(self, text: str) -> None:
        self._fit_mode = text
        self._apply_fit_or_manual()

    def _set_fit_mode(self, mode: str) -> None:
        self._fit_mode = mode
        self._fit_combo.blockSignals(True)
        self._fit_combo.setCurrentText(mode)
        self._fit_combo.blockSignals(False)

    def _apply_fit_or_manual(self) -> None:
        if self._fit_mode == FIT_MANUAL:
            self._update_canvas_pixel_size()
            self._update_zoom_label()
            return

        w_in, h_in = self._figure.get_size_inches()
        dpi = self._preview_dpi
        fig_px_w = w_in * dpi
        fig_px_h = h_in * dpi

        vp = self._scroll.viewport()
        vp_w = max(vp.width(), 100)
        vp_h = max(vp.height(), 100)

        if self._fit_mode == FIT_AUTO:
            scale = min(vp_w / fig_px_w, vp_h / fig_px_h)
        elif self._fit_mode == FIT_WIDTH:
            scale = vp_w / fig_px_w
        elif self._fit_mode == FIT_HEIGHT:
            scale = vp_h / fig_px_h
        else:
            scale = self._zoom_level

        self._zoom_level = max(_ZOOM_MIN, min(_ZOOM_MAX, scale))
        self._update_canvas_pixel_size()
        self._update_zoom_label()

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------

    def _on_zoom_in_clicked(self) -> None:
        new = self._zoom_level * _BUTTON_FACTOR
        self._zoom_level = max(_ZOOM_MIN, min(_ZOOM_MAX, new))
        self._set_fit_mode(FIT_MANUAL)
        self._update_canvas_pixel_size()
        self._update_zoom_label()

    def _on_zoom_out_clicked(self) -> None:
        new = self._zoom_level / _BUTTON_FACTOR
        self._zoom_level = max(_ZOOM_MIN, min(_ZOOM_MAX, new))
        self._set_fit_mode(FIT_MANUAL)
        self._update_canvas_pixel_size()
        self._update_zoom_label()

    def _apply_button_zoom(self, factor: float) -> None:
        self._zoom_level = max(
            _ZOOM_MIN, min(_ZOOM_MAX, self._zoom_level * factor)
        )
        self._set_fit_mode(FIT_MANUAL)
        self._update_canvas_pixel_size()
        self._update_zoom_label()

    def _update_canvas_pixel_size(self) -> None:
        w, h = self._figure.get_size_inches()
        dpi = self._preview_dpi
        z = self._zoom_level
        self._canvas.setFixedSize(
            max(int(w * dpi * z), 200),
            max(int(h * dpi * z), 150),
        )

    def _update_zoom_label(self) -> None:
        pct = int(round(self._zoom_level * 100))
        self._zoom_label.setText(f"{pct}%")

    # ------------------------------------------------------------------
    # Middle-click pan helpers
    # ------------------------------------------------------------------

    def _start_pan(self, global_pos: QtCore.QPoint) -> None:
        self._dragging = True
        self._drag_origin = global_pos

    def _update_pan(self, global_pos: QtCore.QPoint) -> None:
        delta = global_pos - self._drag_origin
        self._drag_origin = global_pos
        h_bar = self._scroll.horizontalScrollBar()
        v_bar = self._scroll.verticalScrollBar()
        h_bar.setValue(h_bar.value() - delta.x())
        v_bar.setValue(v_bar.value() - delta.y())

    def _end_pan(self) -> None:
        self._dragging = False

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode != FIT_MANUAL:
            self._resize_timer.start()

    def _on_resize_timeout(self) -> None:
        if self._fit_mode != FIT_MANUAL:
            self._apply_fit_or_manual()

    def eventFilter(self, obj, event) -> bool:
        """Middle-click drag to pan the scroll area. Nothing else intercepted."""
        if obj is not self._scroll.viewport():
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == _MOUSE_PRESS and event.button() == _MID_BUTTON:
            self._start_pan(_event_global_pos(event))
            return True
        if etype == _MOUSE_RELEASE and event.button() == _MID_BUTTON:
            if self._dragging:
                self._end_pan()
                return True
        if etype == _MOUSE_MOVE and self._dragging:
            self._update_pan(_event_global_pos(event))
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
        self._apply_fit_or_manual()
        self._canvas.draw_idle()
        self.preview_dpi_changed.emit(dpi)
