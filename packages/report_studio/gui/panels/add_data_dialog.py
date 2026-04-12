"""
Add-data dialog — per-subplot data addition.

Replaces the old ProjectDialog for adding data to a specific subplot.
The user selects:
  1. Figure type (from registry — currently just "Source Offset Curves")
  2. PKL file + optional NPZ file
  3. Which offsets to include (checklist)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
    DialogAccepted, DialogRejected,
    Checked, Unchecked,
)


class AddDataDialog(QtWidgets.QDialog):
    """Dialog for adding data to a specific subplot."""

    def __init__(self, parent=None, subplot_key: str = "main"):
        super().__init__(parent)
        self.setWindowTitle(f"Add Data — {subplot_key}")
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)

        self._subplot_key = subplot_key
        self._pkl_path = ""
        self._npz_path = ""
        self._offset_labels: List[str] = []
        self._selected_type_id = "source_offset"

        self._build_ui()
        self._restore_default_paths()

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Figure type selector
        type_group = QtWidgets.QGroupBox("Figure Type")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self._type_combo = QtWidgets.QComboBox()
        self._populate_type_combo()
        type_layout.addWidget(self._type_combo)
        layout.addWidget(type_group)

        # File selection
        file_group = QtWidgets.QGroupBox("Data Files")
        file_layout = QtWidgets.QFormLayout(file_group)

        pkl_row = QtWidgets.QHBoxLayout()
        self._pkl_edit = QtWidgets.QLineEdit()
        self._pkl_edit.setPlaceholderText("Select .pkl state file...")
        pkl_btn = QtWidgets.QPushButton("Browse...")
        pkl_btn.clicked.connect(self._browse_pkl)
        pkl_row.addWidget(self._pkl_edit, stretch=1)
        pkl_row.addWidget(pkl_btn)
        file_layout.addRow("State file (.pkl):", pkl_row)

        npz_row = QtWidgets.QHBoxLayout()
        self._npz_edit = QtWidgets.QLineEdit()
        self._npz_edit.setPlaceholderText("Optional: .npz spectrum file...")
        npz_btn = QtWidgets.QPushButton("Browse...")
        npz_btn.clicked.connect(self._browse_npz)
        npz_row.addWidget(self._npz_edit, stretch=1)
        npz_row.addWidget(npz_btn)
        file_layout.addRow("Spectrum (.npz):", npz_row)

        layout.addWidget(file_group)

        # Offset checklist
        offset_group = QtWidgets.QGroupBox("Select Offsets")
        offset_layout = QtWidgets.QVBoxLayout(offset_group)

        btn_row = QtWidgets.QHBoxLayout()
        self._btn_all = QtWidgets.QPushButton("Select All")
        self._btn_none = QtWidgets.QPushButton("Select None")
        self._btn_all.clicked.connect(self._select_all)
        self._btn_none.clicked.connect(self._select_none)
        btn_row.addWidget(self._btn_all)
        btn_row.addWidget(self._btn_none)
        btn_row.addStretch()
        offset_layout.addLayout(btn_row)

        self._offset_list = QtWidgets.QListWidget()
        offset_layout.addWidget(self._offset_list)

        self._lbl_status = QtWidgets.QLabel("Load a PKL file to see offsets.")
        self._lbl_status.setStyleSheet("color: #888;")
        offset_layout.addWidget(self._lbl_status)

        layout.addWidget(offset_group, stretch=1)

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

    # ── Populate helpers ───────────────────────────────────────────────

    def _populate_type_combo(self):
        # Import here to ensure plugins are registered
        from ...core.plugins import source_offset as _  # noqa: F401
        from ...core.figure_types import registry

        for plugin in registry.all_types():
            self._type_combo.addItem(plugin.display_name, plugin.type_id)

    # ── Browse handlers ────────────────────────────────────────────────

    def _browse_pkl(self):
        import os
        start = os.path.dirname(self._pkl_edit.text()) or ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select State File", start,
            "Pickle Files (*.pkl);;All Files (*)",
        )
        if path:
            self._pkl_edit.setText(path)
            self._load_offset_list(path)

    def _browse_npz(self):
        import os
        start = os.path.dirname(self._npz_edit.text()) or ""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Spectrum File", start,
            "NPZ Files (*.npz);;All Files (*)",
        )
        if path:
            self._npz_edit.setText(path)

    def _restore_default_paths(self):
        """Pre-fill PKL/NPZ from QSettings defaults."""
        try:
            from .project_start_dialog import load_data_paths
            pkl, npz = load_data_paths()
            if pkl and not self._pkl_edit.text():
                self._pkl_edit.setText(pkl)
                self._load_offset_list(pkl)
            if npz and not self._npz_edit.text():
                self._npz_edit.setText(npz)
        except Exception:
            pass

    def _load_offset_list(self, pkl_path: str):
        """Read PKL metadata and populate the offset checklist."""
        self._offset_list.clear()
        self._offset_labels.clear()

        try:
            from ...io.pkl_reader import read_pkl_metadata
            meta = read_pkl_metadata(pkl_path)
        except Exception as e:
            self._lbl_status.setText(f"Error reading PKL: {e}")
            return

        labels = meta.get("labels", [])
        if not labels:
            self._lbl_status.setText("No offsets found in this file.")
            return

        self._offset_labels = labels
        for label in labels:
            item = QtWidgets.QListWidgetItem(str(label))
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Checked)
            self._offset_list.addItem(item)

        self._lbl_status.setText(f"{len(labels)} offsets found — all selected.")

    # ── Select all / none ──────────────────────────────────────────────

    def _select_all(self):
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Checked)
        self._lbl_status.setText(f"{self._offset_list.count()} selected.")

    def _select_none(self):
        for i in range(self._offset_list.count()):
            self._offset_list.item(i).setCheckState(Unchecked)
        self._lbl_status.setText("0 selected.")

    # ── Accept ─────────────────────────────────────────────────────────

    def _on_accept(self):
        pkl = self._pkl_edit.text().strip()
        if not pkl or not Path(pkl).exists():
            QtWidgets.QMessageBox.warning(
                self, "Missing Data",
                "Please select a valid .pkl state file.",
            )
            return

        selected = self.selected_offsets
        if not selected:
            QtWidgets.QMessageBox.warning(
                self, "No Offsets",
                "Please select at least one offset.",
            )
            return

        # Persist paths for next time
        try:
            from .project_start_dialog import save_data_paths
            save_data_paths(pkl, self._npz_edit.text().strip())
        except Exception:
            pass

        self.accept()

    # ── Public API ─────────────────────────────────────────────────────

    @property
    def pkl_path(self) -> str:
        return self._pkl_edit.text().strip()

    @property
    def npz_path(self) -> str:
        return self._npz_edit.text().strip()

    @property
    def selected_offsets(self) -> List[str]:
        """Return the labels of checked offsets."""
        result = []
        for i in range(self._offset_list.count()):
            item = self._offset_list.item(i)
            if item.checkState() == Checked:
                result.append(item.text())
        return result

    @property
    def selected_type_id(self) -> str:
        idx = self._type_combo.currentIndex()
        if idx >= 0:
            return self._type_combo.itemData(idx)
        return "source_offset"

    @property
    def subplot_key(self) -> str:
        return self._subplot_key
