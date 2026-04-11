"""Layers panel -- per-layer visibility and color toggles."""
from __future__ import annotations

from typing import List

from ..qt_compat import (
    QtWidgets, Signal,
    ItemIsUserCheckable, Checked, Unchecked, UserRole,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QLabel = QtWidgets.QLabel
QCheckBox = QtWidgets.QCheckBox


class LayersPanel(QWidget):
    """Lists data layers with visibility checkboxes.

    Emits ``visibility_changed`` whenever a layer toggle changes so the
    render cycle can re-read active flags from the generator.
    """

    visibility_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("<b>Layers</b>")
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(False)
        self._tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree, stretch=1)

        self._items: list[QTreeWidgetItem] = []

    def populate(self, labels: List[str], active_flags: List[bool],
                 spectrum_flags: List[bool] | None = None) -> None:
        """Fill the tree with layer entries.

        Parameters
        ----------
        labels : list of str
            Display labels for each layer.
        active_flags : list of bool
            Initial visibility for each layer.
        spectrum_flags : list of bool, optional
            Whether spectrum data exists for each layer (for future use).
        """
        self._tree.blockSignals(True)
        self._tree.clear()
        self._items.clear()

        for i, (label, active) in enumerate(zip(labels, active_flags)):
            item = QTreeWidgetItem(self._tree, [label])
            item.setFlags(item.flags() | ItemIsUserCheckable)
            item.setCheckState(0, Checked if active else Unchecked)
            item.setData(0, UserRole, i)
            self._items.append(item)

        self._tree.blockSignals(False)

    def get_active_flags(self) -> List[bool]:
        """Return current visibility flags for all layers."""
        flags = []
        for item in self._items:
            flags.append(item.checkState(0) == Checked)
        return flags

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column == 0:
            self.visibility_changed.emit()
