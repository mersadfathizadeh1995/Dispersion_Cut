"""
Data assignment dialog — configure grid and assign curves to subplots.

Shown after loading data so the user can:
1. Set the grid layout (rows × cols)
2. Drag-and-drop or select which curves go into which subplot
3. Preview the arrangement before committing
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    DialogAccepted, DialogRejected,
    Horizontal, Vertical,
)

if TYPE_CHECKING:
    from ...core.models import OffsetCurve


# Qt flags with compat
def _ItemIsEnabled():
    try:
        return QtCore.Qt.ItemFlag.ItemIsEnabled
    except AttributeError:
        return QtCore.Qt.ItemIsEnabled

def _ItemIsSelectable():
    try:
        return QtCore.Qt.ItemFlag.ItemIsSelectable
    except AttributeError:
        return QtCore.Qt.ItemIsSelectable

def _Checked():
    try:
        return QtCore.Qt.CheckState.Checked
    except AttributeError:
        return QtCore.Qt.Checked

def _Unchecked():
    try:
        return QtCore.Qt.CheckState.Unchecked
    except AttributeError:
        return QtCore.Qt.Unchecked


class AssignmentDialog(QtWidgets.QDialog):
    """
    Grid-first data assignment dialog.

    Shows loaded curves on the left, grid preview on the right.
    User picks grid size, then drags/assigns curves to subplot slots.
    """

    def __init__(self, curves: List["OffsetCurve"], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Arrange Subplots")
        self.setMinimumSize(700, 500)
        self.resize(800, 550)

        self._curves = list(curves)
        self._grid_rows = 1
        self._grid_cols = 1
        # mapping: subplot_key → list of curve UIDs
        self._assignments: Dict[str, List[str]] = {"main": [c.uid for c in curves]}

        self._build_ui()
        self._refresh_assignment_view()

    # ── Result getters ────────────────────────────────────────────────

    @property
    def grid_rows(self) -> int:
        return self._grid_rows

    @property
    def grid_cols(self) -> int:
        return self._grid_cols

    @property
    def assignments(self) -> Dict[str, List[str]]:
        """subplot_key → list of curve UIDs."""
        return dict(self._assignments)

    # ── Build UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # ── Top bar: grid size ────────────────────────────────────────
        grid_bar = QtWidgets.QHBoxLayout()
        grid_bar.addWidget(QtWidgets.QLabel("Grid:"))

        self._spin_rows = QtWidgets.QSpinBox()
        self._spin_rows.setRange(1, 6)
        self._spin_rows.setValue(1)
        self._spin_rows.setPrefix("Rows: ")
        self._spin_rows.valueChanged.connect(self._on_grid_changed)
        grid_bar.addWidget(self._spin_rows)

        grid_bar.addWidget(QtWidgets.QLabel("×"))

        self._spin_cols = QtWidgets.QSpinBox()
        self._spin_cols.setRange(1, 6)
        self._spin_cols.setValue(1)
        self._spin_cols.setPrefix("Cols: ")
        self._spin_cols.valueChanged.connect(self._on_grid_changed)
        grid_bar.addWidget(self._spin_cols)

        grid_bar.addStretch()

        # Quick layout presets
        for label, r, c in [("1×1", 1, 1), ("2×1", 2, 1), ("1×2", 1, 2),
                             ("2×2", 2, 2), ("3×1", 3, 1)]:
            btn = QtWidgets.QPushButton(label)
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda _, rr=r, cc=c: self._set_grid(rr, cc))
            grid_bar.addWidget(btn)

        main_layout.addLayout(grid_bar)

        # ── Center: source list ↔ subplot slots ───────────────────────
        center = QtWidgets.QHBoxLayout()

        # Left: available curves (source list)
        left_frame = QtWidgets.QGroupBox("Available Curves")
        left_layout = QtWidgets.QVBoxLayout(left_frame)

        self._source_list = QtWidgets.QListWidget()
        try:
            self._source_list.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        except AttributeError:
            self._source_list.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection)
        self._source_list.setDragEnabled(True)

        for curve in self._curves:
            item = QtWidgets.QListWidgetItem(curve.display_name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole
                         if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                         else QtCore.Qt.UserRole,
                         curve.uid)
            if curve.color:
                px = QtGui.QPixmap(12, 12)
                px.fill(QtGui.QColor(curve.color))
                item.setIcon(QtGui.QIcon(px))
            self._source_list.addItem(item)

        left_layout.addWidget(self._source_list)

        # Assign selected → target
        btn_row = QtWidgets.QHBoxLayout()
        self._btn_assign = QtWidgets.QPushButton("Assign →")
        self._btn_assign.setToolTip("Assign selected curves to the selected subplot")
        self._btn_assign.clicked.connect(self._on_assign)
        btn_row.addWidget(self._btn_assign)

        self._btn_unassign = QtWidgets.QPushButton("← Remove")
        self._btn_unassign.setToolTip("Remove selected curves from their subplot")
        self._btn_unassign.clicked.connect(self._on_unassign)
        btn_row.addWidget(self._btn_unassign)

        self._btn_assign_all = QtWidgets.QPushButton("All →")
        self._btn_assign_all.setToolTip("Assign all curves to the selected subplot")
        self._btn_assign_all.clicked.connect(self._on_assign_all)
        btn_row.addWidget(self._btn_assign_all)

        left_layout.addLayout(btn_row)
        center.addWidget(left_frame, stretch=1)

        # Right: subplot slots (tree showing subplots with assigned curves)
        right_frame = QtWidgets.QGroupBox("Subplot Assignments")
        right_layout = QtWidgets.QVBoxLayout(right_frame)

        self._assign_tree = QtWidgets.QTreeWidget()
        self._assign_tree.setHeaderHidden(True)
        self._assign_tree.setColumnCount(1)
        right_layout.addWidget(self._assign_tree)

        center.addWidget(right_frame, stretch=1)

        main_layout.addLayout(center, stretch=1)

        # ── Bottom: OK / Cancel ───────────────────────────────────────
        try:
            ok_btn = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            ok_btn = QtWidgets.QDialogButtonBox.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.Cancel

        btn_box = QtWidgets.QDialogButtonBox(ok_btn | cancel_btn)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    # ── Grid management ───────────────────────────────────────────────

    def _set_grid(self, rows: int, cols: int):
        self._spin_rows.setValue(rows)
        self._spin_cols.setValue(cols)

    def _on_grid_changed(self):
        new_r = self._spin_rows.value()
        new_c = self._spin_cols.value()
        self._grid_rows = new_r
        self._grid_cols = new_c

        # Build new subplot keys
        if new_r == 1 and new_c == 1:
            new_keys = ["main"]
        else:
            new_keys = [f"cell_{r}_{c}" for r in range(new_r) for c in range(new_c)]

        # Collect all currently assigned UIDs
        all_uids = []
        for uid_list in self._assignments.values():
            all_uids.extend(uid_list)

        # Rebuild assignments — put all into first subplot initially
        self._assignments = {}
        for key in new_keys:
            self._assignments[key] = []
        if all_uids and new_keys:
            self._assignments[new_keys[0]] = all_uids

        self._refresh_assignment_view()

    def _subplot_display_name(self, key: str) -> str:
        if key == "main":
            return "Main"
        parts = key.split("_")
        if len(parts) == 3:
            return f"Row {int(parts[1])+1}, Col {int(parts[2])+1}"
        return key

    # ── Assignment view refresh ───────────────────────────────────────

    def _refresh_assignment_view(self):
        """Rebuild the assignment tree from self._assignments."""
        self._assign_tree.clear()
        uid_to_curve = {c.uid: c for c in self._curves}

        for key in self._assignments:
            sp_item = QtWidgets.QTreeWidgetItem(
                [self._subplot_display_name(key)])
            sp_item.setData(0, QtCore.Qt.ItemDataRole.UserRole
                            if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                            else QtCore.Qt.UserRole,
                            key)
            font = sp_item.font(0)
            font.setBold(True)
            sp_item.setFont(0, font)
            sp_item.setFlags(_ItemIsEnabled() | _ItemIsSelectable())

            for uid in self._assignments[key]:
                curve = uid_to_curve.get(uid)
                if not curve:
                    continue
                c_item = QtWidgets.QTreeWidgetItem([curve.display_name])
                c_item.setData(0, QtCore.Qt.ItemDataRole.UserRole
                               if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                               else QtCore.Qt.UserRole,
                               uid)
                if curve.color:
                    px = QtGui.QPixmap(12, 12)
                    px.fill(QtGui.QColor(curve.color))
                    c_item.setIcon(0, QtGui.QIcon(px))
                c_item.setFlags(_ItemIsEnabled() | _ItemIsSelectable())
                sp_item.addChild(c_item)

            self._assign_tree.addTopLevelItem(sp_item)
            sp_item.setExpanded(True)

        # Update source list (dim already-assigned curves)
        assigned_set = set()
        for uid_list in self._assignments.values():
            assigned_set.update(uid_list)

        for i in range(self._source_list.count()):
            item = self._source_list.item(i)
            uid = item.data(QtCore.Qt.ItemDataRole.UserRole
                            if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                            else QtCore.Qt.UserRole)
            if uid in assigned_set:
                item.setForeground(QtGui.QColor("#999999"))
            else:
                item.setForeground(QtGui.QColor("#000000"))

    # ── Assign / unassign ─────────────────────────────────────────────

    def _get_target_subplot_key(self) -> Optional[str]:
        """Get the currently selected subplot key in the assignment tree."""
        item = self._assign_tree.currentItem()
        if not item:
            return None
        # If a curve item is selected, use its parent subplot
        parent = item.parent()
        if parent:
            item = parent
        role = (QtCore.Qt.ItemDataRole.UserRole
                if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                else QtCore.Qt.UserRole)
        key = item.data(0, role)
        return key if key in self._assignments else None

    def _on_assign(self):
        """Assign selected curves from source to selected subplot."""
        target = self._get_target_subplot_key()
        if not target:
            # Default to first subplot
            keys = list(self._assignments.keys())
            target = keys[0] if keys else None
        if not target:
            return

        role = (QtCore.Qt.ItemDataRole.UserRole
                if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                else QtCore.Qt.UserRole)

        for sel_item in self._source_list.selectedItems():
            uid = sel_item.data(role)
            if not uid:
                continue
            # Remove from current subplot if already assigned
            for key in self._assignments:
                if uid in self._assignments[key]:
                    self._assignments[key].remove(uid)
            self._assignments[target].append(uid)

        self._refresh_assignment_view()

    def _on_assign_all(self):
        """Assign all curves to the selected subplot."""
        target = self._get_target_subplot_key()
        if not target:
            keys = list(self._assignments.keys())
            target = keys[0] if keys else None
        if not target:
            return

        all_uids = [c.uid for c in self._curves]
        # Clear all assignments
        for key in self._assignments:
            self._assignments[key] = []
        self._assignments[target] = all_uids
        self._refresh_assignment_view()

    def _on_unassign(self):
        """Remove selected curves from their subplot in the assignment tree."""
        item = self._assign_tree.currentItem()
        if not item or not item.parent():
            return  # Must be a curve item (has parent)

        role = (QtCore.Qt.ItemDataRole.UserRole
                if hasattr(QtCore.Qt.ItemDataRole, "UserRole")
                else QtCore.Qt.UserRole)
        uid = item.data(0, role)
        if not uid:
            return

        for key in self._assignments:
            if uid in self._assignments[key]:
                self._assignments[key].remove(uid)
                break

        self._refresh_assignment_view()
