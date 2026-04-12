"""Reusable CollapsibleSection widget with arrow-based toggle.

Matches the GeoFigure-style collapsible: a QToolButton header with a
down/right arrow that expands or collapses the content beneath it.
"""

from __future__ import annotations

from ...qt_compat import QtWidgets, QtCore


class CollapsibleSection(QtWidgets.QWidget):
    """A section with a clickable arrow header that expands/collapses content."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._toggle = QtWidgets.QToolButton()
        self._toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 2px 0px; }"
        )
        self._toggle.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded
            else QtCore.Qt.ArrowType.RightArrow
        )
        self._toggle.setText(f" {title}")
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)

        self.content = QtWidgets.QWidget()
        self.form = QtWidgets.QFormLayout(self.content)
        self.form.setContentsMargins(8, 2, 4, 2)
        self.content.setVisible(expanded)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._toggle)
        lay.addWidget(self.content)
        self._toggle.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool):
        self._toggle.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if checked
            else QtCore.Qt.ArrowType.RightArrow
        )
        self.content.setVisible(checked)

    def set_expanded(self, expanded: bool):
        self._toggle.setChecked(expanded)


# Keep backward-compatible alias used by existing imports
CollapsibleGroupBox = CollapsibleSection
