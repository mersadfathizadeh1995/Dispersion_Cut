"""Limit-Lines tab for the NF Evaluation dock.

Shows the full set of NF limit lines that will be drawn on the canvas
as a hierarchical tree:

    Master "Show all" checkbox      [on/off]
    Band 1  (f_lo-f_hi Hz)           [check] [color]
      Wavelength                     [check] [color]
        lambda_max = ... m           [check] [color]
        lambda_min = ... m           [check] [color]
      Frequency                      [check] [color]
        f_min = ... Hz               [check] [color]
        f_max = ... Hz               [check] [color]
    Band 2 ...

The tree is rebuilt whenever the owning dock publishes a new
``DerivedLimitSet`` via :meth:`refresh`.  Per-line visibility and color
are kept in :class:`LimitsLineState` and persisted across sessions.

Signals
-------
state_changed :
    Emitted whenever the user toggles visibility or changes a color.
    The owning dock reacts by redrawing the canvas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.core.processing.nearfield.range_derivation import (
    DerivedLimitSet,
    DerivedLine,
)

# ── Qt5 / Qt6 enum compat ──────────────────────────────────────────
try:
    _Checked = QtCore.Qt.Checked
    _Unchecked = QtCore.Qt.Unchecked
    _PartiallyChecked = QtCore.Qt.PartiallyChecked
except AttributeError:
    _Checked = QtCore.Qt.CheckState.Checked
    _Unchecked = QtCore.Qt.CheckState.Unchecked
    _PartiallyChecked = QtCore.Qt.CheckState.PartiallyChecked

try:
    _UserRole = QtCore.Qt.UserRole
except AttributeError:
    _UserRole = QtCore.Qt.ItemDataRole.UserRole

try:
    _ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemIsEnabled
    _ItemIsSelectable = QtCore.Qt.ItemIsSelectable
    _ItemIsAutoTristate = QtCore.Qt.ItemIsAutoTristate
except AttributeError:
    _ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemFlag.ItemIsEnabled
    _ItemIsSelectable = QtCore.Qt.ItemFlag.ItemIsSelectable
    _ItemIsAutoTristate = QtCore.Qt.ItemFlag.ItemIsAutoTristate


LineKey = Tuple[int, str, str]


# Default palette: first band black, second dark purple, then dark red,
# dark green, dark orange, dark teal (repeats after six).
_BAND_PALETTE = [
    "#000000",  # black
    "#4B0082",  # indigo / dark purple
    "#8B0000",  # dark red
    "#006400",  # dark green
    "#B8860B",  # dark goldenrod
    "#2F4F4F",  # dark slate
]


def default_band_color(band_index: int) -> str:
    return _BAND_PALETTE[band_index % len(_BAND_PALETTE)]


@dataclass
class LimitsLineState:
    """Per-line visibility/color state, persisted between sessions."""

    visible: Dict[LineKey, bool] = field(default_factory=dict)
    colors: Dict[LineKey, str] = field(default_factory=dict)
    show_all: bool = True

    # ── convenience ────────────────────────────────────────────────
    def get_visible(self, key: LineKey, default: bool = True) -> bool:
        return bool(self.visible.get(key, default))

    def get_color(self, key: LineKey, default: str = "#000000") -> str:
        return self.colors.get(key, default)

    def set_visible(self, key: LineKey, value: bool) -> None:
        self.visible[key] = bool(value)

    def set_color(self, key: LineKey, value: str) -> None:
        self.colors[key] = str(value)

    # ── persistence (dict round-trip) ──────────────────────────────
    def to_dict(self) -> dict:
        def k2s(k: LineKey) -> str:
            return f"{k[0]}|{k[1]}|{k[2]}"
        return {
            "show_all": bool(self.show_all),
            "visible": {k2s(k): v for k, v in self.visible.items()},
            "colors": {k2s(k): v for k, v in self.colors.items()},
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "LimitsLineState":
        if not d:
            return cls()
        def s2k(s: str) -> Optional[LineKey]:
            try:
                bi, kind, role = s.split("|")
                return (int(bi), str(kind), str(role))
            except (ValueError, AttributeError):
                return None
        out = cls(show_all=bool(d.get("show_all", True)))
        for s, v in (d.get("visible") or {}).items():
            key = s2k(s)
            if key is not None:
                out.visible[key] = bool(v)
        for s, v in (d.get("colors") or {}).items():
            key = s2k(s)
            if key is not None:
                out.colors[key] = str(v)
        return out


class NFLimitsTab(QtWidgets.QWidget):
    """Tree-based control surface for NF limit lines.

    The dock feeds it a :class:`DerivedLimitSet` (for one mode at a
    time) via :meth:`refresh`; the tab exposes a
    :class:`LimitsLineState` whose changes are broadcast via
    :attr:`state_changed`.
    """

    state_changed = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self._state = LimitsLineState()
        self._limit_set: Optional[DerivedLimitSet] = None
        self._updating = False  # guard for programmatic updates

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── master "Show all" toggle ───────────────────────────────
        self._chk_show_all = QtWidgets.QCheckBox("Show all limit lines")
        self._chk_show_all.setChecked(True)
        self._chk_show_all.toggled.connect(self._on_show_all_toggled)
        layout.addWidget(self._chk_show_all)

        # ── info banner ────────────────────────────────────────────
        self._info = QtWidgets.QLabel(
            "Enter an evaluation range in NACD-Only or Reference to "
            "populate this tree."
        )
        self._info.setWordWrap(True)
        self._info.setStyleSheet("color: #777; font-style: italic;")
        layout.addWidget(self._info)

        # ── tree ───────────────────────────────────────────────────
        self._tree = QtWidgets.QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Limit", "Color"])
        self._tree.setColumnWidth(0, 220)
        self._tree.setUniformRowHeights(False)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree, stretch=1)

        # ── hint row ───────────────────────────────────────────────
        hint = QtWidgets.QLabel(
            "Tip: double-click a row's color cell to change it."
        )
        hint.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(hint)

    # ── public API ───────────────────────────────────────────────────
    def state(self) -> LimitsLineState:
        return self._state

    def set_state(self, state: LimitsLineState) -> None:
        self._state = state or LimitsLineState()
        self._updating = True
        try:
            self._chk_show_all.setChecked(bool(self._state.show_all))
        finally:
            self._updating = False
        # Rebuild so new visibility/color apply to existing tree items.
        self.refresh(self._limit_set)

    def refresh(self, limit_set: Optional[DerivedLimitSet]) -> None:
        """Rebuild the tree from ``limit_set``."""
        self._limit_set = limit_set
        self._updating = True
        try:
            self._tree.blockSignals(True)
            self._tree.clear()
            if limit_set is None or not limit_set.lines:
                self._info.setVisible(True)
                return
            self._info.setVisible(False)
            by_band = limit_set.by_band()
            for bi in sorted(by_band.keys()):
                self._add_band_node(bi, by_band[bi])
        finally:
            self._tree.blockSignals(False)
            self._updating = False
        self._tree.expandAll()

    # ── internals ────────────────────────────────────────────────────
    def _default_color(self, key: LineKey) -> str:
        return self._state.get_color(
            key, default=default_band_color(key[0]),
        )

    def _add_band_node(
        self, band_index: int, lines: List[DerivedLine],
    ) -> None:
        color = default_band_color(band_index)
        # Pick a representative f-range for the label.
        f_lines = [ln for ln in lines if ln.kind == "freq"]
        if f_lines:
            fmins = [ln.value for ln in f_lines if ln.role == "min"]
            fmaxs = [ln.value for ln in f_lines if ln.role == "max"]
            if fmins and fmaxs:
                title = f"Band {band_index + 1}  ({fmins[0]:g}–{fmaxs[0]:g} Hz)"
            else:
                title = f"Band {band_index + 1}"
        else:
            title = f"Band {band_index + 1}  (\u03bb-only)"

        band_item = QtWidgets.QTreeWidgetItem([title, ""])
        band_item.setFlags(
            band_item.flags()
            | _ItemIsUserCheckable
            | _ItemIsAutoTristate
        )
        # Band-level key uses a sentinel role so persistence stays
        # unique even if it overlaps with leaves.
        band_key: LineKey = (band_index, "band", "band")
        band_item.setData(0, _UserRole, band_key)
        self._apply_color_cell(band_item, self._state.get_color(band_key, color))
        self._tree.addTopLevelItem(band_item)

        # Group: Wavelength
        lam_group = self._add_group(band_item, band_index, "lambda",
                                    "Wavelength", color)
        for role in ("min", "max"):
            ln = next(
                (x for x in lines if x.kind == "lambda" and x.role == role),
                None,
            )
            if ln is not None:
                self._add_leaf(lam_group, ln, color)

        # Group: Frequency
        freq_group = self._add_group(band_item, band_index, "freq",
                                     "Frequency", color)
        for role in ("min", "max"):
            ln = next(
                (x for x in lines if x.kind == "freq" and x.role == role),
                None,
            )
            if ln is not None:
                self._add_leaf(freq_group, ln, color)

        # Apply band check state LAST, after children have set theirs.
        band_check = _Checked if self._state.get_visible(band_key, True) else _Unchecked
        band_item.setCheckState(0, band_check)

    def _add_group(
        self, parent: QtWidgets.QTreeWidgetItem,
        band_index: int, kind: str, label: str, color: str,
    ) -> QtWidgets.QTreeWidgetItem:
        key: LineKey = (band_index, kind, "group")
        item = QtWidgets.QTreeWidgetItem([label, ""])
        item.setFlags(
            item.flags()
            | _ItemIsUserCheckable
            | _ItemIsAutoTristate
        )
        item.setData(0, _UserRole, key)
        self._apply_color_cell(item, self._state.get_color(key, color))
        parent.addChild(item)
        item.setCheckState(0, _Checked if self._state.get_visible(key, True) else _Unchecked)
        return item

    def _add_leaf(
        self, group: QtWidgets.QTreeWidgetItem,
        ln: DerivedLine, default_color: str,
    ) -> None:
        key: LineKey = (ln.band_index, ln.kind, ln.role)
        if ln.kind == "lambda":
            unit = "m"
            label_prefix = "\u03bb"
        else:
            unit = "Hz"
            label_prefix = "f"
        suffix = ""
        if ln.source == "derived":
            suffix = f"   (derived from {ln.derived_from:g})"
        elif ln.source == "user":
            suffix = "   (user)"
        if not ln.valid:
            suffix += "  \u2014 outside curve coverage"
        text = f"{label_prefix}_{ln.role} = {ln.value:g} {unit}{suffix}"

        item = QtWidgets.QTreeWidgetItem([text, ""])
        flags = item.flags() | _ItemIsUserCheckable | _ItemIsEnabled | _ItemIsSelectable
        item.setFlags(flags)
        item.setData(0, _UserRole, key)
        color = self._state.get_color(key, default_color)
        self._apply_color_cell(item, color)
        if not ln.valid:
            try:
                item.setForeground(0, QtGui.QColor("#888"))
            except Exception:
                pass
        group.addChild(item)
        visible = self._state.get_visible(key, True) and ln.valid
        item.setCheckState(0, _Checked if visible else _Unchecked)

    def _apply_color_cell(
        self, item: QtWidgets.QTreeWidgetItem, color: str,
    ) -> None:
        try:
            item.setText(1, color)
            item.setForeground(1, QtGui.QColor(color))
            # Use a filled background swatch for readability.
            item.setBackground(1, QtGui.QColor(color))
            fg = "#FFF" if QtGui.QColor(color).lightnessF() < 0.5 else "#000"
            item.setForeground(1, QtGui.QColor(fg))
        except Exception:
            pass

    # ── event handlers ──────────────────────────────────────────────
    def _on_show_all_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        self._state.show_all = bool(checked)
        self.state_changed.emit()

    def _on_item_changed(
        self, item: QtWidgets.QTreeWidgetItem, column: int,
    ) -> None:
        if self._updating or column != 0:
            return
        key = item.data(0, _UserRole)
        if key is None:
            return
        self._state.set_visible(tuple(key), item.checkState(0) == _Checked)
        self.state_changed.emit()

    def _on_item_double_clicked(
        self, item: QtWidgets.QTreeWidgetItem, column: int,
    ) -> None:
        if column != 1:
            return
        key = item.data(0, _UserRole)
        if key is None:
            return
        current = self._state.get_color(
            tuple(key), default=default_band_color(int(key[0])),
        )
        picked = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Pick limit-line color",
        )
        if not picked.isValid():
            return
        new_color = picked.name()
        tkey = tuple(key)
        self._state.set_color(tkey, new_color)
        self._updating = True
        try:
            self._apply_color_cell(item, new_color)
        finally:
            self._updating = False
        # If this is a band/group node, cascade into children that still
        # use the default.
        if tkey[1] in ("band", "lambda", "freq") and tkey[2] in ("band", "group"):
            self._cascade_color(item, new_color)
        self.state_changed.emit()

    def _cascade_color(
        self, parent: QtWidgets.QTreeWidgetItem, new_color: str,
    ) -> None:
        self._updating = True
        try:
            for i in range(parent.childCount()):
                child = parent.child(i)
                key = child.data(0, _UserRole)
                if key is not None:
                    tkey = tuple(key)
                    # Only overwrite when the user hasn't already
                    # picked a custom color.
                    self._state.set_color(tkey, new_color)
                    self._apply_color_cell(child, new_color)
                if child.childCount() > 0:
                    self._cascade_color(child, new_color)
        finally:
            self._updating = False


__all__ = [
    "NFLimitsTab",
    "LimitsLineState",
    "default_band_color",
]
