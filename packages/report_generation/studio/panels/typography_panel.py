"""Typography settings panel -- fonts, sizes, weights, presets."""
from __future__ import annotations

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QComboBox = QtWidgets.QComboBox
QCheckBox = QtWidgets.QCheckBox
QPushButton = QtWidgets.QPushButton
QHBoxLayout = QtWidgets.QHBoxLayout

from ..models import TypographyConfig

FONT_FAMILIES = [
    "serif", "sans-serif", "monospace",
    "Times New Roman", "Arial", "Helvetica",
    "Calibri", "Cambria", "Georgia",
    "DejaVu Serif", "DejaVu Sans",
]


class TypographyPanel(QWidget):
    """Controls for fonts, sizes, weights, and typography presets."""

    changed = Signal()
    preset_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Font group --
        font_group = QGroupBox("Font")
        font_form = QFormLayout(font_group)

        self._family = QComboBox()
        self._family.setEditable(True)
        self._family.addItems(FONT_FAMILIES)
        self._family.setCurrentText("serif")
        font_form.addRow("Family:", self._family)

        self._bold = QCheckBox("Bold")
        font_form.addRow(self._bold)

        layout.addWidget(font_group)

        # -- Sizes group --
        sizes_group = QGroupBox("Font Sizes (pt)")
        sizes_form = QFormLayout(sizes_group)

        self._title_size = self._size_spin(14.0)
        sizes_form.addRow("Title:", self._title_size)
        self._label_size = self._size_spin(12.0)
        sizes_form.addRow("Axis labels:", self._label_size)
        self._tick_size = self._size_spin(10.0)
        sizes_form.addRow("Tick labels:", self._tick_size)
        self._legend_size = self._size_spin(10.0)
        sizes_form.addRow("Legend:", self._legend_size)
        self._annotation_size = self._size_spin(9.0)
        sizes_form.addRow("Annotations:", self._annotation_size)

        layout.addWidget(sizes_group)

        # -- Spacing group --
        spacing_group = QGroupBox("Spacing")
        spacing_form = QFormLayout(spacing_group)

        self._title_pad = self._size_spin(6.0)
        spacing_form.addRow("Title padding:", self._title_pad)
        self._label_pad = self._size_spin(4.0)
        spacing_form.addRow("Label padding:", self._label_pad)
        self._bold_ticks = QCheckBox("Bold tick labels")
        spacing_form.addRow(self._bold_ticks)

        layout.addWidget(spacing_group)

        # -- Presets --
        presets_group = QGroupBox("Presets")
        presets_layout = QHBoxLayout(presets_group)
        btn_pub = QPushButton("Publication")
        btn_pub.clicked.connect(lambda: self.preset_requested.emit("publication"))
        btn_compact = QPushButton("Compact")
        btn_compact.clicked.connect(lambda: self.preset_requested.emit("compact"))
        presets_layout.addWidget(btn_pub)
        presets_layout.addWidget(btn_compact)
        layout.addWidget(presets_group)

        layout.addStretch()

        # Wire signals
        self._family.currentTextChanged.connect(lambda: self.changed.emit())
        self._bold.toggled.connect(self.changed)
        for s in (self._title_size, self._label_size, self._tick_size,
                  self._legend_size, self._annotation_size,
                  self._title_pad, self._label_pad):
            s.valueChanged.connect(self.changed)
        self._bold_ticks.toggled.connect(self.changed)

    def _size_spin(self, default: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(4.0, 48.0)
        spin.setSingleStep(0.5)
        spin.setDecimals(1)
        spin.setSuffix(" pt")
        spin.setValue(default)
        return spin

    def write_to(self, cfg: TypographyConfig) -> None:
        cfg.font_family = self._family.currentText()
        cfg.font_weight = "bold" if self._bold.isChecked() else "normal"
        cfg.title_size = self._title_size.value()
        cfg.axis_label_size = self._label_size.value()
        cfg.tick_label_size = self._tick_size.value()
        cfg.legend_size = self._legend_size.value()
        cfg.annotation_size = self._annotation_size.value()
        cfg.title_pad = self._title_pad.value()
        cfg.label_pad = self._label_pad.value()
        cfg.bold_ticks = self._bold_ticks.isChecked()

    def read_from(self, cfg: TypographyConfig) -> None:
        widgets = [self._family, self._bold, self._title_size, self._label_size,
                   self._tick_size, self._legend_size, self._annotation_size,
                   self._title_pad, self._label_pad, self._bold_ticks]
        for w in widgets:
            w.blockSignals(True)
        self._family.setCurrentText(cfg.font_family)
        self._bold.setChecked(cfg.font_weight == "bold")
        self._title_size.setValue(cfg.title_size)
        self._label_size.setValue(cfg.axis_label_size)
        self._tick_size.setValue(cfg.tick_label_size)
        self._legend_size.setValue(cfg.legend_size)
        self._annotation_size.setValue(cfg.annotation_size)
        self._title_pad.setValue(cfg.title_pad)
        self._label_pad.setValue(cfg.label_pad)
        self._bold_ticks.setChecked(cfg.bold_ticks)
        for w in widgets:
            w.blockSignals(False)
