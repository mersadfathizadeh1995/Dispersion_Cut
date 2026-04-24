"""Settings panel for a single NFZoneBand / NFZoneArrow override.

Opened from the right panel when the user selects a zone item in the
data tree.  Emits one ``zone_changed`` signal per widget change so the
main window can mutate the matching dataclass by uid and re-render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...qt_compat import QtWidgets, QtGui, Signal

if TYPE_CHECKING:
    from ...core.models import NFAnalysis, NFZoneArrow, NFZoneBand


def _nacd_range_hint(zone_spec, gi: int, zi: int) -> str:
    """Format the NACD range this zone occupies as ``"NACD 1.0 \u2013 1.5"``.

    Used to label the zone panel title so the user knows which NACD
    bin their edits apply to.  Returns an empty string when the spec
    is missing or doesn't define thresholds for the given group.
    Accepts either the NACDZoneSpec dataclass or its serialised dict
    form (whichever the sheet happens to carry).
    """
    try:
        if zone_spec is None:
            return ""
        # Normalise to a list of threshold NACD floats for this group.
        thresholds: list = []
        if isinstance(zone_spec, dict):
            groups = zone_spec.get("groups") or []
            if gi < 0 or gi >= len(groups):
                return ""
            g = groups[gi] or {}
            for t in (g.get("thresholds") or []):
                try:
                    thresholds.append(float(t.get("nacd", 0.0)))
                except (TypeError, ValueError, AttributeError):
                    continue
        else:
            groups = getattr(zone_spec, "groups", None) or []
            if gi < 0 or gi >= len(groups):
                return ""
            g = groups[gi]
            for t in getattr(g, "thresholds", None) or []:
                try:
                    thresholds.append(float(getattr(t, "nacd", 0.0)))
                except (TypeError, ValueError):
                    continue
        thresholds = sorted(thresholds)
        n = len(thresholds)
        if n == 0:
            return ""
        # Zone 0 ..< thresholds[0]; zone N ≥ thresholds[-1];
        # zone k spans [thresholds[k-1], thresholds[k]).
        if zi < 0 or zi > n:
            return ""
        if zi == 0:
            return f"NACD < {thresholds[0]:g}"
        if zi == n:
            return f"NACD \u2265 {thresholds[-1]:g}"
        lo, hi = thresholds[zi - 1], thresholds[zi]
        return f"NACD {lo:g} \u2013 {hi:g}"
    except Exception:
        return ""


class NFZoneSettingsPanel(QtWidgets.QWidget):
    """One panel, two "kinds" (band / arrow)."""

    #   nf_uid, kind ("band"|"arrow"), zone_uid, attr, value
    zone_changed = Signal(str, str, str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nf_uid: str = ""
        self._zone_uid: str = ""
        self._kind: str = "band"
        self._obj = None  # NFZoneBand or NFZoneArrow

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        self._title = QtWidgets.QLabel("")
        self._title.setStyleSheet("font-weight: bold; padding: 4px 2px;")
        outer.addWidget(self._title)

        # ── Band group ─────────────────────────────────────────────
        self._band_box = QtWidgets.QGroupBox("Band")
        bf = QtWidgets.QFormLayout(self._band_box)
        bf.setSpacing(4)

        self._band_color = QtWidgets.QPushButton()
        self._band_color.clicked.connect(
            lambda: self._pick_color("band_color", self._band_color))
        bf.addRow("Band color:", self._band_color)

        self._band_alpha = QtWidgets.QDoubleSpinBox()
        self._band_alpha.setRange(0.0, 1.0)
        self._band_alpha.setSingleStep(0.05)
        self._band_alpha.setDecimals(2)
        self._band_alpha.valueChanged.connect(
            lambda v: self._emit("band_alpha", float(v)))
        bf.addRow("Band alpha:", self._band_alpha)

        self._point_color = QtWidgets.QPushButton()
        self._point_color.clicked.connect(
            lambda: self._pick_color("point_color", self._point_color))
        bf.addRow("Point color:", self._point_color)

        outer.addWidget(self._band_box)

        # ── Label group ───────────────────────────────────────────
        self._label_box = QtWidgets.QGroupBox("Label")
        lf = QtWidgets.QFormLayout(self._label_box)
        lf.setSpacing(4)

        self._label_visible = QtWidgets.QCheckBox("Show label")
        self._label_visible.toggled.connect(
            lambda v: self._emit("label_visible", bool(v)))
        lf.addRow(self._label_visible)

        self._label_text = QtWidgets.QLineEdit()
        self._label_text.setPlaceholderText("Zone I")
        self._label_text.editingFinished.connect(
            lambda: self._emit("label", self._label_text.text()))
        lf.addRow("Text:", self._label_text)

        self._label_fs = QtWidgets.QSpinBox()
        self._label_fs.setRange(4, 32)
        self._label_fs.valueChanged.connect(
            lambda v: self._emit("label_fontsize", int(v)))
        lf.addRow("Font size:", self._label_fs)

        self._label_pos = QtWidgets.QComboBox()
        for p in ("top", "bottom", "left", "right"):
            self._label_pos.addItem(p, p)
        self._label_pos.currentIndexChanged.connect(
            lambda _i: self._emit("label_position",
                                   self._label_pos.currentData()))
        lf.addRow("Position:", self._label_pos)

        self._label_ha = QtWidgets.QComboBox()
        for a in ("left", "center", "right"):
            self._label_ha.addItem(a, a)
        self._label_ha.currentIndexChanged.connect(
            lambda _i: self._emit("label_ha",
                                   self._label_ha.currentData()))
        lf.addRow("H-align:", self._label_ha)

        self._row_off = QtWidgets.QDoubleSpinBox()
        self._row_off.setRange(-0.5, 0.5)
        self._row_off.setSingleStep(0.01)
        self._row_off.setDecimals(3)
        self._row_off.valueChanged.connect(
            lambda v: self._emit("label_row_offset", float(v)))
        lf.addRow("Row offset:", self._row_off)

        self._label_color = QtWidgets.QPushButton()
        self._label_color.clicked.connect(
            lambda: self._pick_color("label_color", self._label_color))
        lf.addRow("Label color:", self._label_color)

        outer.addWidget(self._label_box)

        # ── Arrow-below-label group (request 1) ───────────────────
        self._abl_box = QtWidgets.QGroupBox("Arrow below label")
        af = QtWidgets.QFormLayout(self._abl_box)
        af.setSpacing(4)

        self._abl_on = QtWidgets.QCheckBox(
            "Draw <-> arrow beneath the zone label")
        self._abl_on.toggled.connect(
            lambda v: self._emit("arrow_below_label", bool(v)))
        af.addRow(self._abl_on)

        self._abl_gap = QtWidgets.QDoubleSpinBox()
        self._abl_gap.setRange(0.0, 0.3)
        self._abl_gap.setSingleStep(0.01)
        self._abl_gap.setDecimals(3)
        self._abl_gap.valueChanged.connect(
            lambda v: self._emit("arrow_below_gap", float(v)))
        af.addRow("Gap:", self._abl_gap)

        self._abl_lw = QtWidgets.QDoubleSpinBox()
        self._abl_lw.setRange(0.2, 6.0)
        self._abl_lw.setSingleStep(0.1)
        self._abl_lw.valueChanged.connect(
            lambda v: self._emit("arrow_below_linewidth", float(v)))
        af.addRow("Line width:", self._abl_lw)

        self._abl_color = QtWidgets.QPushButton()
        self._abl_color.clicked.connect(
            lambda: self._pick_color("arrow_below_color", self._abl_color))
        af.addRow("Color:", self._abl_color)

        outer.addWidget(self._abl_box)

        # ── Arrow group (NFZoneArrow / vertical boundary) ─────────
        self._arrow_box = QtWidgets.QGroupBox("Vertical boundary arrow")
        vf = QtWidgets.QFormLayout(self._arrow_box)
        vf.setSpacing(4)

        self._arr_enabled = QtWidgets.QCheckBox("Enabled")
        self._arr_enabled.toggled.connect(
            lambda v: self._emit("enabled", bool(v)))
        vf.addRow(self._arr_enabled)

        self._arr_color = QtWidgets.QPushButton()
        self._arr_color.clicked.connect(
            lambda: self._pick_color("color", self._arr_color))
        vf.addRow("Color:", self._arr_color)

        self._arr_lw = QtWidgets.QDoubleSpinBox()
        self._arr_lw.setRange(0.2, 6.0)
        self._arr_lw.setSingleStep(0.1)
        self._arr_lw.valueChanged.connect(
            lambda v: self._emit("linewidth", float(v)))
        vf.addRow("Line width:", self._arr_lw)

        self._arr_y = QtWidgets.QDoubleSpinBox()
        self._arr_y.setRange(0.0, 1.0)
        self._arr_y.setSingleStep(0.05)
        self._arr_y.setDecimals(2)
        self._arr_y.valueChanged.connect(
            lambda v: self._emit("y_frac", float(v)))
        vf.addRow("Y position:", self._arr_y)

        self._arr_text = QtWidgets.QLineEdit()
        self._arr_text.editingFinished.connect(
            lambda: self._emit("text", self._arr_text.text()))
        vf.addRow("Text:", self._arr_text)

        self._arr_text_fs = QtWidgets.QSpinBox()
        self._arr_text_fs.setRange(4, 32)
        self._arr_text_fs.valueChanged.connect(
            lambda v: self._emit("text_fontsize", int(v)))
        vf.addRow("Text font size:", self._arr_text_fs)

        self._arr_text_dy = QtWidgets.QDoubleSpinBox()
        self._arr_text_dy.setRange(-0.5, 0.5)
        self._arr_text_dy.setSingleStep(0.01)
        self._arr_text_dy.setDecimals(3)
        self._arr_text_dy.valueChanged.connect(
            lambda v: self._emit("text_y_offset", float(v)))
        vf.addRow("Text Y offset:", self._arr_text_dy)

        outer.addWidget(self._arrow_box)

        outer.addStretch(1)

    # ── Public API ───────────────────────────────────────────────
    def show_zone(
        self,
        nf: "NFAnalysis",
        kind: str,
        zone_uid: str,
        *,
        zone_spec=None,
    ) -> None:
        """Populate the panel for the selected zone band or arrow.

        ``zone_spec`` is the sheet-level NACDZoneSpec dict (if any).
        When supplied, the panel title is augmented with the zone's
        NACD range (e.g. ``"NACD 1.0 – 1.5"``) so the user can see
        which NACD bin their edits apply to.
        """
        kind = "arrow" if kind == "arrow" else "band"
        self._kind = kind
        self._nf_uid = nf.uid
        self._zone_uid = zone_uid
        obj = None
        if kind == "band":
            for zb in getattr(nf, "zone_bands", None) or []:
                if zb.uid == zone_uid:
                    obj = zb
                    break
        else:
            for za in getattr(nf, "zone_arrows", None) or []:
                if za.uid == zone_uid:
                    obj = za
                    break
        self._obj = obj
        if obj is None:
            self._title.setText("(zone not found)")
            self._band_box.setVisible(False)
            self._label_box.setVisible(False)
            self._abl_box.setVisible(False)
            self._arrow_box.setVisible(False)
            return

        # Toggle group visibility by kind.
        is_band = (kind == "band")
        self._band_box.setVisible(is_band)
        self._label_box.setVisible(is_band)
        self._abl_box.setVisible(is_band)
        self._arrow_box.setVisible(not is_band)
        axis = str(getattr(obj, "axis", ""))
        gi = int(getattr(obj, "group_index", 0))
        zi = int(getattr(obj, "zone_index", 0))
        label_txt = str(getattr(obj, "label", "") or f"Zone {zi + 1}") \
            if is_band else f"Zone {zi + 1} arrow"
        nacd_hint = _nacd_range_hint(zone_spec, gi, zi)
        hint_suffix = f"  \u2022  {nacd_hint}" if nacd_hint else ""
        self._title.setText(
            f"{label_txt} \u2014 group {gi + 1}, {axis} axis{hint_suffix}"
        )

        if is_band:
            self._populate_band(obj)
        else:
            self._populate_arrow(obj)

    # ── population helpers ───────────────────────────────────────
    def _populate_band(self, b) -> None:
        widgets = [
            self._band_alpha, self._label_visible, self._label_text,
            self._label_fs, self._label_pos, self._label_ha,
            self._row_off, self._abl_on, self._abl_gap, self._abl_lw,
        ]
        for w in widgets:
            w.blockSignals(True)
        self._band_color.setStyleSheet(
            f"background-color: {b.band_color or '#cccccc'}; min-height: 22px;"
        )
        self._band_alpha.setValue(float(getattr(b, "band_alpha", 0.15)))
        self._point_color.setStyleSheet(
            f"background-color: {b.point_color or '#cccccc'}; min-height: 22px;"
        )
        self._label_visible.setChecked(bool(getattr(b, "label_visible", True)))
        self._label_text.setText(str(getattr(b, "label", "") or ""))
        try:
            fs = int(getattr(b, "label_fontsize", 9) or 9)
        except (TypeError, ValueError):
            fs = 9
        self._label_fs.setValue(max(4, fs))
        pos = str(getattr(b, "label_position", "top") or "top")
        idx = self._label_pos.findData(pos)
        self._label_pos.setCurrentIndex(max(0, idx))
        ha = str(getattr(b, "label_ha", "center") or "center")
        idx2 = self._label_ha.findData(ha)
        self._label_ha.setCurrentIndex(max(0, idx2))
        self._row_off.setValue(float(getattr(b, "label_row_offset", 0.0)))
        self._label_color.setStyleSheet(
            f"background-color: {getattr(b, 'label_color', '') or '#000000'}; "
            "min-height: 22px;"
        )
        self._abl_on.setChecked(bool(getattr(b, "arrow_below_label", False)))
        self._abl_gap.setValue(float(getattr(b, "arrow_below_gap", 0.03)))
        self._abl_lw.setValue(float(getattr(b, "arrow_below_linewidth", 1.4)))
        self._abl_color.setStyleSheet(
            "background-color: "
            f"{getattr(b, 'arrow_below_color', '') or '#000000'};"
            " min-height: 22px;"
        )
        for w in widgets:
            w.blockSignals(False)

    def _populate_arrow(self, a) -> None:
        widgets = [
            self._arr_enabled, self._arr_lw, self._arr_y,
            self._arr_text, self._arr_text_fs, self._arr_text_dy,
        ]
        for w in widgets:
            w.blockSignals(True)
        self._arr_enabled.setChecked(bool(getattr(a, "enabled", False)))
        self._arr_color.setStyleSheet(
            f"background-color: {getattr(a, 'color', '') or '#C00000'};"
            " min-height: 22px;"
        )
        self._arr_lw.setValue(float(getattr(a, "linewidth", 1.8)))
        self._arr_y.setValue(float(getattr(a, "y_frac", 0.5)))
        self._arr_text.setText(str(getattr(a, "text", "") or ""))
        try:
            afs = int(getattr(a, "text_fontsize", 11) or 11)
        except (TypeError, ValueError):
            afs = 11
        self._arr_text_fs.setValue(max(4, afs))
        self._arr_text_dy.setValue(float(getattr(a, "text_y_offset", -0.06)))
        for w in widgets:
            w.blockSignals(False)

    # ── color pickers ────────────────────────────────────────────
    def _pick_color(self, attr: str, button: QtWidgets.QPushButton) -> None:
        if self._obj is None:
            return
        current = str(getattr(self._obj, attr, "") or "#000000") or "#000000"
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(current), self, "Pick color",
        )
        if not c.isValid():
            return
        button.setStyleSheet(
            f"background-color: {c.name()}; min-height: 22px;"
        )
        self._emit(attr, c.name())

    def _emit(self, attr: str, value) -> None:
        if not self._nf_uid or not self._zone_uid:
            return
        self.zone_changed.emit(
            self._nf_uid, self._kind, self._zone_uid, attr, value,
        )
