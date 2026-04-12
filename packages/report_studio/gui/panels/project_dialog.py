"""
Project dialog — data source selection when launching Report Studio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
    DialogAccepted, DialogRejected,
)


class ProjectDialog(QtWidgets.QDialog):
    """
    Dialog for selecting data sources (PKL + optional NPZ).

    The user can:
    - Load from a PKL state file (mandatory)
    - Optionally attach an NPZ spectrum file
    - Or use data from the current controller (if launched from main app)
    """

    def __init__(self, parent=None, controller=None,
                 default_pkl: str = "", default_npz: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Report Studio — Data Source")
        self.setMinimumWidth(500)

        self._controller = controller
        self._pkl_path = default_pkl
        self._npz_path = default_npz
        self._use_controller = controller is not None

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Source selection
        source_group = QtWidgets.QGroupBox("Data Source")
        source_layout = QtWidgets.QVBoxLayout(source_group)

        if self._controller is not None:
            self._rb_controller = QtWidgets.QRadioButton(
                "Use current session data"
            )
            self._rb_controller.setChecked(True)
            source_layout.addWidget(self._rb_controller)

            self._rb_file = QtWidgets.QRadioButton("Load from files")
            source_layout.addWidget(self._rb_file)
            self._rb_file.toggled.connect(self._on_source_toggled)
        else:
            self._rb_controller = None
            self._rb_file = None

        # File selection area
        self._file_widget = QtWidgets.QWidget()
        file_layout = QtWidgets.QFormLayout(self._file_widget)

        # PKL
        pkl_row = QtWidgets.QHBoxLayout()
        self._pkl_edit = QtWidgets.QLineEdit(self._pkl_path)
        self._pkl_edit.setPlaceholderText("Select .pkl state file...")
        pkl_btn = QtWidgets.QPushButton("Browse...")
        pkl_btn.clicked.connect(self._browse_pkl)
        pkl_row.addWidget(self._pkl_edit, stretch=1)
        pkl_row.addWidget(pkl_btn)
        file_layout.addRow("State file (.pkl):", pkl_row)

        # NPZ
        npz_row = QtWidgets.QHBoxLayout()
        self._npz_edit = QtWidgets.QLineEdit(self._npz_path)
        self._npz_edit.setPlaceholderText("Optional: select .npz spectrum file...")
        npz_btn = QtWidgets.QPushButton("Browse...")
        npz_btn.clicked.connect(self._browse_npz)
        npz_row.addWidget(self._npz_edit, stretch=1)
        npz_row.addWidget(npz_btn)
        file_layout.addRow("Spectrum (.npz):", npz_row)

        source_layout.addWidget(self._file_widget)

        if self._controller is not None:
            self._file_widget.setEnabled(False)

        layout.addWidget(source_group)

        # Buttons
        try:
            ok_btn = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            ok_btn = QtWidgets.QDialogButtonBox.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.Cancel

        btn_box = QtWidgets.QDialogButtonBox(ok_btn | cancel_btn)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ── Event handlers ─────────────────────────────────────────────────

    def _on_source_toggled(self, checked):
        self._file_widget.setEnabled(checked)
        self._use_controller = not checked

    def _browse_pkl(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select State File", "", "Pickle Files (*.pkl);;All Files (*)"
        )
        if path:
            self._pkl_edit.setText(path)

    def _browse_npz(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Spectrum File", "", "NPZ Files (*.npz);;All Files (*)"
        )
        if path:
            self._npz_edit.setText(path)

    def _on_accept(self):
        if self._use_controller and self._controller is not None:
            self.accept()
            return
        # Validate PKL path
        pkl = self._pkl_edit.text().strip()
        if not pkl or not Path(pkl).exists():
            QtWidgets.QMessageBox.warning(
                self, "Missing Data",
                "Please select a valid .pkl state file."
            )
            return
        self.accept()

    # ── Public getters ─────────────────────────────────────────────────

    @property
    def use_controller(self) -> bool:
        return self._use_controller

    @property
    def pkl_path(self) -> str:
        return self._pkl_edit.text().strip()

    @property
    def npz_path(self) -> str:
        return self._npz_edit.text().strip()
