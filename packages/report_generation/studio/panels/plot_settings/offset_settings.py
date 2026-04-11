"""Settings widget for source-offset analysis plot types.

Provides a multi-offset checklist (select which offsets to include),
spectrum toggle, and grid layout controls.
"""
from __future__ import annotations

from typing import List

from ...qt_compat import (
    QtWidgets,
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

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class OffsetSettings(BasePlotSettingsWidget):
    """Settings for offset_curve_only, offset_with_spectrum, offset_spectrum_only."""

    def __init__(self, offset_labels: list | None = None,
                 spectrum_flags: list | None = None, parent=None):
        super().__init__(parent)
        labels = offset_labels or []
        spec_flags = spectrum_flags or [False] * len(labels)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

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
        for i, label in enumerate(labels):
            display = label
            if i < len(spec_flags) and spec_flags[i]:
                display += " [+spectrum]"
            item = QListWidgetItem(display)
            item.setFlags(item.flags() | ItemIsUserCheckable)
            item.setCheckState(Unchecked)
            item.setData(UserRole, i)
            self._offset_list.addItem(item)
        if labels:
            first = self._offset_list.item(0)
            if first:
                first.setCheckState(Checked)
        self._offset_list.itemChanged.connect(lambda: self.changed.emit())
        sel_layout.addWidget(self._offset_list)

        layout.addWidget(sel_group)

        # -- Spectrum toggle --
        spec_group = QGroupBox("Spectrum in Plot")
        spec_form = QFormLayout(spec_group)

        self._include_spectrum = QCheckBox("Include spectrum background")
        self._include_spectrum.toggled.connect(self.changed)
        spec_form.addRow(self._include_spectrum)

        layout.addWidget(spec_group)

        # -- Grid layout --
        grid_group = QGroupBox("Grid Layout")
        grid_form = QFormLayout(grid_group)

        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(0, 10)
        self._grid_rows.setSpecialValueText("Auto")
        self._grid_rows.valueChanged.connect(self.changed)
        grid_form.addRow("Rows:", self._grid_rows)

        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(0, 10)
        self._grid_cols.setSpecialValueText("Auto")
        self._grid_cols.valueChanged.connect(self.changed)
        grid_form.addRow("Columns:", self._grid_cols)

        layout.addWidget(grid_group)
        layout.addStretch()

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

    def write_to(self, settings: ReportStudioSettings) -> None:
        pass

    def read_from(self, settings: ReportStudioSettings) -> None:
        pass

    def _select_all(self) -> None:
        self._offset_list.blockSignals(True)
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Checked)
        self._offset_list.blockSignals(False)
        self.changed.emit()

    def _deselect_all(self) -> None:
        self._offset_list.blockSignals(True)
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Unchecked)
        self._offset_list.blockSignals(False)
        self.changed.emit()
