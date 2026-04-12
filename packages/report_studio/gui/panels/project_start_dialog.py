"""Project setup dialog for Report Studio v2.6.

Shown on startup — lets the user:
  1. Choose data source (DC Cut controller or files)
  2. Create a new project or open an existing one
  3. Pick from recent projects

QSettings remembers last-used paths and recent projects.
"""
from __future__ import annotations

import os
from typing import Optional

from ...qt_compat import (
    QtWidgets, QtCore,
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
    from PySide6.QtCore import QSettings

SETTINGS_ORG = "DCCut"
SETTINGS_APP = "ReportStudio"
KEY_LAST_PROJECT_DIR = "project/last_base_dir"
KEY_LAST_PROJECT_NAME = "project/last_name"
KEY_RECENT_PROJECTS = "project/recent"
KEY_LAST_PKL = "data/last_pkl"
KEY_LAST_NPZ = "data/last_npz"
MAX_RECENT = 8


def get_qsettings() -> QSettings:
    """Return a QSettings instance for Report Studio."""
    return QSettings(SETTINGS_ORG, SETTINGS_APP)


class ProjectStartDialog(QDialog):
    """Startup dialog: data source + project directory."""

    def __init__(self, controller=None, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._has_controller = controller is not None
        self._qs = get_qsettings()

        # Result state
        self._open_existing_path: str = ""
        self._suppress_edit_clear: bool = False

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
        if self._open_existing_path:
            return self._open_existing_path
        return self._resolved_path()

    @property
    def project_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def is_open_existing(self) -> bool:
        return bool(self._open_existing_path)

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

        self._memory_summary = QLabel()
        self._memory_summary.setStyleSheet("color: #666; margin-left: 20px;")
        data_layout.addWidget(self._memory_summary)
        self._update_memory_summary()

        # File pickers
        self._file_form = QWidget()
        file_layout = QFormLayout(self._file_form)
        file_layout.setContentsMargins(20, 4, 0, 0)

        pkl_row = QHBoxLayout()
        self._pkl_edit = QLineEdit()
        self._pkl_edit.setPlaceholderText("Path to .pkl session file")
        pkl_row.addWidget(self._pkl_edit, stretch=1)
        pkl_browse = QPushButton("Browse…")
        pkl_browse.setFixedWidth(80)
        pkl_browse.clicked.connect(self._browse_pkl)
        pkl_row.addWidget(pkl_browse)
        file_layout.addRow("Session file:", pkl_row)

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
        proj_group = QGroupBox("Project")
        proj_layout = QVBoxLayout(proj_group)

        # Open existing project button
        open_row = QHBoxLayout()
        self._btn_open_existing = QPushButton("Open Existing Project…")
        self._btn_open_existing.clicked.connect(self._browse_open_existing)
        open_row.addWidget(self._btn_open_existing)
        self._open_path_label = QLabel("")
        self._open_path_label.setStyleSheet("color: #0078d4;")
        open_row.addWidget(self._open_path_label, stretch=1)
        proj_layout.addLayout(open_row)

        # Recent projects
        recent_row = QHBoxLayout()
        recent_label = QLabel("Recent:")
        recent_row.addWidget(recent_label)
        self._recent_combo = QComboBox()
        self._recent_combo.setEditable(False)
        self._recent_combo.addItem("— Select Recent Project —")
        self._recent_combo.currentIndexChanged.connect(self._on_recent_selected)
        recent_row.addWidget(self._recent_combo, stretch=1)
        proj_layout.addLayout(recent_row)

        # Separator
        sep = QLabel("— or create a new project —")
        sep.setStyleSheet("color: #888; margin: 4px 0;")
        sep.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        proj_layout.addWidget(sep)

        # New project fields
        new_form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Site_A_Report")
        self._name_edit.textChanged.connect(self._on_new_project_edited)
        new_form.addRow("Project name:", self._name_edit)

        base_row = QHBoxLayout()
        self._base_dir_edit = QLineEdit()
        self._base_dir_edit.setPlaceholderText("Select base directory…")
        self._base_dir_edit.textChanged.connect(self._on_new_project_edited)
        base_row.addWidget(self._base_dir_edit, stretch=1)
        base_browse = QPushButton("Browse…")
        base_browse.setFixedWidth(80)
        base_browse.clicked.connect(self._browse_base_dir)
        base_row.addWidget(base_browse)
        new_form.addRow("Base directory:", base_row)

        self._resolved_label = QLabel()
        self._resolved_label.setStyleSheet(
            "color: #0078d4; font-weight: bold; padding: 4px;"
        )
        new_form.addRow("Project path:", self._resolved_label)

        proj_layout.addLayout(new_form)
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
            "Pickle Files (*.pkl);;All Files (*)",
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

    def _browse_open_existing(self) -> None:
        """Browse for an existing project directory (contains project.json)."""
        start = self._qs.value(KEY_LAST_PROJECT_DIR, "") or ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", str(start),
        )
        if not d:
            return
        pj = os.path.join(d, "project.json")
        if not os.path.isfile(pj):
            QMessageBox.warning(
                self, "Not a Project",
                f"No project.json found in:\n{d}\n\n"
                "Please select a directory containing a Report Studio project.",
            )
            return
        self._open_existing_path = d
        self._open_path_label.setText(d)
        # Clear new-project fields to avoid confusion
        self._name_edit.clear()
        self._base_dir_edit.clear()
        self._resolved_label.setText("")

    def _on_recent_selected(self, index: int) -> None:
        if index <= 0:
            return
        text = self._recent_combo.currentText()
        if not text or text.startswith("—"):
            return
        # Recent entries stored as absolute project paths
        self._suppress_edit_clear = True
        try:
            if os.path.isdir(text):
                pj = os.path.join(text, "project.json")
                if os.path.isfile(pj):
                    self._open_existing_path = text
                    self._open_path_label.setText(text)
                    self._name_edit.clear()
                    self._base_dir_edit.clear()
                    self._resolved_label.setText("")
                    return
            # Fallback: try "name — base" format
            if " — " in text:
                name, base = text.split(" — ", 1)
                self._name_edit.setText(name.strip())
                self._base_dir_edit.setText(base.strip())
                self._open_existing_path = ""
                self._open_path_label.setText("")
        finally:
            self._suppress_edit_clear = False

    def _on_new_project_edited(self) -> None:
        """User typed in new-project fields — clear open-existing selection."""
        if self._suppress_edit_clear:
            return
        if self._name_edit.text().strip() or self._base_dir_edit.text().strip():
            self._open_existing_path = ""
            self._open_path_label.setText("")
        self._update_resolved_display()

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
                    "Please select a valid session file (.pkl).",
                )
                return

        # For open-existing, just validate the path
        if self._open_existing_path:
            pj = os.path.join(self._open_existing_path, "project.json")
            if not os.path.isfile(pj):
                QMessageBox.warning(
                    self, "Invalid Project",
                    f"No project.json found in:\n{self._open_existing_path}",
                )
                return
            self._save_to_settings()
            self.accept()
            return

        # Validate new project directory
        name = self._name_edit.text().strip()
        base = self._base_dir_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name",
                                "Please enter a project name.")
            return
        if not base or not os.path.isdir(base):
            QMessageBox.warning(self, "Missing Directory",
                                "Please select a valid base directory.")
            return

        # Create project folder structure
        project = self._resolved_path()
        for sub in ("sheets", "session"):
            os.makedirs(os.path.join(project, sub), exist_ok=True)

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
                "No DC Cut session active. Load session file below."
            )
            return
        ctrl = self._controller
        try:
            n = len(ctrl.velocity_arrays)
            labels = list(ctrl.offset_labels[:n]) if hasattr(ctrl, 'offset_labels') else []
            has_spec = False
            if hasattr(ctrl, '_layers_model') and ctrl._layers_model:
                for layer in ctrl._layers_model.layers[:n]:
                    if getattr(layer, 'spectrum_data', None):
                        has_spec = True
                        break
            parts = [f"{n} offset(s)"]
            if labels:
                shown = labels[:4]
                if len(labels) > 4:
                    shown.append(f"… +{len(labels) - 4} more")
                parts.append(", ".join(str(s) for s in shown))
            if has_spec:
                parts.append("spectrum available")
            self._memory_summary.setText("  •  ".join(parts))
        except Exception:
            self._memory_summary.setText("Controller data available")

    def _restore_from_settings(self) -> None:
        s = self._qs
        last_base = s.value(KEY_LAST_PROJECT_DIR, "")
        last_name = s.value(KEY_LAST_PROJECT_NAME, "")
        last_pkl = s.value(KEY_LAST_PKL, "")
        last_npz = s.value(KEY_LAST_NPZ, "")

        self._suppress_edit_clear = True
        try:
            if last_base:
                self._base_dir_edit.setText(str(last_base))
            if last_name:
                self._name_edit.setText(str(last_name))
            if last_pkl:
                self._pkl_edit.setText(str(last_pkl))
            if last_npz:
                self._npz_edit.setText(str(last_npz))
        finally:
            self._suppress_edit_clear = False

        # Populate recent projects
        recent = s.value(KEY_RECENT_PROJECTS, [])
        if isinstance(recent, str):
            recent = [recent] if recent else []
        elif recent is None:
            recent = []
        for entry in recent[:MAX_RECENT]:
            if isinstance(entry, str) and entry:
                self._recent_combo.addItem(entry)

        self._update_resolved_display()

    def _save_to_settings(self) -> None:
        s = self._qs
        if self._open_existing_path:
            proj = self._open_existing_path
        else:
            proj = self._resolved_path()
            s.setValue(KEY_LAST_PROJECT_DIR, self._base_dir_edit.text().strip())
            s.setValue(KEY_LAST_PROJECT_NAME, self._name_edit.text().strip())

        # Save file paths
        if not self._from_memory_cb.isChecked():
            s.setValue(KEY_LAST_PKL, self._pkl_edit.text().strip())
            s.setValue(KEY_LAST_NPZ, self._npz_edit.text().strip())

        # Update recent projects (store absolute paths)
        if proj:
            recent = s.value(KEY_RECENT_PROJECTS, [])
            if isinstance(recent, str):
                recent = [recent] if recent else []
            elif recent is None:
                recent = []
            recent = [r for r in recent if r != proj]
            recent.insert(0, proj)
            s.setValue(KEY_RECENT_PROJECTS, recent[:MAX_RECENT])


def save_data_paths(pkl_path: str = "", npz_path: str = "") -> None:
    """Persist PKL/NPZ paths to QSettings (called after AddDataDialog)."""
    s = get_qsettings()
    if pkl_path:
        s.setValue(KEY_LAST_PKL, pkl_path)
    if npz_path:
        s.setValue(KEY_LAST_NPZ, npz_path)


def load_data_paths() -> tuple[str, str]:
    """Retrieve last-used PKL/NPZ paths from QSettings."""
    s = get_qsettings()
    pkl = str(s.value(KEY_LAST_PKL, "") or "")
    npz = str(s.value(KEY_LAST_NPZ, "") or "")
    return pkl, npz


def add_recent_project(project_dir: str) -> None:
    """Add a project to the recent list."""
    s = get_qsettings()
    recent = s.value(KEY_RECENT_PROJECTS, [])
    if isinstance(recent, str):
        recent = [recent] if recent else []
    elif recent is None:
        recent = []
    recent = [r for r in recent if r != project_dir]
    recent.insert(0, project_dir)
    s.setValue(KEY_RECENT_PROJECTS, recent[:MAX_RECENT])
