"""Project setup dialog for Report Studio.

Unified dialog for data source selection and project directory setup.
Replaces the simple Yes/No project directory prompt.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from .qt_compat import (
    QtWidgets, QtCore,
    AlignLeft, AlignRight,
)

QDialog = QtWidgets.QDialog
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QCheckBox = QtWidgets.QCheckBox
QLabel = QtWidgets.QLabel
QLineEdit = QtWidgets.QLineEdit
QPushButton = QtWidgets.QPushButton
QComboBox = QtWidgets.QComboBox
QFileDialog = QtWidgets.QFileDialog
QDialogButtonBox = QtWidgets.QDialogButtonBox
QMessageBox = QtWidgets.QMessageBox

try:
    QSettings = QtCore.QSettings
except AttributeError:
    from matplotlib.backends.qt_compat import QtCore as _QC
    QSettings = _QC.QSettings

_SETTINGS_ORG = "DCCut"
_SETTINGS_APP = "ReportStudio"
_KEY_LAST_PROJECT_DIR = "project/last_base_dir"
_KEY_LAST_PROJECT_NAME = "project/last_name"
_KEY_RECENT_PROJECTS = "project/recent"
_KEY_LAST_PKL = "data/last_pkl"
_KEY_LAST_NPZ = "data/last_npz"
_MAX_RECENT = 8


class StudioProjectDialog(QDialog):
    """Project setup dialog combining data source and project directory."""

    def __init__(
        self,
        controller=None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._controller = controller
        self._has_controller = controller is not None
        self._qsettings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

        self.setWindowTitle("Report Studio — Project Setup")
        self.setMinimumWidth(560)

        self._build_ui()
        self._restore_from_settings()

    # ── Public results ────────────────────────────────────────────

    @property
    def use_controller(self) -> bool:
        return self._from_memory_cb.isChecked()

    @property
    def pkl_path(self) -> str:
        return self._pkl_edit.text().strip()

    @property
    def npz_path(self) -> str:
        return self._npz_edit.text().strip()

    @property
    def project_dir(self) -> str:
        return self._resolved_path()

    @property
    def project_name(self) -> str:
        return self._name_edit.text().strip()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Section A: Data Source ────────────────────────────────
        data_group = QGroupBox("Data Source")
        data_layout = QVBoxLayout(data_group)

        self._from_memory_cb = QCheckBox("Load from DC Cut (data in memory)")
        self._from_memory_cb.setChecked(self._has_controller)
        self._from_memory_cb.setEnabled(self._has_controller)
        self._from_memory_cb.toggled.connect(self._on_memory_toggled)
        data_layout.addWidget(self._from_memory_cb)

        # Summary label when loading from memory
        self._memory_summary = QLabel()
        self._memory_summary.setStyleSheet("color: #666; margin-left: 20px;")
        data_layout.addWidget(self._memory_summary)
        self._update_memory_summary()

        # File pickers (for when not using controller)
        self._file_form = QWidget()
        file_layout = QFormLayout(self._file_form)
        file_layout.setContentsMargins(20, 4, 0, 0)

        # PKL file
        pkl_row = QHBoxLayout()
        self._pkl_edit = QLineEdit()
        self._pkl_edit.setPlaceholderText("Path to .pkl or .dc_state session file")
        pkl_row.addWidget(self._pkl_edit, stretch=1)
        pkl_browse = QPushButton("Browse…")
        pkl_browse.setFixedWidth(80)
        pkl_browse.clicked.connect(self._browse_pkl)
        pkl_row.addWidget(pkl_browse)
        file_layout.addRow("Session file:", pkl_row)

        # NPZ file
        npz_row = QHBoxLayout()
        self._npz_edit = QLineEdit()
        self._npz_edit.setPlaceholderText("Path to spectrum .npz file (optional)")
        npz_row.addWidget(self._npz_edit, stretch=1)
        npz_browse = QPushButton("Browse…")
        npz_browse.setFixedWidth(80)
        npz_browse.clicked.connect(self._browse_npz)
        npz_row.addWidget(npz_browse)
        file_layout.addRow("Spectrum file:", npz_row)

        data_layout.addWidget(self._file_form)
        layout.addWidget(data_group)

        # ── Section B: Project Directory ──────────────────────────
        proj_group = QGroupBox("Project Directory")
        proj_layout = QFormLayout(proj_group)

        # Recent projects
        recent_row = QHBoxLayout()
        self._recent_combo = QComboBox()
        self._recent_combo.setEditable(False)
        self._recent_combo.addItem("— New Project —")
        self._recent_combo.currentIndexChanged.connect(self._on_recent_selected)
        recent_row.addWidget(self._recent_combo, stretch=1)
        proj_layout.addRow("Recent:", recent_row)

        # Project name
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Site_A_Report")
        self._name_edit.textChanged.connect(self._update_resolved_display)
        proj_layout.addRow("Project name:", self._name_edit)

        # Base directory
        base_row = QHBoxLayout()
        self._base_dir_edit = QLineEdit()
        self._base_dir_edit.setPlaceholderText("Select base directory…")
        self._base_dir_edit.textChanged.connect(self._update_resolved_display)
        base_row.addWidget(self._base_dir_edit, stretch=1)
        base_browse = QPushButton("Browse…")
        base_browse.setFixedWidth(80)
        base_browse.clicked.connect(self._browse_base_dir)
        base_row.addWidget(base_browse)
        proj_layout.addRow("Base directory:", base_row)

        # Resolved path display
        self._resolved_label = QLabel()
        self._resolved_label.setStyleSheet(
            "color: #0078d4; font-weight: bold; padding: 4px;"
        )
        proj_layout.addRow("Project path:", self._resolved_label)

        layout.addWidget(proj_group)

        # ── Buttons ───────────────────────────────────────────────
        try:
            btn_ok = QDialogButtonBox.StandardButton.Ok
            btn_cancel = QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            btn_ok = QDialogButtonBox.Ok
            btn_cancel = QDialogButtonBox.Cancel

        self._buttons = QDialogButtonBox(btn_ok | btn_cancel)
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        # Initial state
        self._on_memory_toggled(self._from_memory_cb.isChecked())

    # ── Slots ─────────────────────────────────────────────────────

    def _on_memory_toggled(self, checked: bool) -> None:
        self._file_form.setVisible(not checked)
        self._memory_summary.setVisible(checked)
        self.adjustSize()

    def _browse_pkl(self) -> None:
        start = os.path.dirname(self._pkl_edit.text()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Session File", start,
            "Session Files (*.pkl *.dc_state);;All Files (*)",
        )
        if path:
            self._pkl_edit.setText(path)

    def _browse_npz(self) -> None:
        start = os.path.dirname(self._npz_edit.text()) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Spectrum File", start,
            "NumPy Files (*.npz);;All Files (*)",
        )
        if path:
            self._npz_edit.setText(path)

    def _browse_base_dir(self) -> None:
        start = self._base_dir_edit.text() or ""
        d = QFileDialog.getExistingDirectory(self, "Select Base Directory", start)
        if d:
            self._base_dir_edit.setText(d)

    def _on_recent_selected(self, index: int) -> None:
        if index <= 0:
            return
        text = self._recent_combo.currentText()
        if not text or text.startswith("—"):
            return
        # text is "name — path"
        if " — " in text:
            name, base = text.split(" — ", 1)
            self._name_edit.setText(name.strip())
            self._base_dir_edit.setText(base.strip())

    def _update_resolved_display(self) -> None:
        resolved = self._resolved_path()
        if resolved:
            self._resolved_label.setText(resolved)
        else:
            self._resolved_label.setText("(set project name and directory)")

    def _on_accept(self) -> None:
        # Validate data source
        if not self._from_memory_cb.isChecked():
            pkl = self._pkl_edit.text().strip()
            if not pkl or not os.path.isfile(pkl):
                QMessageBox.warning(
                    self, "Missing Data",
                    "Please select a valid session file (.pkl or .dc_state).",
                )
                return

        # Validate project directory
        name = self._name_edit.text().strip()
        base = self._base_dir_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing Name",
                "Please enter a project name.",
            )
            return
        if not base or not os.path.isdir(base):
            QMessageBox.warning(
                self, "Missing Directory",
                "Please select a valid base directory.",
            )
            return

        # Create project folder structure
        project = self._resolved_path()
        for sub in ("render", "sheets", "exports", "session"):
            os.makedirs(os.path.join(project, sub), exist_ok=True)

        # Save to QSettings
        self._save_to_settings()
        self.accept()

    # ── Helpers ────────────────────────────────────────────────────

    def _resolved_path(self) -> str:
        name = self._name_edit.text().strip()
        base = self._base_dir_edit.text().strip()
        if name and base:
            return os.path.join(base, name)
        return ""

    def _update_memory_summary(self) -> None:
        if not self._has_controller:
            self._memory_summary.setText(
                "No DC Cut session active. Please load a session file below."
            )
            return
        ctrl = self._controller
        try:
            n = len(ctrl.velocity_arrays)
            labels = list(ctrl.offset_labels[:n]) if hasattr(ctrl, 'offset_labels') else []
            has_spec = False
            if hasattr(ctrl, '_layers_model') and ctrl._layers_model:
                for layer in ctrl._layers_model.layers[:n]:
                    if getattr(layer, 'spectrum_data', None) is not None:
                        has_spec = True
                        break
            parts = [f"{n} offset(s)"]
            if labels:
                shown = labels[:4]
                if len(labels) > 4:
                    shown.append(f"… +{len(labels) - 4} more")
                parts.append(", ".join(shown))
            if has_spec:
                parts.append("spectrum available")
            self._memory_summary.setText("  •  ".join(parts))
        except Exception:
            self._memory_summary.setText("Controller data available")

    def _restore_from_settings(self) -> None:
        s = self._qsettings
        # Restore last values
        last_base = s.value(_KEY_LAST_PROJECT_DIR, "")
        last_name = s.value(_KEY_LAST_PROJECT_NAME, "")
        last_pkl = s.value(_KEY_LAST_PKL, "")
        last_npz = s.value(_KEY_LAST_NPZ, "")

        if last_base:
            self._base_dir_edit.setText(str(last_base))
        if last_name:
            self._name_edit.setText(str(last_name))
        if last_pkl:
            self._pkl_edit.setText(str(last_pkl))
        if last_npz:
            self._npz_edit.setText(str(last_npz))

        # Populate recent projects
        recent = s.value(_KEY_RECENT_PROJECTS, [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif recent is None:
            recent = []
        for entry in recent[:_MAX_RECENT]:
            if isinstance(entry, str) and entry:
                self._recent_combo.addItem(entry)

        self._update_resolved_display()

    def _save_to_settings(self) -> None:
        s = self._qsettings
        name = self._name_edit.text().strip()
        base = self._base_dir_edit.text().strip()

        s.setValue(_KEY_LAST_PROJECT_DIR, base)
        s.setValue(_KEY_LAST_PROJECT_NAME, name)
        if not self._from_memory_cb.isChecked():
            s.setValue(_KEY_LAST_PKL, self._pkl_edit.text().strip())
            s.setValue(_KEY_LAST_NPZ, self._npz_edit.text().strip())

        # Update recent projects list
        entry = f"{name} — {base}"
        recent = s.value(_KEY_RECENT_PROJECTS, [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif recent is None:
            recent = []
        # Remove duplicate and prepend
        recent = [r for r in recent if r != entry]
        recent.insert(0, entry)
        s.setValue(_KEY_RECENT_PROJECTS, recent[:_MAX_RECENT])
