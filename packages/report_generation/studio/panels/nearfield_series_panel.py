"""Per-series near-field effect settings panel.

Displayed when a 'Near-Field Effect' sub-layer is selected
in the data tree.  Controls are written to / read from a
NearFieldLayer on the parent DataSeries.
"""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton

from ..figure_model import NearFieldLayer

_NF_STYLES = ["faded", "colored", "markers", "dashed"]


class NearFieldSeriesPanel(QWidget):
    """Settings panel for a single near-field sub-layer."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_uid: str = ""
        self._build_ui()

    @property
    def current_uid(self) -> str:
        return self._current_uid

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QLabel("Near-Field Effect")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        # Threshold group
        thresh_group = QGroupBox("NACD Threshold")
        thresh_form = QFormLayout(thresh_group)

        self._threshold = QDoubleSpinBox()
        self._threshold.setRange(0.0, 10.0)
        self._threshold.setSingleStep(0.1)
        self._threshold.setDecimals(2)
        self._threshold.setValue(1.0)
        self._threshold.valueChanged.connect(self.changed)
        thresh_form.addRow("Threshold:", self._threshold)

        layout.addWidget(thresh_group)

        # Display group
        disp_group = QGroupBox("Display")
        disp_form = QFormLayout(disp_group)

        self._style = QComboBox()
        self._style.addItems(_NF_STYLES)
        self._style.currentIndexChanged.connect(self.changed)
        disp_form.addRow("Style:", self._style)

        self._alpha = QDoubleSpinBox()
        self._alpha.setRange(0.0, 1.0)
        self._alpha.setSingleStep(0.05)
        self._alpha.setDecimals(2)
        self._alpha.setValue(0.4)
        self._alpha.valueChanged.connect(self.changed)
        disp_form.addRow("Opacity:", self._alpha)

        layout.addWidget(disp_group)

        # Colors group
        color_group = QGroupBox("Colors")
        color_form = QFormLayout(color_group)

        self._ff_color_btn = QPushButton("Far-field")
        self._ff_color_btn.setStyleSheet("background: blue; color: white;")
        self._ff_color_btn.clicked.connect(self._pick_ff_color)
        color_form.addRow("Far-field:", self._ff_color_btn)

        self._nf_color_btn = QPushButton("Near-field")
        self._nf_color_btn.setStyleSheet("background: red; color: white;")
        self._nf_color_btn.clicked.connect(self._pick_nf_color)
        color_form.addRow("Near-field:", self._nf_color_btn)

        layout.addWidget(color_group)
        layout.addStretch()

        self._ff_color = "blue"
        self._nf_color = "red"

    def _pick_ff_color(self) -> None:
        from ..qt_compat import QtWidgets as _QW
        c = _QW.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._ff_color = c.name()
            self._ff_color_btn.setStyleSheet(
                f"background: {self._ff_color}; color: white;"
            )
            self.changed.emit()

    def _pick_nf_color(self) -> None:
        from ..qt_compat import QtWidgets as _QW
        c = _QW.QColorDialog.getColor(parent=self)
        if c.isValid():
            self._nf_color = c.name()
            self._nf_color_btn.setStyleSheet(
                f"background: {self._nf_color}; color: white;"
            )
            self.changed.emit()

    # ── Read / Write ──────────────────────────────────────────────

    def load_from(self, uid: str, nf: NearFieldLayer) -> None:
        self._current_uid = uid
        self.blockSignals(True)
        self._threshold.setValue(nf.nacd_threshold)
        idx = self._style.findText(nf.style)
        if idx >= 0:
            self._style.setCurrentIndex(idx)
        self._alpha.setValue(nf.alpha)
        self._ff_color = nf.farfield_color
        self._nf_color = nf.nearfield_color
        self._ff_color_btn.setStyleSheet(
            f"background: {self._ff_color}; color: white;"
        )
        self._nf_color_btn.setStyleSheet(
            f"background: {self._nf_color}; color: white;"
        )
        self.blockSignals(False)

    def write_to(self, nf: NearFieldLayer) -> None:
        nf.nacd_threshold = self._threshold.value()
        nf.style = self._style.currentText()
        nf.alpha = self._alpha.value()
        nf.farfield_color = self._ff_color
        nf.nearfield_color = self._nf_color
