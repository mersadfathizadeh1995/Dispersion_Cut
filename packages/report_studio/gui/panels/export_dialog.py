"""
Export dialog — choose format, DPI, and size for canvas export.
"""

from __future__ import annotations

from pathlib import Path

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
    DialogAccepted, DialogRejected,
)


class ExportDialog(QtWidgets.QDialog):
    """
    Image export dialog — select format, DPI, and dimensions.

    Attributes after exec():
        path : str — chosen file path
        dpi  : int — selected DPI
        width_inches : float — figure width
        height_inches : float — figure height
    """

    def __init__(self, parent=None, default_name: str = "report"):
        super().__init__(parent)
        self.setWindowTitle("Export Image")
        self.setMinimumWidth(400)

        self.path = ""
        self.dpi = 300
        self.width_inches = 10.0
        self.height_inches = 7.0

        self._default_name = default_name
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Format + path
        path_group = QtWidgets.QGroupBox("Output")
        pg = QtWidgets.QHBoxLayout()
        self._edit_path = QtWidgets.QLineEdit()
        self._edit_path.setPlaceholderText("Select output file...")
        self._btn_browse = QtWidgets.QPushButton("Browse...")
        self._btn_browse.clicked.connect(self._on_browse)
        pg.addWidget(self._edit_path, 1)
        pg.addWidget(self._btn_browse)
        path_group.setLayout(pg)
        layout.addWidget(path_group)

        # Settings
        settings_group = QtWidgets.QGroupBox("Settings")
        sl = QtWidgets.QFormLayout()

        self._spin_dpi = QtWidgets.QSpinBox()
        self._spin_dpi.setRange(72, 1200)
        self._spin_dpi.setValue(300)
        self._spin_dpi.setSingleStep(50)
        sl.addRow("DPI:", self._spin_dpi)

        self._spin_width = QtWidgets.QDoubleSpinBox()
        self._spin_width.setRange(2.0, 30.0)
        self._spin_width.setValue(10.0)
        self._spin_width.setSingleStep(0.5)
        self._spin_width.setSuffix(" in")
        sl.addRow("Width:", self._spin_width)

        self._spin_height = QtWidgets.QDoubleSpinBox()
        self._spin_height.setRange(2.0, 30.0)
        self._spin_height.setValue(7.0)
        self._spin_height.setSingleStep(0.5)
        self._spin_height.setSuffix(" in")
        sl.addRow("Height:", self._spin_height)

        settings_group.setLayout(sl)
        layout.addWidget(settings_group)

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox()
        try:
            ok_btn = btn_box.addButton(
                QtWidgets.QDialogButtonBox.StandardButton.Ok
            )
            cancel_btn = btn_box.addButton(
                QtWidgets.QDialogButtonBox.StandardButton.Cancel
            )
        except AttributeError:
            ok_btn = btn_box.addButton(QtWidgets.QDialogButtonBox.Ok)
            cancel_btn = btn_box.addButton(QtWidgets.QDialogButtonBox.Cancel)

        ok_btn.setText("Export")
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _on_browse(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Image",
            f"{self._default_name}.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;TIFF (*.tiff);;All (*)",
        )
        if path:
            self._edit_path.setText(path)

    def _on_accept(self):
        path = self._edit_path.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(
                self, "Export", "Please select an output file."
            )
            return

        self.path = path
        self.dpi = self._spin_dpi.value()
        self.width_inches = self._spin_width.value()
        self.height_inches = self._spin_height.value()
        self.accept()
