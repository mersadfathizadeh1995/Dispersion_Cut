"""Multi-sheet tab widget for the Report Studio.

Provides closable, renamable, movable tabs. Each tab stores a snapshot
of the settings for that sheet so switching tabs restores the full state.
"""
from __future__ import annotations

import copy
from typing import Dict, Optional

from .qt_compat import (
    QtWidgets, Signal, CustomContextMenu, QAction,
)

QTabWidget = QtWidgets.QTabWidget
QTabBar = QtWidgets.QTabBar
QInputDialog = QtWidgets.QInputDialog
QMenu = QtWidgets.QMenu
QWidget = QtWidgets.QWidget

from .models import ReportStudioSettings


class SheetTabs(QTabWidget):
    """Tab widget where each tab represents a report sheet with its own settings."""

    sheet_changed = Signal(str)
    settings_snapshot_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._sheet_settings: Dict[int, ReportStudioSettings] = {}

        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self._on_close_tab)
        self.currentChanged.connect(self._on_tab_changed)

        tab_bar = self.tabBar()
        tab_bar.setContextMenuPolicy(CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._show_context_menu)
        tab_bar.mouseDoubleClickEvent = self._on_double_click

        self.add_sheet("Sheet 1")

    def add_sheet(self, name: str,
                  settings: Optional[ReportStudioSettings] = None) -> int:
        """Add a new sheet tab. Returns the tab index."""
        placeholder = QWidget()
        idx = self.addTab(placeholder, name)
        self._sheet_settings[idx] = settings or ReportStudioSettings()
        self.setCurrentIndex(idx)
        return idx

    def current_settings(self) -> ReportStudioSettings:
        """Return the settings snapshot for the current tab."""
        idx = self.currentIndex()
        if idx not in self._sheet_settings:
            self._sheet_settings[idx] = ReportStudioSettings()
        return self._sheet_settings[idx]

    def save_current_settings(self, settings: ReportStudioSettings) -> None:
        """Store a snapshot of the current settings for the active tab."""
        idx = self.currentIndex()
        self._sheet_settings[idx] = copy.deepcopy(settings)

    def current_sheet_name(self) -> str:
        idx = self.currentIndex()
        return self.tabText(idx) if idx >= 0 else "Sheet"

    def all_sheet_names(self) -> list[str]:
        return [self.tabText(i) for i in range(self.count())]

    def _on_close_tab(self, index: int) -> None:
        if self.count() <= 1:
            return
        self._sheet_settings.pop(index, None)
        self.removeTab(index)
        self._reindex_settings()

    def _on_tab_changed(self, index: int) -> None:
        if index >= 0:
            self.sheet_changed.emit(self.tabText(index))

    def _reindex_settings(self) -> None:
        """Rebuild _sheet_settings with contiguous indices after a remove."""
        old = self._sheet_settings
        self._sheet_settings = {}
        for new_idx in range(self.count()):
            for old_idx, s in old.items():
                if old_idx == new_idx:
                    self._sheet_settings[new_idx] = s
                    break
            else:
                self._sheet_settings[new_idx] = ReportStudioSettings()

    def _show_context_menu(self, pos) -> None:
        tab_bar = self.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return

        menu = QMenu(self)

        rename_act = QAction("Rename", self)
        rename_act.triggered.connect(lambda: self._rename_tab(index))
        menu.addAction(rename_act)

        dup_act = QAction("Duplicate", self)
        dup_act.triggered.connect(lambda: self._duplicate_tab(index))
        menu.addAction(dup_act)

        if self.count() > 1:
            close_act = QAction("Close", self)
            close_act.triggered.connect(lambda: self._on_close_tab(index))
            menu.addAction(close_act)

        menu.exec(tab_bar.mapToGlobal(pos))

    def _on_double_click(self, event) -> None:
        index = self.tabBar().tabAt(event.pos())
        if index >= 0:
            self._rename_tab(index)
        QTabBar.mouseDoubleClickEvent(self.tabBar(), event)

    def _rename_tab(self, index: int) -> None:
        old_name = self.tabText(index)
        name, ok = QInputDialog.getText(
            self, "Rename Sheet", "New name:", text=old_name,
        )
        if ok and name.strip():
            self.setTabText(index, name.strip())

    def _duplicate_tab(self, index: int) -> None:
        self.settings_snapshot_requested.emit()
        src = self._sheet_settings.get(index, ReportStudioSettings())
        new_settings = copy.deepcopy(src)
        name = f"{self.tabText(index)} (copy)"
        self.add_sheet(name, new_settings)
