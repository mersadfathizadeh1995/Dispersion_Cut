"""Settings widget for offset grid and NACD grid plot types.

Provides a multi-offset checkbox list, grid layout controls, and
display mode selection. Replaces the grid sections that were previously
embedded in OffsetSettings and NearFieldSettings.
"""
from __future__ import annotations

from typing import List, Optional

from ...qt_compat import (
    QtWidgets, Signal,
    ItemIsUserCheckable, Checked, Unchecked, UserRole,
)

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QListWidget = QtWidgets.QListWidget
QListWidgetItem = QtWidgets.QListWidgetItem
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
QRadioButton = QtWidgets.QRadioButton
QPushButton = QtWidgets.QPushButton

from .base import BasePlotSettingsWidget
from ...models import ReportStudioSettings


class OffsetGridSettings(BasePlotSettingsWidget):
    """Multi-offset selection + grid layout for offset_grid and nacd_grid."""

    def __init__(self, offset_labels: list | None = None,
                 spectrum_flags: list | None = None,
                 parent=None):
        super().__init__(parent)
        labels = offset_labels or []
        spec_flags = spectrum_flags or [False] * len(labels)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # -- Offset selection list --
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
            item.setCheckState(Checked)
            item.setData(UserRole, i)
            self._offset_list.addItem(item)
        self._offset_list.itemChanged.connect(lambda: self.changed.emit())
        sel_layout.addWidget(self._offset_list)

        layout.addWidget(sel_group)

        # -- Display mode --
        mode_group = QGroupBox("Display Mode")
        mode_form = QFormLayout(mode_group)

        self._mode_curves = QRadioButton("Curves only")
        self._mode_spectrum = QRadioButton("Spectrum only")
        self._mode_both = QRadioButton("Curves + Spectrum")
        self._mode_curves.setChecked(True)
        for rb in (self._mode_curves, self._mode_spectrum, self._mode_both):
            rb.toggled.connect(lambda: self.changed.emit())
        mode_form.addRow(self._mode_curves)
        mode_form.addRow(self._mode_spectrum)
        mode_form.addRow(self._mode_both)

        layout.addWidget(mode_group)

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
    def grid_rows(self) -> int | None:
        v = self._grid_rows.value()
        return v if v > 0 else None

    @property
    def grid_cols(self) -> int | None:
        v = self._grid_cols.value()
        return v if v > 0 else None

    @property
    def include_spectrum(self) -> bool:
        return self._mode_spectrum.isChecked() or self._mode_both.isChecked()

    @property
    def include_curves(self) -> bool:
        return self._mode_curves.isChecked() or self._mode_both.isChecked()

    def write_to(self, settings: ReportStudioSettings) -> None:
        selected = self.get_selected_indices()
        settings.grid_offset_indices = selected if selected else None

    def read_from(self, settings: ReportStudioSettings) -> None:
        indices = settings.grid_offset_indices
        self._offset_list.blockSignals(True)
        for i in range(self._offset_list.count()):
            item = self._offset_list.item(i)
            idx = item.data(UserRole)
            if indices is None:
                item.setCheckState(Checked)
            else:
                item.setCheckState(Checked if idx in indices else Unchecked)
        self._offset_list.blockSignals(False)

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
