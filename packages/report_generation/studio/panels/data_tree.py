"""Data tree -- hierarchical view of subplots and data series.

Replaces the flat LayerEditor with a geo_figure-inspired tree:
    Subplot 0: "Frequency Domain"
      +-- Offset 1 (5m)   [checkbox] [color swatch]
      |     +-- ☐ Spectrum Background
      |     +-- ☐ Near-Field Effect
      +-- Offset 2 (10m)  [checkbox] [color swatch]
            +-- ☐ Spectrum Background
            +-- ☐ Near-Field Effect

Subplot rows are top-level; data rows are children. Sub-layers
(spectrum, NF) are grandchildren. Drag-and-drop moves data between
subplots. Selection emits typed signals that drive the context-
sensitive right panel.
"""
from __future__ import annotations

from typing import List, Optional

from ..qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Checked, Unchecked, UserRole,
    ItemIsEnabled, ItemIsSelectable, ItemIsUserCheckable,
    ItemIsDragEnabled, ItemIsDropEnabled, MoveAction, InternalMove,
    DialogAccepted,
)
from ..figure_model import FigureModel, SubplotModel, DataSeries

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QTreeWidget = QtWidgets.QTreeWidget
QTreeWidgetItem = QtWidgets.QTreeWidgetItem
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QSpinBox = QtWidgets.QSpinBox
QDialog = QtWidgets.QDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QComboBox = QtWidgets.QComboBox
QFormLayout = QtWidgets.QFormLayout

_ROLE_TYPE = UserRole + 1
_ROLE_KEY = UserRole + 2

_TYPE_SUBPLOT = "subplot"
_TYPE_DATA = "data"
_TYPE_SPECTRUM = "spectrum"
_TYPE_NEARFIELD = "nearfield"


class _DragDropTree(QTreeWidget):
    """QTreeWidget subclass that emits a signal after an internal drag-drop."""

    items_dropped = Signal()

    def dropEvent(self, event):
        super().dropEvent(event)
        self.items_dropped.emit()


class _OffsetPickerDialog(QDialog):
    """Dialog for selecting offsets to add as data series."""

    def __init__(self, offset_labels: List[str], subplot_names: List[tuple],
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Data Series")
        self.setMinimumWidth(320)
        self.setMinimumHeight(300)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Select offsets to add:"))

        btn_row = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.clicked.connect(self._select_all)
        desel_all = QPushButton("Deselect All")
        desel_all.clicked.connect(self._deselect_all)
        btn_row.addWidget(sel_all)
        btn_row.addWidget(desel_all)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._offset_list = QListWidget()
        self._offset_list.setMinimumHeight(160)
        for i, label in enumerate(offset_labels):
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | ItemIsUserCheckable)
            item.setCheckState(Unchecked)
            item.setData(UserRole, i)
            self._offset_list.addItem(item)
        layout.addWidget(self._offset_list)

        form = QFormLayout()
        self._subplot_combo = QComboBox()
        for key, title in subplot_names:
            self._subplot_combo.addItem(title or key, key)
        form.addRow("Target subplot:", self._subplot_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_selected_indices(self) -> List[int]:
        indices = []
        for i in range(self._offset_list.count()):
            item = self._offset_list.item(i)
            if item.checkState() == Checked:
                idx = item.data(UserRole)
                if idx is not None:
                    indices.append(idx)
        return indices

    def get_target_subplot_key(self) -> str:
        return self._subplot_combo.currentData() or ""

    def _select_all(self) -> None:
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Checked)

    def _deselect_all(self) -> None:
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Unchecked)


class DataTree(QWidget):
    """Hierarchical subplot/data tree with drag-drop, checkboxes, and selection signals."""

    selection_changed = Signal(str, str)
    data_visibility_changed = Signal(str, bool)
    data_moved = Signal(str, str)
    structure_changed = Signal()
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._model: Optional[FigureModel] = None
        self._offset_labels: List[str] = []
        self._spectrum_available: List[bool] = []
        self._populating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(4, 4, 4, 4)
        self._back_btn = QPushButton("< Back")
        self._back_btn.setFixedWidth(70)
        self._back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self._back_btn)
        self._title_label = QLabel("Data Tree")
        self._title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header.addWidget(self._title_label, stretch=1)
        layout.addLayout(header)

        # Grid layout controls
        grid_row = QHBoxLayout()
        grid_row.setContentsMargins(4, 0, 4, 0)
        grid_row.addWidget(QLabel("Grid:"))

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 10)
        self._rows_spin.setValue(1)
        self._rows_spin.setToolTip("Number of rows")
        self._rows_spin.setFixedWidth(50)
        self._rows_spin.valueChanged.connect(self._on_grid_spinbox_changed)
        grid_row.addWidget(self._rows_spin)
        grid_row.addWidget(QLabel("\u00d7"))  # multiplication sign

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 10)
        self._cols_spin.setValue(1)
        self._cols_spin.setToolTip("Number of columns")
        self._cols_spin.setFixedWidth(50)
        self._cols_spin.valueChanged.connect(self._on_grid_spinbox_changed)
        grid_row.addWidget(self._cols_spin)

        self._add_row_btn = QPushButton("+ Row")
        self._add_row_btn.setToolTip("Add a row of subplots")
        self._add_row_btn.clicked.connect(self._on_add_row)
        grid_row.addWidget(self._add_row_btn)

        self._add_col_btn = QPushButton("+ Col")
        self._add_col_btn.setToolTip("Add a column of subplots")
        self._add_col_btn.clicked.connect(self._on_add_col)
        grid_row.addWidget(self._add_col_btn)

        grid_row.addStretch()
        layout.addLayout(grid_row)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 0, 4, 0)
        self._add_data_btn = QPushButton("+ Data")
        self._add_data_btn.setToolTip("Add data series to a subplot (pick offsets)")
        self._add_data_btn.clicked.connect(self._on_add_data)
        toolbar.addWidget(self._add_data_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Remove selected subplot or data series")
        self._remove_btn.clicked.connect(self._on_remove)
        toolbar.addWidget(self._remove_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._tree = _DragDropTree()
        self._tree.setHeaderLabels(["Name", "Index"])
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnWidth(1, 50)
        self._tree.setDragDropMode(InternalMove)
        self._tree.setDefaultDropAction(MoveAction)
        try:
            self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        except AttributeError:
            self._tree.setSelectionMode(QTreeWidget.SingleSelection)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.items_dropped.connect(self._on_items_dropped)
        layout.addWidget(self._tree, stretch=1)

    def set_offset_labels(self, labels: List[str]) -> None:
        """Store offset labels for the offset picker dialog."""
        self._offset_labels = list(labels)

    def set_spectrum_availability(self, flags: List[bool]) -> None:
        """Store which offsets have spectrum data available."""
        self._spectrum_available = list(flags)

    def populate(self, model: FigureModel) -> None:
        """Rebuild the tree from the given FigureModel."""
        self._populating = True
        self._model = model
        self._tree.clear()

        self._rows_spin.blockSignals(True)
        self._cols_spin.blockSignals(True)
        self._rows_spin.setValue(model.layout_rows)
        self._cols_spin.setValue(model.layout_cols)
        self._rows_spin.blockSignals(False)
        self._cols_spin.blockSignals(False)

        for sp in model.subplots:
            sp_item = QTreeWidgetItem()
            sp_item.setText(0, sp.title or sp.key)
            sp_item.setText(1, "")
            sp_item.setData(0, _ROLE_TYPE, _TYPE_SUBPLOT)
            sp_item.setData(0, _ROLE_KEY, sp.key)
            sp_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsDropEnabled
            )
            font = sp_item.font(0)
            font.setBold(True)
            sp_item.setFont(0, font)
            self._tree.addTopLevelItem(sp_item)

            for ds in model.series_for_subplot(sp.key):
                ds_item = QTreeWidgetItem(sp_item)
                ds_item.setText(0, ds.label or f"Offset {ds.offset_index}")
                ds_item.setText(1, str(ds.offset_index))
                ds_item.setData(0, _ROLE_TYPE, _TYPE_DATA)
                ds_item.setData(0, _ROLE_KEY, ds.uid)
                ds_item.setCheckState(0, Checked if ds.visible else Unchecked)
                ds_item.setFlags(
                    ItemIsEnabled | ItemIsSelectable
                    | ItemIsUserCheckable | ItemIsDragEnabled
                )
                if ds.color:
                    px = QtGui.QPixmap(14, 14)
                    px.fill(QtGui.QColor(ds.color))
                    ds_item.setIcon(0, QtGui.QIcon(px))

                # Sub-layer: Spectrum Background (only if data exists)
                has_spec = (
                    ds.offset_index < len(self._spectrum_available)
                    and self._spectrum_available[ds.offset_index]
                )
                if has_spec:
                    spec_item = QTreeWidgetItem(ds_item)
                    spec_item.setText(0, "Spectrum Background")
                    spec_item.setData(0, _ROLE_TYPE, _TYPE_SPECTRUM)
                    spec_item.setData(0, _ROLE_KEY, ds.uid)
                    spec_item.setCheckState(
                        0, Checked if ds.spectrum.visible else Unchecked,
                    )
                    spec_item.setFlags(
                        ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
                    )

                # Sub-layer: Near-Field Effect (only if spectrum exists —
                # NF is only meaningful when we have spectrum data)
                if has_spec:
                    nf_item = QTreeWidgetItem(ds_item)
                    nf_item.setText(0, "Near-Field Effect")
                    nf_item.setData(0, _ROLE_TYPE, _TYPE_NEARFIELD)
                    nf_item.setData(0, _ROLE_KEY, ds.uid)
                    nf_item.setCheckState(
                        0, Checked if ds.near_field.visible else Unchecked,
                    )
                    nf_item.setFlags(
                        ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
                    )

            sp_item.setExpanded(True)

        self._populating = False

    def current_selection(self) -> tuple:
        """Return (item_type, key) for the current selection.

        item_type is 'subplot', 'data', 'spectrum', 'nearfield', or 'none'.
        """
        items = self._tree.selectedItems()
        if not items:
            return ("none", "")
        item = items[0]
        itype = item.data(0, _ROLE_TYPE)
        key = item.data(0, _ROLE_KEY)
        return (itype or "none", key or "")

    def select_by_key(self, key: str, item_type: str = "") -> None:
        """Programmatically select by key, optionally filtering by item type."""
        for i in range(self._tree.topLevelItemCount()):
            sp_item = self._tree.topLevelItem(i)
            if sp_item.data(0, _ROLE_KEY) == key and (
                not item_type or item_type == _TYPE_SUBPLOT
            ):
                self._tree.setCurrentItem(sp_item)
                return
            for j in range(sp_item.childCount()):
                ds_item = sp_item.child(j)
                if ds_item.data(0, _ROLE_KEY) == key and (
                    not item_type or item_type == _TYPE_DATA
                ):
                    self._tree.setCurrentItem(ds_item)
                    return
                # Check sub-layers
                for k in range(ds_item.childCount()):
                    sub = ds_item.child(k)
                    if (
                        sub.data(0, _ROLE_KEY) == key
                        and (not item_type or sub.data(0, _ROLE_TYPE) == item_type)
                    ):
                        self._tree.setCurrentItem(sub)
                        return

    def _on_selection_changed(self) -> None:
        if self._populating:
            return
        itype, key = self.current_selection()
        self.selection_changed.emit(itype, key)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._populating:
            return
        if column != 0:
            return
        itype = item.data(0, _ROLE_TYPE)
        uid = item.data(0, _ROLE_KEY)
        checked = item.checkState(0) == Checked

        if itype == _TYPE_DATA:
            if self._model:
                ds = self._model.series_by_uid(uid)
                if ds:
                    ds.visible = checked
            self.data_visibility_changed.emit(uid, checked)
        elif itype == _TYPE_SPECTRUM:
            if self._model:
                ds = self._model.series_by_uid(uid)
                if ds:
                    ds.spectrum.visible = checked
            self.data_visibility_changed.emit(uid, checked)
        elif itype == _TYPE_NEARFIELD:
            if self._model:
                ds = self._model.series_by_uid(uid)
                if ds:
                    ds.near_field.visible = checked
            self.data_visibility_changed.emit(uid, checked)

    def _on_grid_spinbox_changed(self) -> None:
        if not self._model or self._populating:
            return
        new_rows = self._rows_spin.value()
        new_cols = self._cols_spin.value()
        if new_rows == self._model.layout_rows and new_cols == self._model.layout_cols:
            return
        self._model.resize_grid(new_rows, new_cols)
        self.populate(self._model)
        self.structure_changed.emit()

    def _on_add_row(self) -> None:
        if not self._model:
            return
        self._model.resize_grid(self._model.layout_rows + 1, self._model.layout_cols)
        self.populate(self._model)
        self.structure_changed.emit()

    def _on_add_col(self) -> None:
        if not self._model:
            return
        self._model.resize_grid(self._model.layout_rows, self._model.layout_cols + 1)
        self.populate(self._model)
        self.structure_changed.emit()

    def _on_add_data(self) -> None:
        if not self._model:
            return
        if not self._model.subplots:
            return

        subplot_names = [(sp.key, sp.title or sp.key) for sp in self._model.subplots]

        # Pre-select the subplot based on current tree selection
        preselect_key = ""
        items = self._tree.selectedItems()
        if items:
            item = items[0]
            itype = item.data(0, _ROLE_TYPE)
            if itype == _TYPE_SUBPLOT:
                preselect_key = item.data(0, _ROLE_KEY)
            elif itype == _TYPE_DATA:
                parent = item.parent()
                if parent:
                    preselect_key = parent.data(0, _ROLE_KEY)

        labels = self._offset_labels or [f"Offset {i}" for i in range(20)]
        dialog = _OffsetPickerDialog(labels, subplot_names, parent=self)

        if preselect_key:
            idx = dialog._subplot_combo.findData(preselect_key)
            if idx >= 0:
                dialog._subplot_combo.setCurrentIndex(idx)

        if dialog.exec() != DialogAccepted:
            return

        selected_indices = dialog.get_selected_indices()
        target_key = dialog.get_target_subplot_key()
        if not selected_indices or not target_key:
            return

        for idx in selected_indices:
            lbl = labels[idx] if idx < len(labels) else f"Offset {idx}"
            self._model.add_data_series(target_key, idx, lbl)

        self.populate(self._model)
        self.structure_changed.emit()

    def _on_remove(self) -> None:
        if not self._model:
            return
        items = self._tree.selectedItems()
        if not items:
            return
        item = items[0]
        itype = item.data(0, _ROLE_TYPE)
        key = item.data(0, _ROLE_KEY)
        if itype == _TYPE_SUBPLOT:
            self._model.remove_subplot(key)
        elif itype == _TYPE_DATA:
            self._model.remove_series(key)
        self.populate(self._model)
        self.structure_changed.emit()

    def _on_items_dropped(self) -> None:
        """Called after the QTreeWidget completes an internal drag-drop."""
        self.sync_model_from_tree()
        self.populate(self._model)

    def sync_model_from_tree(self) -> None:
        """Sync data series subplot assignment after drag-drop reorder."""
        if not self._model:
            return
        changed = False
        for i in range(self._tree.topLevelItemCount()):
            sp_item = self._tree.topLevelItem(i)
            sp_key = sp_item.data(0, _ROLE_KEY)
            for j in range(sp_item.childCount()):
                ds_item = sp_item.child(j)
                if ds_item.data(0, _ROLE_TYPE) != _TYPE_DATA:
                    continue
                uid = ds_item.data(0, _ROLE_KEY)
                ds = self._model.series_by_uid(uid)
                if ds and ds.subplot_key != sp_key:
                    ds.subplot_key = sp_key
                    changed = True
        if changed:
            self.structure_changed.emit()
