"""
Sheet tabs — multi-sheet QTabWidget for the central area.

Each tab holds a PlotCanvas rendering one SheetState.
"""

from __future__ import annotations

from typing import Dict, List, TYPE_CHECKING

from ...qt_compat import QtWidgets, QtCore, Signal

if TYPE_CHECKING:
    from .plot_canvas import PlotCanvas


class SheetTabs(QtWidgets.QTabWidget):
    """
    Tab widget managing multiple report sheets.

    Signals
    -------
    sheet_changed(int)
        Emitted when the user switches tabs.
    sheet_renamed(int, str)
        Emitted when a tab is renamed.
    add_sheet_requested()
        Emitted when the "+" button is clicked.
    """

    sheet_changed = Signal(int)
    sheet_renamed = Signal(int, str)
    add_sheet_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)

        # "+" button to add new sheets
        add_btn = QtWidgets.QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Add new sheet")
        add_btn.clicked.connect(self.add_sheet_requested.emit)
        self.setCornerWidget(add_btn, QtCore.Qt.TopRightCorner
                             if hasattr(QtCore.Qt, "TopRightCorner")
                             else QtCore.Qt.Corner.TopRightCorner)

        self.currentChanged.connect(self.sheet_changed.emit)
        self.tabCloseRequested.connect(self._on_close_requested)
        self.tabBarDoubleClicked.connect(self._on_double_click)

    # ── Public API ─────────────────────────────────────────────────────

    def add_tab(self, canvas: "PlotCanvas", name: str) -> int:
        """Add a new sheet tab containing the given canvas."""
        idx = self.addTab(canvas, name)
        self.setCurrentIndex(idx)
        return idx

    def current_canvas(self) -> "PlotCanvas":
        """Return the PlotCanvas in the current tab."""
        return self.currentWidget()

    # ── Event handlers ─────────────────────────────────────────────────

    def _on_close_requested(self, index: int):
        """Close tab (keep at least one)."""
        if self.count() <= 1:
            return
        widget = self.widget(index)
        self.removeTab(index)
        if widget:
            widget.deleteLater()

    def _on_double_click(self, index: int):
        """Rename tab on double-click."""
        if index < 0:
            return
        current_name = self.tabText(index)
        from ...qt_compat import QtWidgets as _qw
        name, ok = _qw.QInputDialog.getText(
            self, "Rename Sheet", "Sheet name:", text=current_name
        )
        if ok and name.strip():
            self.setTabText(index, name.strip())
            self.sheet_renamed.emit(index, name.strip())
