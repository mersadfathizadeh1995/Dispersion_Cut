"""Widgets for editing :class:`NACDZoneSpec`.

The multi_zone view expresses *zones* first (the colored bands and
scatter-point tints) and *thresholds* second (the vertical ``NACD = x``
markers that divide neighbouring zones).  Both kinds live on a single
:class:`ZoneGroup`; the UI keeps them in lock-step so
``len(zones) == len(thresholds) + 1`` is always true.

Public widgets:

* :class:`ZonesEditor` — the stacked Zones / Thresholds tables with
  add / remove controls that always keep the N+1 ↔ N invariant.
* :class:`SingleGroupEditor` — wraps a :class:`ZonesEditor` plus per-
  group metadata (name, label position, and an optional "Draw λ lines"
  toggle hidden by default for the multi_zone tab).
* :class:`MultiGroupEditor` — list of groups + inner group editor for
  the "Multi-zone groups" view.

Every editor emits a ``*_changed`` signal whenever any cell, button or
toggle alters the underlying spec; the NACD tab subscribes and rebuilds
the preview + limit lines on every emission.
"""
from __future__ import annotations

from typing import List

from dc_cut.core.processing.nearfield.nacd_zones import (
    ZoneFill,
    ZoneGroup,
    ZoneThreshold,
)

from .constants import QtCore, QtGui, QtWidgets, _ItemIsEditable


# ── palettes ─────────────────────────────────────────────────────────
#
# The defaults are picked so a fresh two-zone spec reads as
# "red (contaminated) / blue (clean)" out of the box, matching the
# picture the user drew:
#
#     [zone 0]────NACD─────[zone 1]
#        red     threshold     blue
#
# Additional zones cycle through the palette.  Every value is user-
# editable so the chosen palette only matters for the very first
# click.

_DEFAULT_POINT_PALETTE = [
    "#C62828",  # red      — zone 0 (contaminated)
    "#1565C0",  # blue     — zone 1 (clean)
    "#2E7D32",  # green
    "#6A1B9A",  # purple
    "#EF6C00",  # orange
]
_DEFAULT_BAND_PALETTE = [
    "#FFCDD2",  # light red
    "#BBDEFB",  # light blue
    "#C8E6C9",  # light green
    "#E1BEE7",  # light purple
    "#FFE0B2",  # light orange
]
_DEFAULT_LINE_PALETTE = [
    "#B71C1C", "#0D47A1", "#1B5E20", "#4A148C", "#E65100",
]


def _palette_color(idx: int, palette: List[str]) -> str:
    return palette[idx % len(palette)] if palette else ""


# ───────────────────────────────────────────────────────────────────
#  Colour button cell
# ───────────────────────────────────────────────────────────────────


class _ColorButton(QtWidgets.QPushButton):
    """Small square button that opens a color picker and exposes hex."""

    color_changed = QtCore.Signal(str)

    def __init__(self, hex_color: str = "", parent=None) -> None:
        super().__init__(parent)
        self._hex = hex_color or ""
        self.setFixedSize(24, 20)
        self._refresh()
        self.clicked.connect(self._pick)

    def hex_color(self) -> str:
        return self._hex

    def set_hex_color(self, hex_color: str) -> None:
        self._hex = hex_color or ""
        self._refresh()

    def _refresh(self) -> None:
        bg = self._hex if self._hex else "transparent"
        self.setStyleSheet(
            f"background-color: {bg}; border: 1px solid #888;"
        )
        self.setText("" if self._hex else "…")

    def _pick(self) -> None:
        initial = QtGui.QColor(self._hex) if self._hex else QtGui.QColor("#888888")
        dlg = QtWidgets.QColorDialog(initial, self)
        dlg.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, False)
        if dlg.exec():
            chosen = dlg.selectedColor()
            if chosen.isValid():
                self.set_hex_color(chosen.name())
                self.color_changed.emit(self._hex)


# ───────────────────────────────────────────────────────────────────
#  ZonesEditor — two synced tables for one group
# ───────────────────────────────────────────────────────────────────


class ZonesEditor(QtWidgets.QWidget):
    """Edit a group's ``thresholds`` (N) + ``zones`` (N+1) side by side.

    The UI shows Zones first (top to bottom = contaminated to clean on
    the λ axis, equivalently left to right on the f axis) and the
    Thresholds table beneath it; an "Add zone" / "Remove last zone"
    row keeps the two tables in lock-step.
    """

    spec_changed = QtCore.Signal()

    # zone columns
    Z_COL_LABEL = 0
    Z_COL_BAND = 1
    Z_COL_ALPHA = 2
    Z_COL_POINT = 3
    # threshold columns
    T_COL_NACD = 0
    T_COL_LINE = 1
    T_COL_LABEL = 2

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._emit_block = 0

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ── Zones table (fill, alpha, point color, label) ──────────
        root.addWidget(self._section_label("Zones (left → right on f axis)"))
        self.zones_table = QtWidgets.QTableWidget(0, 4, self)
        self.zones_table.setHorizontalHeaderLabels(
            ["Zone label", "Band color", "Alpha", "Point color"]
        )
        self.zones_table.verticalHeader().setVisible(True)
        self.zones_table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.SelectedClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.zones_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.zones_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        try:
            self.zones_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeToContents
            )
        except Exception:
            pass
        self.zones_table.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.zones_table)

        # ── Thresholds table (NACD, line color, custom label) ──────
        root.addWidget(self._section_label(
            "Thresholds  ·  vertical NACD = x lines"
        ))
        self.thresholds_table = QtWidgets.QTableWidget(0, 3, self)
        self.thresholds_table.setHorizontalHeaderLabels(
            ["NACD", "Line color", "Line label"]
        )
        self.thresholds_table.verticalHeader().setVisible(False)
        self.thresholds_table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.SelectedClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
        )
        self.thresholds_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.thresholds_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        try:
            self.thresholds_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeToContents
            )
        except Exception:
            pass
        self.thresholds_table.itemChanged.connect(self._on_item_changed)
        root.addWidget(self.thresholds_table)

        # ── Buttons ───────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("+ Add zone")
        self.btn_add.setToolTip(
            "Append one zone and one NACD threshold to the end (clean side)."
        )
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove = QtWidgets.QPushButton("− Remove last zone")
        self.btn_remove.setToolTip(
            "Drop the last zone and its threshold (cannot go below one zone)."
        )
        self.btn_remove.clicked.connect(self._on_remove)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        btn_row.addStretch()
        root.addLayout(btn_row)

    # ── public api ─────────────────────────────────────────────────
    def set_data(
        self,
        thresholds: List[ZoneThreshold],
        zones: List[ZoneFill],
    ) -> None:
        # Enforce the invariant: N+1 zones for N thresholds.
        zones = list(zones)
        target = len(thresholds) + 1
        if len(zones) > target:
            zones = zones[:target]
        while len(zones) < target:
            zones.append(ZoneFill())

        self._emit_block += 1
        try:
            self.zones_table.setRowCount(0)
            for zi, z in enumerate(zones):
                self._append_zone_row(zi, z)
            self.thresholds_table.setRowCount(0)
            for ti, t in enumerate(thresholds):
                self._append_threshold_row(ti, t)
        finally:
            self._emit_block -= 1

    def get_thresholds(self) -> List[ZoneThreshold]:
        out: List[ZoneThreshold] = []
        for r in range(self.thresholds_table.rowCount()):
            try:
                nacd = float(
                    self.thresholds_table.item(r, self.T_COL_NACD).text()
                )
            except (TypeError, ValueError, AttributeError):
                continue
            btn = self.thresholds_table.cellWidget(r, self.T_COL_LINE)
            label_item = self.thresholds_table.item(r, self.T_COL_LABEL)
            out.append(ZoneThreshold(
                nacd=nacd,
                line_color=btn.hex_color() if isinstance(btn, _ColorButton) else "",
                line_label=label_item.text() if label_item else "",
            ))
        return out

    def get_zones(self) -> List[ZoneFill]:
        out: List[ZoneFill] = []
        for r in range(self.zones_table.rowCount()):
            label_item = self.zones_table.item(r, self.Z_COL_LABEL)
            band_btn = self.zones_table.cellWidget(r, self.Z_COL_BAND)
            point_btn = self.zones_table.cellWidget(r, self.Z_COL_POINT)
            try:
                alpha = float(
                    self.zones_table.item(r, self.Z_COL_ALPHA).text()
                )
            except (TypeError, ValueError, AttributeError):
                alpha = 0.15
            out.append(ZoneFill(
                band_color=band_btn.hex_color()
                if isinstance(band_btn, _ColorButton) else "",
                band_alpha=max(0.0, min(1.0, alpha)),
                point_color=point_btn.hex_color()
                if isinstance(point_btn, _ColorButton) else "",
                zone_label=label_item.text() if label_item else "",
            ))
        return out

    # ── internal helpers ──────────────────────────────────────────
    @staticmethod
    def _section_label(text: str) -> QtWidgets.QLabel:
        lbl = QtWidgets.QLabel(text)
        font = lbl.font()
        font.setBold(True)
        lbl.setFont(font)
        return lbl

    def _append_zone_row(self, idx: int, z: ZoneFill) -> None:
        r = self.zones_table.rowCount()
        self.zones_table.insertRow(r)

        label_item = QtWidgets.QTableWidgetItem(
            z.zone_label or f"Zone {idx + 1}"
        )
        label_item.setFlags(label_item.flags() | _ItemIsEditable)
        self.zones_table.setItem(r, self.Z_COL_LABEL, label_item)

        band_col = z.band_color or _palette_color(idx, _DEFAULT_BAND_PALETTE)
        band_btn = _ColorButton(band_col)
        band_btn.color_changed.connect(self._emit_changed)
        self.zones_table.setCellWidget(r, self.Z_COL_BAND, band_btn)

        alpha_item = QtWidgets.QTableWidgetItem(f"{z.band_alpha:.2f}")
        alpha_item.setFlags(alpha_item.flags() | _ItemIsEditable)
        self.zones_table.setItem(r, self.Z_COL_ALPHA, alpha_item)

        pt_col = z.point_color or _palette_color(idx, _DEFAULT_POINT_PALETTE)
        pt_btn = _ColorButton(pt_col)
        pt_btn.color_changed.connect(self._emit_changed)
        self.zones_table.setCellWidget(r, self.Z_COL_POINT, pt_btn)

    def _append_threshold_row(self, idx: int, t: ZoneThreshold) -> None:
        r = self.thresholds_table.rowCount()
        self.thresholds_table.insertRow(r)

        nacd_item = QtWidgets.QTableWidgetItem(f"{t.nacd:g}")
        nacd_item.setFlags(nacd_item.flags() | _ItemIsEditable)
        self.thresholds_table.setItem(r, self.T_COL_NACD, nacd_item)

        line_col = t.line_color or _palette_color(idx, _DEFAULT_LINE_PALETTE)
        btn = _ColorButton(line_col)
        btn.color_changed.connect(self._emit_changed)
        self.thresholds_table.setCellWidget(r, self.T_COL_LINE, btn)

        label_item = QtWidgets.QTableWidgetItem(t.line_label or "")
        label_item.setFlags(label_item.flags() | _ItemIsEditable)
        # Keep the placeholder in a tooltip so it is obvious what the
        # automatic label will look like when left blank.
        label_item.setToolTip(f'default: "NACD = {t.nacd:g}"')
        self.thresholds_table.setItem(r, self.T_COL_LABEL, label_item)

    # ── buttons ───────────────────────────────────────────────────
    def _on_add(self) -> None:
        """Add one zone + one threshold, keeping the invariant."""
        thresholds = self.get_thresholds()
        zones = self.get_zones()
        # Suggest a new NACD one step above the current max; default to
        # 1.0 when no thresholds exist yet.
        if thresholds:
            next_nacd = max(t.nacd for t in thresholds) + 0.5
        else:
            next_nacd = 1.0
        thresholds.append(ZoneThreshold(nacd=next_nacd))
        zones.append(ZoneFill())
        self.set_data(thresholds, zones)
        self._emit_changed()

    def _on_remove(self) -> None:
        """Drop the last zone and its threshold; floor at one zone."""
        thresholds = self.get_thresholds()
        zones = self.get_zones()
        if not thresholds:
            return  # one zone is the minimum
        thresholds.pop()
        if len(zones) > 1:
            zones.pop()
        self.set_data(thresholds, zones)
        self._emit_changed()

    # ── signal plumbing ───────────────────────────────────────────
    def _on_item_changed(self, _item) -> None:
        self._emit_changed()

    def _emit_changed(self, *_args) -> None:
        if self._emit_block:
            return
        self.spec_changed.emit()


# ───────────────────────────────────────────────────────────────────
#  SingleGroupEditor — one ZoneGroup
# ───────────────────────────────────────────────────────────────────


class SingleGroupEditor(QtWidgets.QWidget):
    """Editor for a single :class:`ZoneGroup`.

    ``show_position=True`` surfaces the "Label position" combobox (used
    by the multi_group editor to pick top/bottom/left/right for each
    overlaid group). ``show_lambda_toggle=False`` hides the "Draw λ
    lines" option entirely; that matches the primary multi_zone UX
    where we only want vertical ``NACD = x`` markers.
    """

    group_changed = QtCore.Signal()

    def __init__(
        self,
        show_position: bool = True,
        show_lambda_toggle: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._emit_block = 0

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Group name")
        self.name_edit.textEdited.connect(self._emit_changed)
        form.addRow("Name:", self.name_edit)

        if show_position:
            self.pos_combo = QtWidgets.QComboBox()
            for code, label in (
                ("top", "Top"),
                ("bottom", "Bottom"),
                ("left", "Left"),
                ("right", "Right"),
            ):
                self.pos_combo.addItem(label, code)
            self.pos_combo.currentIndexChanged.connect(self._emit_changed)
            form.addRow("Label position:", self.pos_combo)
        else:
            self.pos_combo = None

        # Draw toggles — both axes default on so new groups draw the
        # f vertical marker AND the λ hyperbola / λ-axis line. The λ
        # toggle is shown by default; callers can hide it per-editor
        # via show_lambda_toggle=False but the underlying spec still
        # keeps draw_lambda=True.
        self.chk_lambda = QtWidgets.QCheckBox("Draw λ lines")
        self.chk_lambda.setChecked(True)
        self.chk_lambda.toggled.connect(self._emit_changed)
        self.chk_freq = QtWidgets.QCheckBox("Draw f lines")
        self.chk_freq.setChecked(True)
        self.chk_freq.toggled.connect(self._emit_changed)

        toggles = QtWidgets.QHBoxLayout()
        if show_lambda_toggle:
            toggles.addWidget(self.chk_lambda)
        else:
            self.chk_lambda.setVisible(False)
        toggles.addWidget(self.chk_freq)
        toggles.addStretch()
        form.addRow("", self._wrap(toggles))
        root.addLayout(form)

        self.zones_editor = ZonesEditor(self)
        self.zones_editor.spec_changed.connect(self._emit_changed)
        root.addWidget(self.zones_editor)

    # ── public api ────────────────────────────────────────────────
    def set_group(self, group: ZoneGroup) -> None:
        g = group.normalised()
        self._emit_block += 1
        try:
            self.name_edit.setText(g.name)
            if self.pos_combo is not None:
                idx = max(0, self.pos_combo.findData(g.label_position))
                self.pos_combo.setCurrentIndex(idx)
            self.chk_lambda.setChecked(bool(g.draw_lambda))
            self.chk_freq.setChecked(bool(g.draw_freq))
            self.zones_editor.set_data(list(g.thresholds), list(g.zones))
        finally:
            self._emit_block -= 1

    def get_group(self) -> ZoneGroup:
        pos = (
            self.pos_combo.currentData()
            if self.pos_combo is not None else "top"
        )
        g = ZoneGroup(
            name=self.name_edit.text() or "Group",
            thresholds=self.zones_editor.get_thresholds(),
            zones=self.zones_editor.get_zones(),
            draw_lambda=bool(self.chk_lambda.isChecked()),
            draw_freq=bool(self.chk_freq.isChecked()),
            label_position=pos or "top",
        )
        return g.normalised()

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _wrap(layout) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return w

    def _emit_changed(self, *_args) -> None:
        if self._emit_block:
            return
        self.group_changed.emit()


# ───────────────────────────────────────────────────────────────────
#  MultiGroupEditor — N independent groups
# ───────────────────────────────────────────────────────────────────


class MultiGroupEditor(QtWidgets.QWidget):
    """Two-level editor: outer list of groups + inner group editor.

    Uses :class:`SingleGroupEditor` with ``show_lambda_toggle=True`` —
    the multi_group view is the advanced surface so both λ and f
    toggles are exposed here.
    """

    groups_changed = QtCore.Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._emit_block = 0
        self._groups: List[ZoneGroup] = []

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ── left column: group list + add / remove ────────────────
        left = QtWidgets.QVBoxLayout()
        self.group_list = QtWidgets.QListWidget()
        self.group_list.currentRowChanged.connect(self._on_group_selected)
        left.addWidget(self.group_list, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Add group")
        self.btn_add.clicked.connect(self._on_add_group)
        self.btn_remove = QtWidgets.QPushButton("Remove")
        self.btn_remove.clicked.connect(self._on_remove_group)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_remove)
        left.addLayout(btn_row)

        root.addLayout(left, 1)

        # ── right column: group editor ────────────────────────────
        self.group_editor = SingleGroupEditor(
            show_position=True,
            show_lambda_toggle=True,
            parent=self,
        )
        self.group_editor.group_changed.connect(self._on_current_group_edited)
        root.addWidget(self.group_editor, 2)

    # ── public api ────────────────────────────────────────────────
    def set_groups(self, groups: List[ZoneGroup]) -> None:
        self._emit_block += 1
        try:
            self._groups = [self._clone_group(g) for g in groups]
            self._rebuild_list()
            if self._groups:
                self.group_list.setCurrentRow(0)
                self.group_editor.set_group(self._groups[0])
            else:
                self.group_editor.set_group(ZoneGroup(name=""))
        finally:
            self._emit_block -= 1

    def get_groups(self) -> List[ZoneGroup]:
        return [self._clone_group(g) for g in self._groups]

    # ── helpers ───────────────────────────────────────────────────
    @staticmethod
    def _clone_group(g: ZoneGroup) -> ZoneGroup:
        g = g.normalised()
        return ZoneGroup(
            name=g.name,
            thresholds=[
                ZoneThreshold(
                    nacd=t.nacd,
                    line_color=t.line_color,
                    line_label=t.line_label,
                )
                for t in g.thresholds
            ],
            zones=[
                ZoneFill(
                    band_color=z.band_color,
                    band_alpha=z.band_alpha,
                    point_color=z.point_color,
                    zone_label=z.zone_label,
                )
                for z in g.zones
            ],
            draw_lambda=g.draw_lambda,
            draw_freq=g.draw_freq,
            label_position=g.label_position,
            palette_hint=g.palette_hint,
        )

    def _rebuild_list(self) -> None:
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in self._groups:
            self.group_list.addItem(self._group_list_label(g))
        self.group_list.blockSignals(False)

    @staticmethod
    def _group_list_label(g: ZoneGroup) -> str:
        return f"{g.name}  [{g.label_position}]  ({len(g.thresholds)})"

    def _on_group_selected(self, row: int) -> None:
        if not (0 <= row < len(self._groups)):
            return
        self._emit_block += 1
        try:
            self.group_editor.set_group(self._groups[row])
        finally:
            self._emit_block -= 1

    def _on_add_group(self) -> None:
        positions = ["top", "bottom", "left", "right"]
        pos = positions[len(self._groups) % 4]
        # Start with a single-threshold group (= two zones) so the new
        # group immediately shows red / blue out of the box.
        new_group = ZoneGroup(
            name=f"Group {len(self._groups) + 1}",
            thresholds=[ZoneThreshold(nacd=1.0)],
            zones=[ZoneFill(), ZoneFill()],
            label_position=pos,
            draw_lambda=True,
            draw_freq=True,
        )
        new_group = new_group.normalised()
        self._groups.append(new_group)
        self._rebuild_list()
        self.group_list.setCurrentRow(len(self._groups) - 1)
        self._emit_changed()

    def _on_remove_group(self) -> None:
        row = self.group_list.currentRow()
        if not (0 <= row < len(self._groups)):
            return
        del self._groups[row]
        self._rebuild_list()
        if self._groups:
            new_row = min(row, len(self._groups) - 1)
            self.group_list.setCurrentRow(new_row)
        else:
            self.group_editor.set_group(ZoneGroup(name=""))
        self._emit_changed()

    def _on_current_group_edited(self) -> None:
        if self._emit_block:
            return
        row = self.group_list.currentRow()
        if not (0 <= row < len(self._groups)):
            return
        self._groups[row] = self.group_editor.get_group()
        item = self.group_list.item(row)
        if item is not None:
            item.setText(self._group_list_label(self._groups[row]))
        self._emit_changed()

    def _emit_changed(self, *_args) -> None:
        if self._emit_block:
            return
        self.groups_changed.emit()


__all__ = [
    "ZonesEditor",
    "SingleGroupEditor",
    "MultiGroupEditor",
]
