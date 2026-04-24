"""Context panel for one NACD per-offset result."""

from __future__ import annotations

import numpy as np

from ...qt_compat import (
    QtWidgets,
    Signal,
    Checked,
    Unchecked,
    ItemIsEnabled,
    ItemIsSelectable,
    ItemIsUserCheckable,
)


class NFPerOffsetPanel(QtWidgets.QWidget):
    per_offset_changed = Signal(str, int, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nf_uid = ""
        self._offset_index = -1
        self._row_to_global_idx: list[int] = []
        self._hidden_mask = np.array([], dtype=bool)
        self._scatter_toggle_blocked = False
        self._list_blocked = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self._header = QtWidgets.QLabel("Select a per-offset row in the data tree.")
        self._header.setWordWrap(True)
        layout.addWidget(self._header)

        self._scatter_visible = QtWidgets.QCheckBox("Show contaminated scatter")
        self._scatter_visible.toggled.connect(self._emit_scatter_visible)
        layout.addWidget(self._scatter_visible)

        self._points = QtWidgets.QListWidget()
        self._points.itemChanged.connect(self._on_point_item_changed)
        layout.addWidget(self._points, stretch=1)

        btns = QtWidgets.QHBoxLayout()
        show_all = QtWidgets.QPushButton("Show all")
        hide_all = QtWidgets.QPushButton("Hide all")
        show_all.clicked.connect(lambda: self._set_all_hidden(False))
        hide_all.clicked.connect(lambda: self._set_all_hidden(True))
        btns.addWidget(show_all)
        btns.addWidget(hide_all)
        btns.addStretch(1)
        layout.addLayout(btns)

    def show_per_offset(self, nf, offset_index: int) -> None:
        if offset_index < 0 or offset_index >= len(nf.per_offset):
            return
        r = nf.per_offset[offset_index]
        self._nf_uid = nf.uid
        self._offset_index = int(offset_index)

        self._scatter_toggle_blocked = True
        self._scatter_visible.setChecked(bool(getattr(r, "scatter_visible", True)))
        self._scatter_toggle_blocked = False

        label = r.label or "—"
        src = "—" if r.source_offset is None else f"{float(r.source_offset):g}"
        self._header.setText(
            f"Offset: {label}\n"
            f"Source offset: {src} m\n"
            f"λ_max: {float(r.lambda_max):.2f} m\n"
            f"Flagged: {int(r.n_contaminated)}/{int(r.n_total)}"
        )

        mask = np.asarray(
            getattr(r, "mask_contaminated", np.array([], dtype=bool)), dtype=bool
        )
        hidden = getattr(r, "point_hidden", None)
        if hidden is None:
            hidden_mask = np.zeros(mask.size, dtype=bool)
        else:
            hidden_mask = np.asarray(hidden, dtype=bool)
            if hidden_mask.size != mask.size:
                hidden_mask = np.zeros(mask.size, dtype=bool)
        self._hidden_mask = hidden_mask.copy()

        f = np.asarray(getattr(r, "f", np.array([], dtype=float)), dtype=float)
        v = np.asarray(getattr(r, "v", np.array([], dtype=float)), dtype=float)

        self._row_to_global_idx = [int(i) for i, flag in enumerate(mask) if flag]
        self._list_blocked = True
        self._points.clear()
        for i in self._row_to_global_idx:
            txt = f"#{i}: f={float(f[i]):.4g} Hz, v={float(v[i]):.4g} m/s"
            item = QtWidgets.QListWidgetItem(txt)
            item.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
            item.setCheckState(Unchecked if hidden_mask[i] else Checked)
            self._points.addItem(item)
        self._list_blocked = False

    def _emit_scatter_visible(self, on: bool) -> None:
        if self._scatter_toggle_blocked or not self._nf_uid or self._offset_index < 0:
            return
        self.per_offset_changed.emit(
            self._nf_uid, self._offset_index, "scatter_visible", bool(on)
        )

    def _on_point_item_changed(self, item) -> None:
        if self._list_blocked or not self._nf_uid or self._offset_index < 0:
            return
        row = self._points.row(item)
        if row < 0 or row >= len(self._row_to_global_idx):
            return
        idx = self._row_to_global_idx[row]
        hidden = item.checkState() != Checked
        self._hidden_mask[idx] = bool(hidden)
        self.per_offset_changed.emit(
            self._nf_uid, self._offset_index, "point_hidden", self._hidden_mask.copy()
        )

    def _set_all_hidden(self, hidden: bool) -> None:
        if not self._nf_uid or self._offset_index < 0:
            return
        self._list_blocked = True
        for row, idx in enumerate(self._row_to_global_idx):
            self._hidden_mask[idx] = bool(hidden)
            item = self._points.item(row)
            if item is not None:
                item.setCheckState(Unchecked if hidden else Checked)
        self._list_blocked = False
        self.per_offset_changed.emit(
            self._nf_uid, self._offset_index, "point_hidden", self._hidden_mask.copy()
        )
