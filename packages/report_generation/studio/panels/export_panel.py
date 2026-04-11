"""Export panel -- format, DPI, transparency, export/batch actions."""
from __future__ import annotations

import os
from pathlib import Path

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QSpinBox = QtWidgets.QSpinBox
QCheckBox = QtWidgets.QCheckBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QPushButton = QtWidgets.QPushButton
QHBoxLayout = QtWidgets.QHBoxLayout
QLineEdit = QtWidgets.QLineEdit
QFileDialog = QtWidgets.QFileDialog
QLabel = QtWidgets.QLabel

from ..models import ExportConfig, OutputConfig

_FORMAT_ITEMS = [
    ("PDF", "pdf"),
    ("PNG", "png"),
    ("SVG", "svg"),
    ("EPS", "eps"),
    ("TIFF", "tiff"),
]

_DPI_PRESETS = {
    "Screen (72)": 72,
    "Print (300)": 300,
    "High (600)": 600,
    "Custom": None,
}


class ExportPanel(QWidget):
    """Controls for exporting the current figure to disk."""

    export_requested = Signal(str, dict)
    batch_requested = Signal(str, dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # -- Output directory --
        dir_group = QGroupBox("Output Directory")
        dir_layout = QVBoxLayout(dir_group)
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select output directory...")
        dir_row.addWidget(self._dir_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_directory)
        dir_row.addWidget(browse_btn)
        dir_layout.addLayout(dir_row)
        layout.addWidget(dir_group)

        # -- Naming --
        name_group = QGroupBox("File Naming")
        name_form = QFormLayout(name_group)

        self._auto_name = QCheckBox("Auto-generate name")
        self._auto_name.setChecked(True)
        self._auto_name.toggled.connect(self._on_auto_name_toggled)
        name_form.addRow(self._auto_name)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("custom_name")
        self._name_edit.setEnabled(False)
        name_form.addRow("Name:", self._name_edit)

        self._overwrite = QCheckBox("Overwrite existing")
        self._overwrite.setChecked(False)
        name_form.addRow(self._overwrite)

        layout.addWidget(name_group)

        # -- Format --
        fmt_group = QGroupBox("Format && Quality")
        fmt_form = QFormLayout(fmt_group)

        self._format = QComboBox()
        for display, value in _FORMAT_ITEMS:
            self._format.addItem(display, value)
        self._format.setCurrentIndex(0)
        fmt_form.addRow("Format:", self._format)

        self._dpi_preset = QComboBox()
        self._dpi_preset.addItems(list(_DPI_PRESETS.keys()))
        self._dpi_preset.setCurrentText("Print (300)")
        self._dpi_preset.currentTextChanged.connect(self._on_dpi_preset_changed)
        fmt_form.addRow("Quality:", self._dpi_preset)

        self._dpi_custom = QSpinBox()
        self._dpi_custom.setRange(72, 2400)
        self._dpi_custom.setValue(300)
        self._dpi_custom.setEnabled(False)
        fmt_form.addRow("DPI:", self._dpi_custom)

        self._transparent = QCheckBox("Transparent background")
        fmt_form.addRow(self._transparent)

        self._tight_bbox = QCheckBox("Tight bounding box")
        self._tight_bbox.setChecked(True)
        fmt_form.addRow(self._tight_bbox)

        self._pad = QDoubleSpinBox()
        self._pad.setRange(0.0, 1.0)
        self._pad.setSingleStep(0.05)
        self._pad.setDecimals(2)
        self._pad.setValue(0.1)
        fmt_form.addRow("Pad (in):", self._pad)

        layout.addWidget(fmt_group)

        # -- Action buttons --
        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)

        batch_btn = QPushButton("Batch Export")
        batch_btn.setToolTip("Export to all formats in the output directory")
        batch_btn.clicked.connect(self._on_batch)
        btn_layout.addWidget(batch_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    @property
    def output_directory(self) -> str:
        return self._dir_edit.text().strip()

    def set_output_directory(self, path: str) -> None:
        """Programmatically set the output directory (e.g. from project dir)."""
        if path and not self._dir_edit.text().strip():
            self._dir_edit.setText(os.path.join(path, "exports"))

    def _browse_directory(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                             self._dir_edit.text())
        if d:
            self._dir_edit.setText(d)

    def _on_auto_name_toggled(self, checked: bool) -> None:
        self._name_edit.setEnabled(not checked)

    def _on_dpi_preset_changed(self, text: str) -> None:
        value = _DPI_PRESETS.get(text)
        if value is None:
            self._dpi_custom.setEnabled(True)
        else:
            self._dpi_custom.setEnabled(False)
            self._dpi_custom.setValue(value)

    def get_export_options(self) -> dict:
        dpi = self._dpi_custom.value()
        fmt = self._format.currentData()
        return {
            "format": fmt,
            "dpi": dpi,
            "transparent": self._transparent.isChecked(),
            "bbox_inches": "tight" if self._tight_bbox.isChecked() else None,
            "pad_inches": self._pad.value(),
            "facecolor": "none" if self._transparent.isChecked() else "white",
        }

    def resolve_filename(self, plot_type: str) -> str:
        """Build the output file path from current settings."""
        fmt = self._format.currentData()
        directory = self.output_directory

        if self._auto_name.isChecked():
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base = f"{plot_type}_{ts}"
        else:
            base = self._name_edit.text().strip() or plot_type

        filename = f"{base}.{fmt}"
        path = os.path.join(directory, filename) if directory else filename

        if not self._overwrite.isChecked() and os.path.exists(path):
            counter = 1
            while True:
                candidate = os.path.join(
                    directory,
                    f"{base}_{counter:03d}.{fmt}",
                ) if directory else f"{base}_{counter:03d}.{fmt}"
                if not os.path.exists(candidate):
                    path = candidate
                    break
                counter += 1

        return path

    def _on_export(self) -> None:
        opts = self.get_export_options()
        path = self.resolve_filename(opts.get("_plot_type", "figure"))
        self.export_requested.emit(path, opts)

    def _on_batch(self) -> None:
        d = self.output_directory
        if not d:
            d = QFileDialog.getExistingDirectory(self, "Select Batch Directory")
            if d:
                self._dir_edit.setText(d)
            else:
                return
        opts = self.get_export_options()
        self.batch_requested.emit(d, opts)

    def write_to_configs(self, export_cfg: ExportConfig,
                         output_cfg: OutputConfig) -> None:
        export_cfg.format = self._format.currentData()
        export_cfg.dpi = self._dpi_custom.value()
        export_cfg.transparent = self._transparent.isChecked()
        export_cfg.tight_bbox = self._tight_bbox.isChecked()
        export_cfg.pad_inches = self._pad.value()
        output_cfg.directory = self._dir_edit.text().strip()
        output_cfg.auto_name = self._auto_name.isChecked()
        output_cfg.overwrite = self._overwrite.isChecked()
        output_cfg.name_template = self._name_edit.text().strip()

    def read_from_configs(self, export_cfg: ExportConfig,
                          output_cfg: OutputConfig) -> None:
        widgets = [self._format, self._dpi_custom, self._dpi_preset,
                   self._transparent, self._tight_bbox, self._pad,
                   self._dir_edit, self._auto_name, self._overwrite,
                   self._name_edit]
        for w in widgets:
            w.blockSignals(True)
        idx = self._format.findData(export_cfg.format)
        if idx >= 0:
            self._format.setCurrentIndex(idx)
        self._dpi_custom.setValue(export_cfg.dpi)
        matched = False
        for label, val in _DPI_PRESETS.items():
            if val == export_cfg.dpi:
                self._dpi_preset.setCurrentText(label)
                matched = True
                break
        if not matched:
            self._dpi_preset.setCurrentText("Custom")
            self._dpi_custom.setEnabled(True)
        self._transparent.setChecked(export_cfg.transparent)
        self._tight_bbox.setChecked(export_cfg.tight_bbox)
        self._pad.setValue(export_cfg.pad_inches)
        self._dir_edit.setText(output_cfg.directory)
        self._auto_name.setChecked(output_cfg.auto_name)
        self._name_edit.setEnabled(not output_cfg.auto_name)
        self._overwrite.setChecked(output_cfg.overwrite)
        self._name_edit.setText(output_cfg.name_template)
        for w in widgets:
            w.blockSignals(False)
