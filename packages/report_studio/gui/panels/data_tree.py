"""
Data tree — hierarchical QTreeWidget with drag-drop between subplots.

Structure:
    Subplot 1
      ├─ Offset +10m  [✓] (draggable)
      │    ├─ Data: 50 points (freq / vel)
      │    └─ Spectrum: fdbf  [✓]
      ├─ Offset +20m  [✓]
      │    ├─ Data: 45 points (freq / vel)
      │    └─ Spectrum: fdbf  [✓]
      └─ Offset +30m  [ ]
           └─ Data: 48 points (freq / vel)
    Subplot 2
      └─ ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Checked, Unchecked, UserRole, CheckStateRole,
    ItemIsEnabled, ItemIsSelectable, ItemIsUserCheckable,
    ItemIsDragEnabled, ItemIsDropEnabled,
    NoEditTriggers, DragDrop, MoveAction,
)

if TYPE_CHECKING:
    from ...core.models import SheetState, OffsetCurve


# Role for storing uid / subplot_key
_UID_ROLE = UserRole
_KEY_ROLE = UserRole + 1
_ITEM_TYPE_ROLE = UserRole + 2

_TYPE_SUBPLOT = "subplot"
_TYPE_CURVE = "curve"
_TYPE_INFO = "info"
_TYPE_SPECTRUM = "spectrum"


class _DragTreeWidget(QtWidgets.QTreeWidget):
    """QTreeWidget with drag-drop support for moving curves between subplots."""

    curve_moved = Signal(str, str)  # uid, new_subplot_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(DragDrop)
        self.setDefaultDropAction(MoveAction)
        self.setEditTriggers(NoEditTriggers)
        try:
            self.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        except AttributeError:
            self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

    def startDrag(self, supportedActions):
        """Only allow dragging curve items (not subplot roots or info items)."""
        item = self.currentItem()
        if item and item.data(0, _ITEM_TYPE_ROLE) == _TYPE_CURVE:
            super().startDrag(supportedActions)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Only accept drops on subplot root items."""
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        target = self.itemAt(pos)
        if target and target.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
            event.acceptProposedAction()
        elif target and target.parent():
            parent = target.parent()
            if parent.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
                event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Move curve to the target subplot."""
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        target = self.itemAt(pos)
        if not target:
            return

        # Find the subplot target
        if target.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
            new_key = target.data(0, _KEY_ROLE)
        elif target.parent() and target.parent().data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
            new_key = target.parent().data(0, _KEY_ROLE)
        else:
            return

        dragged = self.currentItem()
        if not dragged or dragged.data(0, _ITEM_TYPE_ROLE) != _TYPE_CURVE:
            return

        uid = dragged.data(0, _UID_ROLE)
        if uid and new_key:
            self.curve_moved.emit(uid, new_key)
        event.acceptProposedAction()


class DataTreePanel(QtWidgets.QWidget):
    """
    Left dock panel — hierarchical data tree with visibility checkboxes.

    Signals
    -------
    curve_selected(str)
    curve_visibility_changed(str, bool)
    spectrum_visibility_changed(str, bool)
    curve_moved(str, str)
    remove_curve_requested(str)
    add_data_requested()
    """

    curve_selected = Signal(str)
    curves_selected = Signal(list)       # List[str] — multi-select curve UIDs
    spectrum_selected = Signal(str)      # curve uid whose spectrum was selected
    spectra_selected = Signal(list)      # List[str] — multi-select spectrum UIDs
    subplot_selected = Signal(str)       # subplot key
    subplots_selected = Signal(list)     # List[str] — multi-select subplot keys
    curve_visibility_changed = Signal(str, bool)
    spectrum_visibility_changed = Signal(str, bool)
    curve_moved = Signal(str, str)
    remove_curve_requested = Signal(str)
    add_data_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header with add button
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Data"))
        add_btn = QtWidgets.QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Load data")
        add_btn.clicked.connect(self.add_data_requested.emit)
        header.addStretch()
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Tree widget
        self._tree = _DragTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.curve_moved.connect(self.curve_moved.emit)
        # Windows Explorer-style strong blue selection highlight
        self._tree.setStyleSheet(
            "QTreeWidget::item:selected {"
            "  background-color: #3399FF;"
            "  color: white;"
            "}"
            "QTreeWidget::item:selected:!active {"
            "  background-color: #5CACEE;"
            "  color: white;"
            "}"
        )
        layout.addWidget(self._tree)

        # Context menu
        self._tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu
                                        if not hasattr(QtCore.Qt, "ContextMenuPolicy")
                                        else QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        self._subplot_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._curve_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}

    # ── Public API ─────────────────────────────────────────────────────

    def populate(self, sheet: "SheetState"):
        """Rebuild the tree from a SheetState."""
        self._tree.blockSignals(True)
        self._tree.clear()
        self._subplot_items.clear()
        self._curve_items.clear()

        for key in sheet.subplot_keys_ordered():
            sp = sheet.subplots[key]
            sp_item = QtWidgets.QTreeWidgetItem([sp.display_name])
            sp_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_SUBPLOT)
            sp_item.setData(0, _KEY_ROLE, key)
            sp_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsDropEnabled
            )

            # Bold font for subplot headers
            font = sp_item.font(0)
            font.setBold(True)
            sp_item.setFont(0, font)

            # Add curves with sub-layers
            for uid in sp.curve_uids:
                curve = sheet.curves.get(uid)
                if not curve:
                    continue
                c_item = self._make_curve_item(curve, key, sheet)
                sp_item.addChild(c_item)
                self._curve_items[uid] = c_item

            self._tree.addTopLevelItem(sp_item)
            self._subplot_items[key] = sp_item
            sp_item.setExpanded(True)

        self._tree.blockSignals(False)

    def select_curve(self, uid: str):
        """Programmatically select a curve in the tree."""
        item = self._curve_items.get(uid)
        if item:
            self._tree.setCurrentItem(item)

    # ── Tree item construction ─────────────────────────────────────────

    def _make_curve_item(self, curve, key: str, sheet) -> QtWidgets.QTreeWidgetItem:
        """Build a curve tree item with data info and spectrum sub-layers."""
        c_item = QtWidgets.QTreeWidgetItem([curve.display_name])
        c_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_CURVE)
        c_item.setData(0, _UID_ROLE, curve.uid)
        c_item.setData(0, _KEY_ROLE, key)
        c_item.setFlags(
            ItemIsEnabled | ItemIsSelectable
            | ItemIsUserCheckable | ItemIsDragEnabled
        )
        c_item.setCheckState(0, Checked if curve.visible else Unchecked)

        # Color indicator
        if curve.color:
            px = QtGui.QPixmap(12, 12)
            px.fill(QtGui.QColor(curve.color))
            c_item.setIcon(0, QtGui.QIcon(px))

        # Sub-layer: Data info
        n_pts = curve.n_points
        if curve.point_mask is not None:
            n_active = int(curve.point_mask.sum())
            data_text = f"Data: {n_active}/{n_pts} points"
        else:
            data_text = f"Data: {n_pts} points"
        info_item = QtWidgets.QTreeWidgetItem([data_text])
        info_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_INFO)
        info_item.setData(0, _UID_ROLE, curve.uid)
        info_item.setFlags(ItemIsEnabled | ItemIsSelectable)
        # Dimmed style for info rows
        info_item.setForeground(0, QtGui.QColor("#888888"))
        c_item.addChild(info_item)

        # Sub-layer: Spectrum (if linked)
        if curve.spectrum_uid:
            spec = sheet.spectra.get(curve.spectrum_uid)
            spec_label = f"Spectrum"
            if spec:
                spec_label += f": {spec.method}"
            spec_item = QtWidgets.QTreeWidgetItem([spec_label])
            spec_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_SPECTRUM)
            spec_item.setData(0, _UID_ROLE, curve.uid)
            spec_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
            )
            spec_item.setCheckState(
                0, Checked if curve.spectrum_visible else Unchecked
            )
            spec_item.setForeground(0, QtGui.QColor("#666699"))
            c_item.addChild(spec_item)

        return c_item

    # ── Event handlers ─────────────────────────────────────────────────

    def _on_item_clicked(self, item, column):
        item_type = item.data(0, _ITEM_TYPE_ROLE)
        uid = item.data(0, _UID_ROLE)
        key = item.data(0, _KEY_ROLE)

        # ── Single-click signal based on item type ────────────────────
        if item_type == _TYPE_SUBPLOT and key:
            self.subplot_selected.emit(key)
        elif item_type == _TYPE_SPECTRUM and uid:
            self.spectrum_selected.emit(uid)
        elif item_type in (_TYPE_CURVE, _TYPE_INFO) and uid:
            self.curve_selected.emit(uid)

        # ── Multi-select: gather per type ─────────────────────────────
        sel_curve_uids = []
        sel_spectrum_uids = []
        sel_subplot_keys = []

        for sel_item in self._tree.selectedItems():
            sel_type = sel_item.data(0, _ITEM_TYPE_ROLE)
            sel_uid = sel_item.data(0, _UID_ROLE)
            sel_key = sel_item.data(0, _KEY_ROLE)

            if sel_type == _TYPE_SUBPLOT and sel_key:
                if sel_key not in sel_subplot_keys:
                    sel_subplot_keys.append(sel_key)
            elif sel_type == _TYPE_SPECTRUM and sel_uid:
                if sel_uid not in sel_spectrum_uids:
                    sel_spectrum_uids.append(sel_uid)
            elif sel_type == _TYPE_CURVE and sel_uid:
                if sel_uid not in sel_curve_uids:
                    sel_curve_uids.append(sel_uid)
            elif sel_type == _TYPE_INFO and sel_uid:
                if sel_uid not in sel_curve_uids:
                    sel_curve_uids.append(sel_uid)

        # Emit batch signals when >1 items of same type
        if len(sel_curve_uids) > 1:
            self.curves_selected.emit(sel_curve_uids)
        if len(sel_spectrum_uids) > 1:
            self.spectra_selected.emit(sel_spectrum_uids)
        if len(sel_subplot_keys) > 1:
            self.subplots_selected.emit(sel_subplot_keys)

    def _on_item_changed(self, item, column):
        item_type = item.data(0, _ITEM_TYPE_ROLE)
        if item_type == _TYPE_CURVE:
            uid = item.data(0, _UID_ROLE)
            checked = item.checkState(0) == Checked
            if uid:
                self.curve_visibility_changed.emit(uid, checked)
        elif item_type == _TYPE_SPECTRUM:
            uid = item.data(0, _UID_ROLE)
            checked = item.checkState(0) == Checked
            if uid:
                self.spectrum_visibility_changed.emit(uid, checked)

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = QtWidgets.QMenu(self)
        item_type = item.data(0, _ITEM_TYPE_ROLE)

        if item_type == _TYPE_CURVE:
            uid = item.data(0, _UID_ROLE)
            act_remove = menu.addAction("Remove curve")
            act_remove.triggered.connect(lambda: self.remove_curve_requested.emit(uid))

        if menu.actions():
            menu.exec(self._tree.viewport().mapToGlobal(pos))
