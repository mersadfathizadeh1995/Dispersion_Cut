"""Left-panel plot type selector with per-plot-type settings stack.

Provides a QTreeWidget of available (implemented) plot types grouped by
category, plus a QStackedWidget below that swaps to show per-plot-type
settings when the selection changes.
"""
from __future__ import annotations

from ..qt_compat import (
    QtWidgets, Signal,
    Vertical, AlignCenter, ItemIsSelectable, UserRole,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QStackedWidget = QtWidgets.QStackedWidget
QLabel = QtWidgets.QLabel
QSplitter = QtWidgets.QSplitter

from ...dialog.constants import FIGURE_TYPES


class PlotSelector(QWidget):
    """Plot type selector with dynamic per-plot-type settings area."""

    plot_type_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_key: str = ""
        self._settings_widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        header = QLabel("<b>Plot Types</b>")
        layout.addWidget(header)

        splitter = QSplitter(Vertical)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setIndentation(16)
        self._tree.currentItemChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._tree)

        self._settings_stack = QStackedWidget()
        self._empty_label = QLabel("Select a plot type to see its settings")
        self._empty_label.setAlignment(AlignCenter)
        self._empty_label.setWordWrap(True)
        self._settings_stack.addWidget(self._empty_label)
        splitter.addWidget(self._settings_stack)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, stretch=1)

        self._populate_tree()

    def _populate_tree(self) -> None:
        """Build the tree from FIGURE_TYPES, showing only implemented entries."""
        self._tree.clear()
        for category, entries in FIGURE_TYPES.items():
            implemented = [e for e in entries if e[3]]
            if not implemented:
                continue
            cat_item = QTreeWidgetItem(self._tree, [category])
            cat_item.setFlags(cat_item.flags() & ~ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            for display_name, key, description, _ in implemented:
                child = QTreeWidgetItem(cat_item, [display_name])
                child.setData(0, UserRole, key)
                child.setToolTip(0, description)
            cat_item.setExpanded(True)

    def _on_selection_changed(self, current: QTreeWidgetItem | None,
                              _previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        key = current.data(0, UserRole)
        if key is None:
            return
        if key == self._current_key:
            return
        self._current_key = key

        if key in self._settings_widgets:
            self._settings_stack.setCurrentWidget(self._settings_widgets[key])
        else:
            self._settings_stack.setCurrentWidget(self._empty_label)

        self.plot_type_changed.emit(key)

    @property
    def current_plot_type(self) -> str:
        return self._current_key

    def register_settings_widget(self, plot_type_key: str,
                                 widget: QWidget) -> None:
        """Register a per-plot-type settings widget in the stacked area."""
        self._settings_widgets[plot_type_key] = widget
        self._settings_stack.addWidget(widget)

    def select_plot_type(self, key: str) -> None:
        """Programmatically select a plot type by internal key."""
        it = self._tree.invisibleRootItem()
        for cat_idx in range(it.childCount()):
            cat = it.child(cat_idx)
            for child_idx in range(cat.childCount()):
                child = cat.child(child_idx)
                if child.data(0, UserRole) == key:
                    self._tree.setCurrentItem(child)
                    return
