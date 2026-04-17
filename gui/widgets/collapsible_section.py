"""Collapsible section widget for Qt.

Usage:
    section = CollapsibleSection("View", parent)
    section.add_widget(my_combo_box)
    section.add_widget(my_checkbox)
    layout.addWidget(section)
"""
from __future__ import annotations

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

# Qt5/Qt6 compat
try:
    _DownArrow = QtCore.Qt.DownArrow
    _RightArrow = QtCore.Qt.RightArrow
except AttributeError:
    _DownArrow = QtCore.Qt.ArrowType.DownArrow
    _RightArrow = QtCore.Qt.ArrowType.RightArrow

try:
    _ToolButtonTextBesideIcon = QtCore.Qt.ToolButtonTextBesideIcon
except AttributeError:
    _ToolButtonTextBesideIcon = QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon


class CollapsibleSection(QtWidgets.QWidget):
    """A collapsible section with a clickable header and toggleable body."""

    def __init__(
        self,
        title: str = "",
        parent: QtWidgets.QWidget | None = None,
        *,
        initially_expanded: bool = True,
    ) -> None:
        super().__init__(parent)

        self._toggle_button = QtWidgets.QToolButton(self)
        self._toggle_button.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 4px 2px; }"
        )
        self._toggle_button.setToolButtonStyle(_ToolButtonTextBesideIcon)
        self._toggle_button.setText(title)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(initially_expanded)
        self._toggle_button.setArrowType(
            _DownArrow if initially_expanded else _RightArrow
        )
        self._toggle_button.toggled.connect(self._on_toggled)

        # Separator line under header
        self._line = QtWidgets.QFrame(self)
        try:
            self._line.setFrameShape(QtWidgets.QFrame.HLine)
            self._line.setFrameShadow(QtWidgets.QFrame.Sunken)
        except AttributeError:
            self._line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            self._line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)

        # Content area
        self._content = QtWidgets.QWidget(self)
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 2, 0, 4)
        self._content_layout.setSpacing(4)
        self._content.setVisible(initially_expanded)

        # Main layout
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self._toggle_button)
        main.addWidget(self._line)
        main.addWidget(self._content)

    # ── public API ──

    def add_widget(self, widget: QtWidgets.QWidget) -> None:
        """Add a widget to the content area."""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout: QtWidgets.QLayout) -> None:
        """Add a layout to the content area."""
        self._content_layout.addLayout(layout)

    def add_row(self, label: str, widget: QtWidgets.QWidget) -> None:
        """Add a label + widget row (form-style)."""
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label))
        row.addWidget(widget, stretch=1)
        self._content_layout.addLayout(row)

    def set_expanded(self, expanded: bool) -> None:
        self._toggle_button.setChecked(expanded)

    def is_expanded(self) -> bool:
        return self._toggle_button.isChecked()

    @property
    def content_layout(self) -> QtWidgets.QVBoxLayout:
        return self._content_layout

    # ── private ──

    def _on_toggled(self, checked: bool) -> None:
        self._toggle_button.setArrowType(
            _DownArrow if checked else _RightArrow
        )
        self._content.setVisible(checked)
