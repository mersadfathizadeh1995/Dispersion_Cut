"""Settings for one :class:`NFLambdaLine` attached to a curve."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...qt_compat import QtWidgets, QtGui, Signal

if TYPE_CHECKING:
    from ...core.models import NFLambdaLine, OffsetCurve


class LambdaSettingsPanel(QtWidgets.QWidget):
    style_changed = Signal(str, str, str, object)  # curve_uid, lambda_uid, attr, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curve_uid = ""
        self._lam_uid = ""
        self._curve: Optional["OffsetCurve"] = None
        self._line: Optional["NFLambdaLine"] = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        # ── Line appearance ──────────────────────────────────────────
        appearance = QtWidgets.QGroupBox("Line")
        form = QtWidgets.QFormLayout(appearance)
        form.setSpacing(4)

        self._color = QtWidgets.QPushButton()
        self._color.clicked.connect(self._pick_color)
        form.addRow("Color:", self._color)

        self._style = QtWidgets.QComboBox()
        for s in ("-", "--", "-.", ":"):
            self._style.addItem(s, s)
        self._style.currentIndexChanged.connect(self._emit_style)
        form.addRow("Line style:", self._style)

        self._width = QtWidgets.QDoubleSpinBox()
        self._width.setRange(0.5, 6.0)
        self._width.setSingleStep(0.25)
        self._width.valueChanged.connect(
            lambda v: self._emit_attr("line_width", float(v))
        )
        form.addRow("Line width:", self._width)

        self._alpha = QtWidgets.QDoubleSpinBox()
        self._alpha.setRange(0.05, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.valueChanged.connect(
            lambda v: self._emit_attr("alpha", float(v))
        )
        form.addRow("Alpha:", self._alpha)

        outer.addWidget(appearance)

        # ── Label group ──────────────────────────────────────────────
        label_box = QtWidgets.QGroupBox("Label")
        lf = QtWidgets.QFormLayout(label_box)
        lf.setSpacing(4)

        self._show_lbl = QtWidgets.QCheckBox("Show label")
        self._show_lbl.toggled.connect(
            lambda v: self._emit_attr("show_label", bool(v))
        )
        lf.addRow(self._show_lbl)

        self._custom_label = QtWidgets.QLineEdit()
        self._custom_label.setPlaceholderText("(default: λ = value m)")
        self._custom_label.editingFinished.connect(
            lambda: self._emit_attr("custom_label", self._custom_label.text())
        )
        lf.addRow("Text:", self._custom_label)

        self._label_pos = QtWidgets.QDoubleSpinBox()
        self._label_pos.setRange(0.02, 0.98)
        self._label_pos.setSingleStep(0.05)
        self._label_pos.setDecimals(2)
        self._label_pos.setToolTip(
            "Position along the visible part of the line (0=start, 1=end)"
        )
        self._label_pos.valueChanged.connect(
            lambda v: self._emit_attr("label_position", float(v))
        )
        lf.addRow("Position:", self._label_pos)

        self._rot_mode = QtWidgets.QComboBox()
        self._rot_mode.addItem("Along line", "along")
        self._rot_mode.addItem("Horizontal", "horizontal")
        self._rot_mode.currentIndexChanged.connect(
            lambda _i: self._emit_attr(
                "label_rotation_mode", self._rot_mode.currentData()
            )
        )
        lf.addRow("Rotation:", self._rot_mode)

        self._label_fs = QtWidgets.QSpinBox()
        self._label_fs.setRange(6, 32)
        self._label_fs.valueChanged.connect(
            lambda v: self._emit_attr("label_fontsize", int(v))
        )
        lf.addRow("Font size:", self._label_fs)

        outer.addWidget(label_box)

        # ── Background box ───────────────────────────────────────────
        box = QtWidgets.QGroupBox("Background box")
        bf = QtWidgets.QFormLayout(box)
        bf.setSpacing(4)

        self._box_on = QtWidgets.QCheckBox("Show box behind label")
        self._box_on.toggled.connect(
            lambda v: self._emit_attr("label_box", bool(v))
        )
        bf.addRow(self._box_on)

        self._box_face = QtWidgets.QPushButton()
        self._box_face.clicked.connect(self._pick_box_face)
        bf.addRow("Fill color:", self._box_face)

        self._box_edge = QtWidgets.QPushButton()
        self._box_edge.clicked.connect(self._pick_box_edge)
        bf.addRow("Border:", self._box_edge)

        self._box_alpha = QtWidgets.QDoubleSpinBox()
        self._box_alpha.setRange(0.0, 1.0)
        self._box_alpha.setSingleStep(0.05)
        self._box_alpha.setDecimals(2)
        self._box_alpha.valueChanged.connect(
            lambda v: self._emit_attr("label_box_alpha", float(v))
        )
        bf.addRow("Opacity:", self._box_alpha)

        self._box_pad = QtWidgets.QDoubleSpinBox()
        self._box_pad.setRange(0.0, 20.0)
        self._box_pad.setSingleStep(0.5)
        self._box_pad.valueChanged.connect(
            lambda v: self._emit_attr("label_box_pad", float(v))
        )
        bf.addRow("Padding:", self._box_pad)

        outer.addWidget(box)
        outer.addStretch(1)

    # ── public API ────────────────────────────────────────────────────
    def show_lambda_line(self, curve: "OffsetCurve", line: "NFLambdaLine") -> None:
        self._curve = curve
        self._line = line
        self._curve_uid = curve.uid
        self._lam_uid = line.uid
        widgets = [
            self._style, self._width, self._alpha, self._show_lbl,
            self._custom_label, self._label_pos, self._rot_mode,
            self._label_fs, self._box_on, self._box_alpha, self._box_pad,
        ]
        for w in widgets:
            w.blockSignals(True)
        idx = self._style.findData(line.line_style)
        self._style.setCurrentIndex(max(0, idx))
        self._width.setValue(float(line.line_width))
        self._alpha.setValue(float(line.alpha))
        self._show_lbl.setChecked(bool(line.show_label))
        self._custom_label.setText(line.custom_label or "")
        try:
            self._label_pos.setValue(float(line.label_position))
        except (TypeError, ValueError):
            self._label_pos.setValue(0.55)
        rmi = self._rot_mode.findData(line.label_rotation_mode or "along")
        self._rot_mode.setCurrentIndex(max(0, rmi))
        fs = int(line.label_fontsize) if line.label_fontsize else 10
        self._label_fs.setValue(fs)
        self._box_on.setChecked(bool(line.label_box))
        self._box_alpha.setValue(float(line.label_box_alpha))
        self._box_pad.setValue(float(line.label_box_pad))
        self._color.setStyleSheet(
            f"background-color: {line.color}; min-height: 22px;"
        )
        self._box_face.setStyleSheet(
            f"background-color: {line.label_box_facecolor}; min-height: 22px;"
        )
        self._box_edge.setStyleSheet(
            f"background-color: {line.label_box_edgecolor}; min-height: 22px;"
        )
        for w in widgets:
            w.blockSignals(False)

    # ── color helpers ─────────────────────────────────────────────────
    def _pick_color(self):
        if not self._line:
            return
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._line.color), self, "Line color"
        )
        if c.isValid():
            self._color.setStyleSheet(
                f"background-color: {c.name()}; min-height: 22px;"
            )
            self._emit_attr("color", c.name())

    def _pick_box_face(self):
        if not self._line:
            return
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._line.label_box_facecolor), self, "Box fill"
        )
        if c.isValid():
            self._box_face.setStyleSheet(
                f"background-color: {c.name()}; min-height: 22px;"
            )
            self._emit_attr("label_box_facecolor", c.name())

    def _pick_box_edge(self):
        if not self._line:
            return
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self._line.label_box_edgecolor), self, "Box border"
        )
        if c.isValid():
            self._box_edge.setStyleSheet(
                f"background-color: {c.name()}; min-height: 22px;"
            )
            self._emit_attr("label_box_edgecolor", c.name())

    # ── emission ─────────────────────────────────────────────────────
    def _emit_style(self, _i: int):
        if self._line:
            self._emit_attr("line_style", self._style.currentData())

    def _emit_attr(self, attr: str, value):
        if self._line is None:
            return
        self.style_changed.emit(self._curve_uid, self._lam_uid, attr, value)
