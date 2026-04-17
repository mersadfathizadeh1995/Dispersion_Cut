"""Thin left-edge collapse strip for the main window.

Hosts a single arrow button that hides/shows the entire left dock
column at once.  When the column is expanded, the button shows a
left-pointing triangle ("collapse"); when collapsed, a right-pointing
triangle ("expand").  The strip lives in its own left toolbar area so
it never steals height from the dock column it controls, and it can't
be moved, floated or hidden.

Usage (in :mod:`gui.main_window`)::

    self._left_strip = LeftEdgeStrip(self)
    self._left_strip_bar = LeftEdgeStripToolBar(self._left_strip, self)
    self.addToolBar(Qt.LeftToolBarArea, self._left_strip_bar)
    self._left_strip.toggled.connect(self._toggle_left_panel)
"""
from __future__ import annotations

from typing import Optional

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui

try:
    _NoFeatures = QtWidgets.QDockWidget.NoDockWidgetFeatures
except AttributeError:
    _NoFeatures = QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures

try:
    _LeftToolBarArea = QtCore.Qt.LeftToolBarArea
except AttributeError:
    _LeftToolBarArea = QtCore.Qt.ToolBarArea.LeftToolBarArea

try:
    _AlignHCenter = QtCore.Qt.AlignHCenter
    _AlignVCenter = QtCore.Qt.AlignVCenter
    _AlignCenter = QtCore.Qt.AlignCenter
except AttributeError:
    _AlignHCenter = QtCore.Qt.AlignmentFlag.AlignHCenter
    _AlignVCenter = QtCore.Qt.AlignmentFlag.AlignVCenter
    _AlignCenter = QtCore.Qt.AlignmentFlag.AlignCenter


class LeftEdgeStrip(QtWidgets.QWidget):
    """A thin vertical bar with one vertically-centred arrow button.

    Signals
    -------
    toggled(bool) :
        Emitted when the user clicks the arrow.  The boolean is the
        new *collapsed* state (``True`` = dock column should hide,
        ``False`` = dock column should show).
    """

    toggled = QtCore.Signal(bool)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(22)
        self.setObjectName("LeftEdgeStrip")
        self.setStyleSheet(
            "QWidget#LeftEdgeStrip { background: palette(window); }"
        )
        # Expand vertically with its host so the centred button is
        # always at the middle of the available height.
        try:
            _sp_fixed = QtWidgets.QSizePolicy.Fixed
            _sp_expand = QtWidgets.QSizePolicy.Expanding
        except AttributeError:
            _sp_fixed = QtWidgets.QSizePolicy.Policy.Fixed
            _sp_expand = QtWidgets.QSizePolicy.Policy.Expanding
        self.setSizePolicy(_sp_fixed, _sp_expand)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)
        # Stretch above AND below so the button stays centred even
        # when the host grows or shrinks.
        layout.addStretch(1)

        self._btn = QtWidgets.QToolButton(self)
        self._btn.setAutoRaise(True)
        self._btn.setFixedSize(20, 28)
        self._btn.setToolTip(
            "Collapse or expand the left panel (Ctrl+B)"
        )
        self._btn.clicked.connect(self._on_clicked)
        layout.addWidget(self._btn, 0, _AlignHCenter)

        layout.addStretch(1)

        # Internal collapsed state; starts expanded.
        self._collapsed = False
        self._update_icon()

    # ── public API ──────────────────────────────────────────────────
    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, value: bool, *, emit: bool = False) -> None:
        value = bool(value)
        if value == self._collapsed:
            return
        self._collapsed = value
        self._update_icon()
        if emit:
            self.toggled.emit(self._collapsed)

    # ── internals ──────────────────────────────────────────────────
    def _on_clicked(self) -> None:
        self._collapsed = not self._collapsed
        self._update_icon()
        self.toggled.emit(self._collapsed)

    def _update_icon(self) -> None:
        # Triangle characters: ▶ (expand) / ◀ (collapse)
        if self._collapsed:
            self._btn.setText("\u25B6")
            self._btn.setToolTip("Expand the left panel (Ctrl+B)")
        else:
            self._btn.setText("\u25C0")
            self._btn.setToolTip("Collapse the left panel (Ctrl+B)")


class LeftEdgeStripToolBar(QtWidgets.QToolBar):
    """Host toolbar for the :class:`LeftEdgeStrip`.

    Using a toolbar (instead of a dock widget) keeps the strip in its
    own left-edge column so the real dock column retains its full
    height, its user-draggable width, and its tabified bottom tab bar
    -- exactly as it was before the strip was introduced.
    """

    def __init__(
        self, strip: LeftEdgeStrip,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__("LeftStrip", parent)
        self.setObjectName("LeftEdgeStripToolBar")
        self.setFloatable(False)
        self.setMovable(False)
        try:
            self.toggleViewAction().setVisible(False)
        except Exception:
            pass
        self.setContextMenuPolicy(QtCore.Qt.PreventContextMenu if hasattr(
            QtCore.Qt, "PreventContextMenu") else QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
        self.setIconSize(QtCore.QSize(16, 16))
        # Zero-margin, full-height host for the strip so the button
        # can be perfectly centred vertically.
        self.addWidget(strip)
        self.setFixedWidth(26)


class LeftEdgeStripDock(QtWidgets.QDockWidget):
    """Legacy dock host (kept for back-compat; prefer the toolbar)."""

    def __init__(
        self, strip: LeftEdgeStrip,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__("", parent)
        self.setObjectName("LeftEdgeStripDock")
        self.setTitleBarWidget(QtWidgets.QWidget(self))
        try:
            self.setFeatures(_NoFeatures)
        except Exception:
            pass
        self.setWidget(strip)
        self.setMinimumWidth(22)
        self.setMaximumWidth(26)


__all__ = ["LeftEdgeStrip", "LeftEdgeStripToolBar", "LeftEdgeStripDock"]
