"""Reusable NF evaluation-range widget.

Provides a single ``NFEvalRangesWidget`` used by both the NACD-Only and
Reference tabs of the NF-Evaluation dock.  The widget shows one unified
table whose rows each describe one evaluation *band* in the user's
chosen domain:

* Kind: "Frequency (Hz)"  → ``Min``/``Max`` are interpreted as
  ``f_min`` / ``f_max``; the widget (and downstream ``derive_limits``)
  will compute matching ``λ_min``/``λ_max`` lines from the current
  ``V(f)`` curve.
* Kind: "Wavelength (m)"  → ``Min``/``Max`` are interpreted as
  ``λ_min`` / ``λ_max``; corresponding ``f_min``/``f_max`` lines are
  derived automatically.

The widget emits :meth:`get_range` values of type ``EvaluationRange``
and a ``show_lines_toggled`` signal for the master "Show limit lines"
checkbox.
"""
from __future__ import annotations

from typing import List, Tuple

from matplotlib.backends import qt_compat

from dc_cut.core.processing.nearfield.ranges import EvaluationRange

QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore

try:
    _Stretch = QtWidgets.QHeaderView.Stretch
    _ResizeToContents = QtWidgets.QHeaderView.ResizeToContents
except AttributeError:
    _Stretch = QtWidgets.QHeaderView.ResizeMode.Stretch
    _ResizeToContents = QtWidgets.QHeaderView.ResizeMode.ResizeToContents


KIND_FREQ = "Frequency (Hz)"
KIND_WAVE = "Wavelength (m)"


# Stylesheet that forces readable foreground/background on the Kind
# QComboBox regardless of the active application palette / Qt style.
# Without this, some styles render the embedded combo with a pitch-black
# background inside the table cell.
_COMBO_QSS = (
    "QComboBox { "
    "  background-color: palette(base); "
    "  color: palette(text); "
    "  border: 1px solid palette(mid); "
    "  padding: 1px 4px; "
    "} "
    "QComboBox:hover { border-color: palette(highlight); } "
    "QComboBox::drop-down { border: 0; } "
    "QComboBox QAbstractItemView { "
    "  background-color: palette(base); "
    "  color: palette(text); "
    "  selection-background-color: palette(highlight); "
    "  selection-color: palette(highlighted-text); "
    "}"
)


class NFEvalRangesWidget(QtWidgets.QWidget):
    """Widget for selecting NF evaluation ranges.

    Signals
    -------
    range_changed :
        Emitted whenever a row is added / removed / its kind is changed
        / a numeric cell edited.
    show_lines_toggled(bool) :
        Emitted when the user toggles the master "Show limit lines"
        checkbox.
    """

    range_changed = QtCore.Signal()
    show_lines_toggled = QtCore.Signal(bool)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        outer.addWidget(QtWidgets.QLabel("Evaluation ranges (empty = full range):"))

        self._table = QtWidgets.QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Kind", "Min", "Max"])
        self._table.setMaximumHeight(140)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, _ResizeToContents)
        hdr.setSectionResizeMode(1, _Stretch)
        hdr.setSectionResizeMode(2, _Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
            if hasattr(QtWidgets.QAbstractItemView, "SelectRows")
            else QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.itemChanged.connect(self._on_cell_changed)
        outer.addWidget(self._table)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("+ Add Range")
        add_btn.clicked.connect(self._add_row_default)
        rem_btn = QtWidgets.QPushButton("− Remove")
        rem_btn.clicked.connect(self._remove_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(rem_btn)
        outer.addLayout(btn_row)

        self._show_lines = QtWidgets.QCheckBox("Show limit lines")
        self._show_lines.setChecked(True)
        self._show_lines.toggled.connect(self.show_lines_toggled)
        outer.addWidget(self._show_lines)

    # ── public API ───────────────────────────────────────────────────
    def get_range(self) -> EvaluationRange:
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
        return EvaluationRange(
            freq_bands=freq_bands,
            lambda_bands=lam_bands,
        )

    def set_range(self, rng: EvaluationRange | None) -> None:
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        if rng is not None:
            for lo, hi in rng.freq_bands:
                self._append_row(KIND_FREQ, lo, hi)
            for lo, hi in rng.lambda_bands:
                self._append_row(KIND_WAVE, lo, hi)
            # Migrate legacy global λ clamps into a single λ-band row.
            legacy_lo = rng.lambda_min or 0.0
            legacy_hi = rng.lambda_max or 0.0
            if (legacy_lo > 0 or legacy_hi > 0) and not rng.lambda_bands:
                # Use finite defaults for open ends so the row is valid.
                row_lo = legacy_lo if legacy_lo > 0 else 0.0
                row_hi = legacy_hi if legacy_hi > 0 else 0.0
                if row_hi > row_lo:
                    self._append_row(KIND_WAVE, row_lo, row_hi)
        self._table.blockSignals(False)

    def show_lines(self) -> bool:
        return self._show_lines.isChecked()

    def set_show_lines(self, checked: bool) -> None:
        self._show_lines.setChecked(bool(checked))

    def set_editing_enabled(self, enabled: bool, *, reason: str = "") -> None:
        """Enable / disable the whole ranges editor.

        When disabled, the table, add/remove buttons and "Show limit
        lines" checkbox are greyed out and carry *reason* as a tooltip.
        """
        enabled = bool(enabled)
        self._table.setEnabled(enabled)
        self._show_lines.setEnabled(enabled)
        for btn in self.findChildren(QtWidgets.QPushButton):
            btn.setEnabled(enabled)
        tip = reason if not enabled else ""
        self.setToolTip(tip)
        self._table.setToolTip(tip)

    # ── internals ────────────────────────────────────────────────────
    def _kind_combo(self, current: str = KIND_FREQ) -> QtWidgets.QComboBox:
        combo = QtWidgets.QComboBox(self._table)
        combo.addItems([KIND_FREQ, KIND_WAVE])
        idx = combo.findText(current)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setStyleSheet(_COMBO_QSS)
        combo.currentIndexChanged.connect(
            lambda _ix: self.range_changed.emit()
        )
        return combo

    def _append_row(self, kind: str, lo: float, hi: float) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setCellWidget(row, 0, self._kind_combo(kind))
        self._table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{lo:g}"))
        self._table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{hi:g}"))

    def _add_row_default(self) -> None:
        self._append_row(KIND_FREQ, 0.0, 0.0)

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
