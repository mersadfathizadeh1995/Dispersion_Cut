"""
Export panel — figure, subplot, and data export controls.

Tab 3 of the right panel. Collapsible sections for different export modes.
Modular architecture for data exporters.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Dict, List, Optional

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import SheetState


_IMAGE_FORMATS = ["PNG", "PDF", "SVG", "TIFF"]


class ExportPanel(QtWidgets.QWidget):
    """
    Export controls: figure export, per-subplot export, data export.

    Signals
    -------
    export_figure_requested(dict)
        {"path": str, "format": str, "dpi": int, "width": float, "height": float}
    export_subplots_requested(dict)
        {"path": str, "format": str, "dpi": int, "keys": List[str]}
    export_data_requested(dict)
        {"path": str, "format": str, "options": dict}
    """

    export_figure_requested = Signal(dict)
    export_subplots_requested = Signal(dict)
    export_data_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._subplot_checks: Dict[str, QtWidgets.QCheckBox] = {}
        self._sheet: Optional["SheetState"] = None
        self._build_ui()

    # ── Public API ────────────────────────────────────────────────────

    def set_sheet(self, sheet: "SheetState"):
        """Keep a reference to the current sheet for export dimensions."""
        self._sheet = sheet

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # ── Figure Export ────────────────────────────────────────────
        fig_sec = CollapsibleSection("Figure Export", expanded=True)
        fl = fig_sec.form
        fl.setSpacing(4)

        # Output directory
        dir_row = QtWidgets.QHBoxLayout()
        self._edit_fig_dir = QtWidgets.QLineEdit()
        self._edit_fig_dir.setPlaceholderText("Output directory")
        self._btn_browse_fig = QtWidgets.QPushButton("Browse")
        self._btn_browse_fig.clicked.connect(self._browse_fig_dir)
        dir_row.addWidget(self._edit_fig_dir)
        dir_row.addWidget(self._btn_browse_fig)
        fl.addRow("Path:", dir_row)

        self._combo_fig_fmt = QtWidgets.QComboBox()
        self._combo_fig_fmt.addItems(_IMAGE_FORMATS)
        fl.addRow("Format:", self._combo_fig_fmt)

        self._spin_fig_dpi = QtWidgets.QSpinBox()
        self._spin_fig_dpi.setRange(72, 2400)
        self._spin_fig_dpi.setSingleStep(50)
        self._spin_fig_dpi.setValue(300)
        fl.addRow("DPI:", self._spin_fig_dpi)

        self._btn_export_fig = QtWidgets.QPushButton("Export Figure")
        self._btn_export_fig.clicked.connect(self._on_export_figure)
        fl.addRow(self._btn_export_fig)

        layout.addWidget(fig_sec)

        # ── Subplot Export ───────────────────────────────────────────
        sub_sec = CollapsibleSection("Individual Subplot Export", expanded=False)
        self._sub_form = sub_sec.form
        self._sub_form.setSpacing(2)

        self._lbl_no_subplots = QtWidgets.QLabel("Load data to see subplots")
        self._sub_form.addRow(self._lbl_no_subplots)

        self._btn_export_subs = QtWidgets.QPushButton("Export Selected Subplots")
        self._btn_export_subs.clicked.connect(self._on_export_subplots)
        self._sub_form.addRow(self._btn_export_subs)

        layout.addWidget(sub_sec)

        # ── Data Export ──────────────────────────────────────────────
        data_sec = CollapsibleSection("Data Export", expanded=False)
        dl = data_sec.form
        dl.setSpacing(4)

        self._combo_data_fmt = QtWidgets.QComboBox()
        self._combo_data_fmt.addItems(["CSV", "Excel", "TXT"])
        dl.addRow("Format:", self._combo_data_fmt)

        self._btn_export_data = QtWidgets.QPushButton("Export Curve Data")
        self._btn_export_data.clicked.connect(self._on_export_data)
        dl.addRow(self._btn_export_data)

        layout.addWidget(data_sec)

        layout.addStretch(1)

    def update_subplots(self, keys: List[str]):
        """Update the subplot checkboxes list."""
        for chk in self._subplot_checks.values():
            self._sub_form.removeRow(chk)
        self._subplot_checks.clear()

        self._lbl_no_subplots.setVisible(not keys)
        for key in keys:
            chk = QtWidgets.QCheckBox(key)
            chk.setChecked(True)
            self._subplot_checks[key] = chk
            # Insert before the export button row
            row_count = self._sub_form.rowCount()
            self._sub_form.insertRow(row_count - 1, chk)

    # ── Internal ──────────────────────────────────────────────────────

    def _browse_fig_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Export Directory")
        if d:
            self._edit_fig_dir.setText(d)

    def _on_export_figure(self):
        path = self._edit_fig_dir.text()
        if not path:
            self._browse_fig_dir()
            path = self._edit_fig_dir.text()
        if not path:
            return
        fmt = self._combo_fig_fmt.currentText().lower()
        # Use figure dimensions from the current sheet (global settings)
        width = self._sheet.figure_width if self._sheet else 10.0
        height = self._sheet.figure_height if self._sheet else 7.0
        self.export_figure_requested.emit({
            "path": os.path.join(path, f"figure.{fmt}"),
            "format": fmt,
            "dpi": self._spin_fig_dpi.value(),
            "width": width,
            "height": height,
        })

    def _on_export_subplots(self):
        path = self._edit_fig_dir.text()
        if not path:
            self._browse_fig_dir()
            path = self._edit_fig_dir.text()
        if not path:
            return
        selected = [k for k, chk in self._subplot_checks.items() if chk.isChecked()]
        if not selected:
            return
        fmt = self._combo_fig_fmt.currentText().lower()
        self.export_subplots_requested.emit({
            "path": path,
            "format": fmt,
            "dpi": self._spin_fig_dpi.value(),
            "keys": selected,
        })

    def _on_export_data(self):
        path = self._edit_fig_dir.text()
        if not path:
            self._browse_fig_dir()
            path = self._edit_fig_dir.text()
        if not path:
            return
        self.export_data_requested.emit({
            "path": path,
            "format": self._combo_data_fmt.currentText().lower(),
        })
