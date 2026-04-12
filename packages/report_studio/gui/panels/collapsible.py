"""Collapsible group box — QGroupBox that can collapse/expand its contents."""

from __future__ import annotations

from ...qt_compat import QtWidgets, QtCore


class CollapsibleGroupBox(QtWidgets.QGroupBox):
    """A QGroupBox whose content can be collapsed by clicking the title."""

    def __init__(self, title: str = "", parent=None, collapsed: bool = False):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(not collapsed)
        self.toggled.connect(self._on_toggled)
        self._content_height = 0

    def _on_toggled(self, checked: bool):
        """Show or hide group content."""
        for i in range(self.layout().count()) if self.layout() else []:
            item = self.layout().itemAt(i)
            widget = item.widget()
            if widget:
                widget.setVisible(checked)
            elif item.layout():
                _set_layout_visible(item.layout(), checked)
        if not checked:
            self.setMaximumHeight(30)
        else:
            self.setMaximumHeight(16777215)


def _set_layout_visible(layout, visible: bool):
    """Recursively show/hide widgets in a layout."""
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        if widget:
            widget.setVisible(visible)
        elif item.layout():
            _set_layout_visible(item.layout(), visible)
