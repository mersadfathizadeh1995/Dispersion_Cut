"""Evaluation-range table for NACD limit-line derivation (Report Studio)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ...qt_compat import QtWidgets, Signal

try:
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
except ImportError:
    EvaluationRange = None  # type: ignore

try:
    _Stretch = QtWidgets.QHeaderView.Stretch
    _Interactive = QtWidgets.QHeaderView.Interactive
except AttributeError:
    _Stretch = QtWidgets.QHeaderView.ResizeMode.Stretch
    _Interactive = QtWidgets.QHeaderView.ResizeMode.Interactive

KIND_FREQ = "Frequency (Hz)"
KIND_WAVE = "Wavelength (m)"

_COMBO_QSS = (
    "QComboBox { "
    "  background-color: palette(base); "
    "  color: palette(text); "
    "  border: 1px solid palette(mid); "
    "  padding: 1px 4px; "
    "} "
    "QComboBox QAbstractItemView { "
    "  background-color: palette(base); "
    "  color: palette(text); "
    "}"
)


class NFRangesPanel(QtWidgets.QWidget):
    """Small table: kind + min/max bands, backed by :class:`EvaluationRange`."""

    range_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        outer.addWidget(
            QtWidgets.QLabel("Ranges (empty = full curve) — Apply to re-derive lines:")
        )

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Kind", "Min", "Max"])
        self._table.setMaximumHeight(160)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, _Interactive)
        hdr.setSectionResizeMode(1, _Stretch)
        hdr.setSectionResizeMode(2, _Stretch)
        self._table.setColumnWidth(0, 150)
        self._table.verticalHeader().setVisible(False)
        try:
            self._table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
        except AttributeError:
            self._table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows
            )
        self._table.itemChanged.connect(self._on_cell_changed)
        outer.addWidget(self._table)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("+ Add range")
        add_btn.clicked.connect(self._add_row_default)
        rem_btn = QtWidgets.QPushButton("− Remove")
        rem_btn.clicked.connect(self._remove_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rem_btn)
        outer.addLayout(btn_row)

    def get_range_dict(self) -> Dict[str, Any]:
        if EvaluationRange is None:
            return {}
        return self.get_range().to_dict()

    def get_range(self) -> "EvaluationRange":
        if EvaluationRange is None:
            raise RuntimeError("dc_cut EvaluationRange not available")
        freq_bands: List[Tuple[float, float]] = []
        lam_bands: List[Tuple[float, float]] = []
        for row in range(self._table.rowCount()):
            kind = self._row_kind(row)
            lo, hi = self._row_values(row)
            if lo is None or hi is None:
                continue
            if hi <= lo or hi <= 0:
                continue
            if kind == KIND_WAVE:
                lam_bands.append((lo, hi))
            else:
                freq_bands.append((lo, hi))
        return EvaluationRange(freq_bands=freq_bands, lambda_bands=lam_bands)

    def set_range_dict(self, d: Dict[str, Any] | None) -> None:
        if EvaluationRange is None:
            self._table.blockSignals(True)
            self._table.setRowCount(0)
            self._table.blockSignals(False)
            return
        rng = EvaluationRange.from_dict(d)
        self.set_range(rng)

    def set_range(self, rng) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if rng is not None:
            for lo, hi in rng.freq_bands:
                self._append_row(KIND_FREQ, lo, hi)
            for lo, hi in rng.lambda_bands:
                self._append_row(KIND_WAVE, lo, hi)
            legacy_lo = rng.lambda_min or 0.0
            legacy_hi = rng.lambda_max or 0.0
            if (legacy_lo > 0 or legacy_hi > 0) and not rng.lambda_bands:
                row_lo = legacy_lo if legacy_lo > 0 else 0.0
                row_hi = legacy_hi if legacy_hi > 0 else 0.0
                if row_hi > row_lo:
                    self._append_row(KIND_WAVE, row_lo, row_hi)
        self._table.blockSignals(False)

    def _kind_combo(self, current: str = KIND_FREQ) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox(self._table)
        combo.addItems([KIND_FREQ, KIND_WAVE])
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setStyleSheet(_COMBO_QSS)
        combo.currentIndexChanged.connect(lambda _ix: self.range_changed.emit())
        return combo

    def _append_row(self, kind: str, lo: float, hi: float) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(row, 0, self._kind_combo(kind))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{lo:g}"))
        self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{hi:g}"))

    def _add_row_default(self) -> None:
        self._append_row(KIND_FREQ, 0.0, 0.0)
        self.range_changed.emit()

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            row = self._table.rowCount() - 1
        if row >= 0:
            self._table.removeRow(row)
            self.range_changed.emit()

    def _on_cell_changed(self, *_args, **_kwargs) -> None:
        self.range_changed.emit()

    def _row_kind(self, row: int) -> str:
        combo = self._table.cellWidget(row, 0)
        if isinstance(combo, QtWidgets.QComboBox):
            return combo.currentText()
        return KIND_FREQ

    def _row_values(self, row: int):
        item_lo = self._table.item(row, 1)
        item_hi = self._table.item(row, 2)
        if item_lo is None or item_hi is None:
            return None, None
        try:
            return float(item_lo.text()), float(item_hi.text())
        except (ValueError, AttributeError):
            return None, None
