"""
Add-data dialog — per-subplot data addition.

Replaces the old ProjectDialog for adding data to a specific subplot.
The user selects:
  1. Figure type (from registry — currently just "Source Offset Curves")
  2. PKL file + optional NPZ file
  3. Which offsets to include (checklist)
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
    DialogAccepted, DialogRejected,
    Checked, Unchecked,
)
from .collapsible import CollapsibleSection


class AddDataDialog(QtWidgets.QDialog):
    """Dialog for adding data to a specific subplot."""

    def __init__(self, parent=None, subplot_key: str = "main"):
        super().__init__(parent)
        self.setWindowTitle(f"Add Data — {subplot_key}")
        self.setMinimumWidth(640)
        self.setMinimumHeight(520)

        self._subplot_key = subplot_key
        self._pkl_path = ""
        self._npz_path = ""
        self._offset_labels: List[str] = []
        self._selected_type_id = "source_offset"
        self._plugin_value_getters: Dict[str, Callable[[], Any]] = {}

        self._build_ui()
        self._restore_default_paths()
        self._rebuild_plugin_fields()

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        self._body = QtWidgets.QWidget()
        self._body_layout = QtWidgets.QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(8)

        body_scroll = QtWidgets.QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        body_scroll.setWidget(self._body)
        layout.addWidget(body_scroll)

        # Figure type selector
        type_group = QtWidgets.QGroupBox("Figure Type")
        type_layout = QtWidgets.QHBoxLayout(type_group)
        self._type_combo = QtWidgets.QComboBox()
        self._populate_type_combo()
        type_layout.addWidget(self._type_combo)
        self._type_combo.currentIndexChanged.connect(
            lambda _i: self._rebuild_plugin_fields()
        )
        self._body_layout.addWidget(type_group)

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

        nf_row = QtWidgets.QHBoxLayout()
        self._nf_edit = QtWidgets.QLineEdit()
        self._nf_edit.setPlaceholderText(
            "Optional: NF evaluation sidecar exported from DC Cut..."
        )
        self._nf_edit.setToolTip(
            "Third file in the DC Cut 3-file bundle: overrides the NF "
            "analysis embedded in the PKL when set."
        )
        nf_btn = QtWidgets.QPushButton("Browse...")
        nf_btn.clicked.connect(self._browse_nf_sidecar)
        nf_row.addWidget(self._nf_edit, stretch=1)
        nf_row.addWidget(nf_btn)
        file_layout.addRow("NF eval (.json):", nf_row)

        self._body_layout.addWidget(file_group)

        # Offset checklist (collapsible)
        self._offset_section = CollapsibleSection("Select Offsets", expanded=True)
        offset_layout = QtWidgets.QVBoxLayout()
        offset_layout.setContentsMargins(0, 0, 0, 0)

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

        off_wrap = QtWidgets.QWidget()
        off_wrap.setLayout(offset_layout)
        self._offset_section.form.addRow(off_wrap)
        self._body_layout.addWidget(self._offset_section)

        self._plugin_outer = QtWidgets.QWidget()
        self._plugin_vbox = QtWidgets.QVBoxLayout(self._plugin_outer)
        self._plugin_vbox.setContentsMargins(0, 0, 0, 0)
        self._plugin_vbox.setSpacing(4)
        self._body_layout.addWidget(self._plugin_outer)
        # Pool any leftover viewport space at the bottom rather than
        # inflating any one section. Without this stretch, collapsing a
        # CollapsibleSection leaves the freed area empty because the parent
        # layout had already allocated the height to that section.
        self._body_layout.addStretch(1)

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
        from ...core.plugins import average_curve as _ac  # noqa: F401
        from ...core.plugins import nacd_only as _nf  # noqa: F401
        from ...core.figure_types import registry

        for plugin in registry.all_types():
            self._type_combo.addItem(plugin.display_name, plugin.type_id)

    def _rebuild_plugin_fields(self) -> None:
        """Dynamic rows from the selected figure type's ``settings_fields()``."""
        self._plugin_value_getters.clear()
        while self._plugin_vbox.count():
            item = self._plugin_vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        from ...core.figure_types import registry

        tid = self.selected_type_id
        plugin = registry.get(tid)
        if not plugin:
            self._plugin_outer.setVisible(False)
            return

        fields = []
        try:
            fields = plugin.settings_fields()
        except Exception:
            fields = []

        if not fields:
            self._plugin_outer.setVisible(False)
            return

        self._plugin_outer.setVisible(True)
        groups: Dict[str, list] = defaultdict(list)
        for spec in fields:
            g = spec.get("group") or "Options"
            groups[g].append(spec)

        preferred_order = ["Layout", "Display", "Recompute / array geometry", "Options"]
        ordered_names = [n for n in preferred_order if n in groups]
        ordered_names += sorted(k for k in groups if k not in preferred_order)

        try:
            growth_policy = QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            wrap_policy = QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows
            label_alignment = QtCore.Qt.AlignmentFlag.AlignRight
        except AttributeError:
            growth_policy = QtWidgets.QFormLayout.ExpandingFieldsGrow
            wrap_policy = QtWidgets.QFormLayout.WrapLongRows
            label_alignment = QtCore.Qt.AlignRight

        for gi, gname in enumerate(ordered_names):
            sec = CollapsibleSection(
                f"Figure options — {gname}",
                expanded=(gname in ("Layout", "Display")),
            )
            form = sec.form
            form.setFieldGrowthPolicy(growth_policy)
            form.setRowWrapPolicy(wrap_policy)
            form.setLabelAlignment(label_alignment)
            for spec in groups[gname]:
                key = spec.get("key", "")
                label = spec.get("label", key)
                typ = spec.get("type", "str")
                default = spec.get("default")

                if typ == "combo":
                    w = QtWidgets.QComboBox()
                    w.setMinimumWidth(260)
                    for opt in spec.get("options") or []:
                        w.addItem(str(opt), opt)
                    idx = w.findData(default)
                    if idx < 0:
                        idx = 0
                    w.setCurrentIndex(idx)
                    self._plugin_value_getters[key] = lambda ww=w: ww.currentData()
                    form.addRow(label, w)
                elif typ == "int":
                    w = QtWidgets.QSpinBox()
                    w.setMinimumWidth(260)
                    w.setRange(int(spec.get("min", -10**6)), int(spec.get("max", 10**6)))
                    w.setValue(int(default if default is not None else 0))
                    self._plugin_value_getters[key] = lambda ww=w: int(ww.value())
                    form.addRow(label, w)
                elif typ == "float":
                    w = QtWidgets.QDoubleSpinBox()
                    w.setMinimumWidth(260)
                    w.setDecimals(3)
                    w.setRange(float(spec.get("min", -1e9)), float(spec.get("max", 1e9)))
                    v = float(default if default is not None else 0.0)
                    w.setValue(v)
                    self._plugin_value_getters[key] = lambda ww=w: float(ww.value())
                    form.addRow(label, w)
                elif typ == "bool":
                    w = QtWidgets.QCheckBox(label)
                    w.setChecked(bool(default))
                    self._plugin_value_getters[key] = lambda ww=w: bool(ww.isChecked())
                    form.addRow(w)
                else:
                    w = QtWidgets.QLineEdit(str(default if default is not None else ""))
                    self._plugin_value_getters[key] = lambda ww=w: ww.text().strip()
                    form.addRow(label, w)
            self._plugin_vbox.addWidget(sec)

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

    def _browse_nf_sidecar(self):
        """Pick the NF evaluation sidecar JSON (3rd file in the bundle)."""
        import os
        start = (
            os.path.dirname(self._nf_edit.text())
            or os.path.dirname(self._pkl_edit.text())
            or ""
        )
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select NF Evaluation Sidecar", start,
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self._nf_edit.setText(path)

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
    def nf_sidecar_path(self) -> str:
        return self._nf_edit.text().strip()

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

    @property
    def plugin_kwargs(self) -> Dict[str, Any]:
        return {k: fn() for k, fn in self._plugin_value_getters.items()}
