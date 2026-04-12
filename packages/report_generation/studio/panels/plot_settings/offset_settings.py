"""Settings widget for source-offset analysis plot types.

Provides a multi-offset checklist (select which offsets to include),
subplot assignment table, spectrum toggle, and grid layout controls.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ...qt_compat import (
    QtWidgets, QtCore,
    ItemIsUserCheckable, Checked, Unchecked, UserRole,
)

QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QPushButton = QtWidgets.QPushButton
QTableWidget = QtWidgets.QTableWidget
QTableWidgetItem = QtWidgets.QTableWidgetItem
QComboBox = QtWidgets.QComboBox
QLabel = QtWidgets.QLabel

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class OffsetSettings(BasePlotSettingsWidget):
    """Settings for offset_curve_only, offset_with_spectrum, offset_spectrum_only."""

    def __init__(self, offset_labels: list | None = None,
                 spectrum_flags: list | None = None, parent=None):
        super().__init__(parent)
        self._labels = offset_labels or []
        spec_flags = spectrum_flags or [False] * len(self._labels)
        self._updating_assignment = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Grid layout (moved above offset selection so it drives assignment) --
        grid_group = QGroupBox("Grid Layout")
        grid_form = QFormLayout(grid_group)

        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 10)
        self._grid_rows.setSpecialValueText("Auto")
        self._grid_rows.valueChanged.connect(self._on_grid_changed)
        grid_form.addRow("Rows:", self._grid_rows)

        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 10)
        self._grid_cols.setSpecialValueText("Auto")
        self._grid_cols.valueChanged.connect(self._on_grid_changed)
        grid_form.addRow("Columns:", self._grid_cols)

        layout.addWidget(grid_group)

        # -- Offset selection (multi-select checklist) --
        sel_group = QGroupBox("Select Offsets")
        sel_layout = QVBoxLayout(sel_group)

        btn_row = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._select_all)
        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(self._deselect_all)
        btn_row.addWidget(self._select_all_btn)
        btn_row.addWidget(self._deselect_all_btn)
        btn_row.addStretch()
        sel_layout.addLayout(btn_row)

        self._offset_list = QListWidget()
        self._offset_list.setMinimumHeight(100)
        self._offset_list.setMaximumHeight(220)
        for i, label in enumerate(self._labels):
            display = label
            if i < len(spec_flags) and spec_flags[i]:
                display += " [+spectrum]"
            item = QListWidgetItem(display)
            item.setFlags(item.flags() | ItemIsUserCheckable)
            item.setCheckState(Unchecked)
            item.setData(UserRole, i)
            self._offset_list.addItem(item)
        if self._labels:
            first = self._offset_list.item(0)
            if first:
                first.setCheckState(Checked)
        self._offset_list.itemChanged.connect(self._on_offset_selection_changed)
        sel_layout.addWidget(self._offset_list)

        layout.addWidget(sel_group)

        # -- Subplot assignment table --
        assign_group = QGroupBox("Subplot Assignment")
        assign_layout = QVBoxLayout(assign_group)

        assign_layout.addWidget(QLabel(
            "Assign each offset to a subplot position:"
        ))

        self._assign_table = QTableWidget(0, 2)
        self._assign_table.setHorizontalHeaderLabels(["Offset", "Subplot"])
        self._assign_table.horizontalHeader().setStretchLastSection(True)
        try:
            self._assign_table.setEditTriggers(
                QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
            )
            self._assign_table.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.NoSelection
            )
        except AttributeError:
            self._assign_table.setEditTriggers(
                QtWidgets.QAbstractItemView.NoEditTriggers
            )
            self._assign_table.setSelectionMode(
                QtWidgets.QAbstractItemView.NoSelection
            )
        self._assign_table.setMinimumHeight(80)
        self._assign_table.setMaximumHeight(200)
        self._assign_table.verticalHeader().setVisible(False)
        assign_layout.addWidget(self._assign_table)

        auto_btn = QPushButton("Auto-Assign Sequential")
        auto_btn.setToolTip("Automatically assign one offset per subplot in order")
        auto_btn.clicked.connect(self._auto_assign_sequential)
        assign_layout.addWidget(auto_btn)

        layout.addWidget(assign_group)

        # -- Spectrum toggle --
        spec_group = QGroupBox("Spectrum in Plot")
        spec_form = QFormLayout(spec_group)

        self._include_spectrum = QCheckBox("Include spectrum background")
        self._include_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._include_spectrum)

        layout.addWidget(spec_group)
        layout.addStretch()

        # Initial population
        self._rebuild_assignment_table()

    # ── Public API ────────────────────────────────────────────────

    def get_selected_indices(self) -> List[int]:
        indices = []
        for i in range(self._offset_list.count()):
            item = self._offset_list.item(i)
            if item.checkState() == Checked:
                idx = item.data(UserRole)
                if idx is not None:
                    indices.append(idx)
        return indices

    @property
    def offset_index(self) -> int:
        """First selected offset index (backward compat)."""
        sel = self.get_selected_indices()
        return sel[0] if sel else 0

    @property
    def grid_rows(self) -> int | None:
        v = self._grid_rows.value()
        return v if v > 0 else None

    @property
    def grid_cols(self) -> int | None:
        v = self._grid_cols.value()
        return v if v > 0 else None

    @property
    def include_spectrum(self) -> bool:
        return self._include_spectrum.isChecked()

    def get_assignment_map(self) -> Dict[int, Tuple[int, int]]:
        """Return {offset_index: (row, col)} from the assignment table."""
        result: Dict[int, Tuple[int, int]] = {}
        for row in range(self._assign_table.rowCount()):
            label_item = self._assign_table.item(row, 0)
            if label_item is None:
                continue
            offset_idx = label_item.data(UserRole)
            if offset_idx is None:
                continue
            combo = self._assign_table.cellWidget(row, 1)
            if combo is None:
                continue
            pos = combo.currentData()
            if pos is not None:
                result[offset_idx] = pos
        return result

    def write_to(self, settings: ReportStudioSettings) -> None:
        pass

    def read_from(self, settings: ReportStudioSettings) -> None:
        pass

    # ── Internal ──────────────────────────────────────────────────

    def _effective_grid(self) -> Tuple[int, int]:
        """Compute the effective grid size from current settings."""
        selected = self.get_selected_indices()
        n = max(len(selected), 1)

        cols = self._grid_cols.value()
        if cols <= 0:
            cols = min(n, 4)
        rows = self._grid_rows.value()
        if rows <= 0:
            import math
            rows = math.ceil(n / cols) if cols else 1
        return rows, cols

    def _subplot_positions(self) -> List[Tuple[int, int]]:
        """All (row, col) positions in the effective grid."""
        rows, cols = self._effective_grid()
        return [(r, c) for r in range(rows) for c in range(cols)]

    def _rebuild_assignment_table(self) -> None:
        """Rebuild the assignment table based on selected offsets and grid."""
        self._updating_assignment = True
        selected = self.get_selected_indices()
        positions = self._subplot_positions()

        self._assign_table.setRowCount(len(selected))

        for table_row, offset_idx in enumerate(selected):
            lbl = (self._labels[offset_idx]
                   if offset_idx < len(self._labels)
                   else f"Offset {offset_idx}")

            label_item = QTableWidgetItem(lbl)
            label_item.setData(UserRole, offset_idx)
            self._assign_table.setItem(table_row, 0, label_item)

            combo = QComboBox()
            for r, c in positions:
                combo.addItem(f"({r+1}, {c+1})", (r, c))
            # Default: sequential assignment
            default_pos = table_row if table_row < len(positions) else len(positions) - 1
            if default_pos >= 0:
                combo.setCurrentIndex(max(0, default_pos))
            combo.currentIndexChanged.connect(
                lambda _: self.changed.emit()
            )
            self._assign_table.setCellWidget(table_row, 1, combo)

        self._updating_assignment = False

    def _on_offset_selection_changed(self) -> None:
        self._rebuild_assignment_table()
        self.changed.emit()

    def _on_grid_changed(self) -> None:
        self._rebuild_assignment_table()
        self.changed.emit()

    def _auto_assign_sequential(self) -> None:
        """Re-assign offsets sequentially: one per subplot."""
        positions = self._subplot_positions()
        for row in range(self._assign_table.rowCount()):
            combo = self._assign_table.cellWidget(row, 1)
            if combo is None:
                continue
            idx = row if row < len(positions) else len(positions) - 1
            combo.setCurrentIndex(max(0, idx))
        self.changed.emit()

    def _select_all(self) -> None:
        self._offset_list.blockSignals(True)
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Checked)
        self._offset_list.blockSignals(False)
        self._rebuild_assignment_table()
        self.changed.emit()

    def _deselect_all(self) -> None:
        self._offset_list.blockSignals(True)
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Unchecked)
        self._offset_list.blockSignals(False)
        self._rebuild_assignment_table()
        self.changed.emit()
