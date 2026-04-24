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
        # Cached bundle summary (or None when user hasn't picked a
        # figure file yet). Populated by ``_on_bundle_picked`` and
        # read back in ``_on_accept`` + ``plugin_kwargs``.
        self._bundle_summary: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._restore_default_paths()
        self._rebuild_plugin_fields()
        self._update_bundle_row_visibility()

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
            lambda _i: (self._rebuild_plugin_fields(),
                        self._update_bundle_row_visibility())
        )
        self._body_layout.addWidget(type_group)

        # ── Figure file (single self-describing .pkl bundle) ───────
        # Replaces the old 4-file mental model: the bundle's ``_kind``
        # tag tells the dialog which figure type + which offsets the
        # user exported from DC Cut, and the preview card renders the
        # metadata so the user knows what they're loading before OK.
        # The linked-data rows (PKL + NPZ) auto-fill from the bundle's
        # ``source`` block and stay collapsed unless the user needs to
        # override them.
        self._file_group = QtWidgets.QGroupBox("Data Files")
        fg_layout = QtWidgets.QVBoxLayout(self._file_group)
        fg_layout.setContentsMargins(8, 6, 8, 6)
        fg_layout.setSpacing(6)

        # Primary "Figure file" row.
        self._bundle_row_widget = QtWidgets.QWidget()
        bundle_form = QtWidgets.QFormLayout(self._bundle_row_widget)
        bundle_form.setContentsMargins(0, 0, 0, 0)
        bundle_picker = QtWidgets.QHBoxLayout()
        self._bundle_edit = QtWidgets.QLineEdit()
        self._bundle_edit.setPlaceholderText(
            "Select figure bundle (.pkl) exported from DC Cut…"
        )
        self._bundle_edit.setToolTip(
            "Self-describing figure file written by "
            "DC Cut → NF Eval → \"Save Figure ▾\".\n"
            "One .pkl per figure type; the dialog reads its "
            "metadata + auto-fills the linked State/Spectrum files."
        )
        # When the path is edited by hand, re-parse on editingFinished
        # rather than every keystroke.
        self._bundle_edit.editingFinished.connect(
            lambda: self._on_bundle_picked(self._bundle_edit.text().strip())
        )
        bundle_btn = QtWidgets.QPushButton("Browse…")
        bundle_btn.clicked.connect(self._browse_bundle)
        bundle_picker.addWidget(self._bundle_edit, stretch=1)
        bundle_picker.addWidget(bundle_btn)
        bundle_form.addRow("Figure file (.pkl):", bundle_picker)
        fg_layout.addWidget(self._bundle_row_widget)

        # Preview card — a compact summary that appears only after a
        # valid bundle is picked. Keeps the header label + offsets
        # QTableWidget so the user can eyeball what got exported.
        self._bundle_preview = QtWidgets.QFrame()
        self._bundle_preview.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self._bundle_preview.setVisible(False)
        pv_layout = QtWidgets.QVBoxLayout(self._bundle_preview)
        pv_layout.setContentsMargins(8, 6, 8, 6)
        pv_layout.setSpacing(4)
        self._bundle_header = QtWidgets.QLabel("")
        self._bundle_header.setWordWrap(True)
        self._bundle_header.setStyleSheet("font-weight: 600;")
        pv_layout.addWidget(self._bundle_header)
        self._bundle_offsets_table = QtWidgets.QTableWidget(0, 4)
        self._bundle_offsets_table.setHorizontalHeaderLabels(
            ["Offset", "x̄ (m)", "λ_max (m)", "n_contam"]
        )
        self._bundle_offsets_table.verticalHeader().setVisible(False)
        self._bundle_offsets_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.NoSelection
        )
        self._bundle_offsets_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        hh = self._bundle_offsets_table.horizontalHeader()
        try:
            hh.setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        except AttributeError:
            hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self._bundle_offsets_table.setMaximumHeight(180)
        pv_layout.addWidget(self._bundle_offsets_table)
        fg_layout.addWidget(self._bundle_preview)

        # Linked data (advanced) — PKL + NPZ, auto-filled + collapsed
        # when a bundle is picked, expanded + editable for the
        # source-offset / average-curve figures that don't ship with
        # a bundle.
        self._linked_section = CollapsibleSection(
            "Linked data (advanced)", expanded=True,
        )
        linked_form = QtWidgets.QFormLayout()
        linked_form.setContentsMargins(0, 0, 0, 0)
        pkl_row = QtWidgets.QHBoxLayout()
        self._pkl_edit = QtWidgets.QLineEdit()
        self._pkl_edit.setPlaceholderText("Select .pkl state file…")
        pkl_btn = QtWidgets.QPushButton("Browse…")
        pkl_btn.clicked.connect(self._browse_pkl)
        pkl_row.addWidget(self._pkl_edit, stretch=1)
        pkl_row.addWidget(pkl_btn)
        linked_form.addRow("State file (.pkl):", pkl_row)

        npz_row = QtWidgets.QHBoxLayout()
        self._npz_edit = QtWidgets.QLineEdit()
        self._npz_edit.setPlaceholderText("Optional: .npz spectrum file…")
        npz_btn = QtWidgets.QPushButton("Browse…")
        npz_btn.clicked.connect(self._browse_npz)
        npz_row.addWidget(self._npz_edit, stretch=1)
        npz_row.addWidget(npz_btn)
        linked_form.addRow("Spectrum (.npz):", npz_row)

        linked_wrap = QtWidgets.QWidget()
        linked_wrap.setLayout(linked_form)
        self._linked_section.form.addRow(linked_wrap)
        fg_layout.addWidget(self._linked_section)

        self._body_layout.addWidget(self._file_group)

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
        from ...core.plugins import nacd_zones as _nz  # noqa: F401
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

    def _browse_bundle(self):
        """Pick a figure-bundle .pkl exported from DC Cut."""
        import os
        start = (
            os.path.dirname(self._bundle_edit.text())
            or os.path.dirname(self._pkl_edit.text())
            or ""
        )
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Figure File", start,
            "Pickle Files (*.pkl);;All Files (*)",
        )
        if path:
            self._bundle_edit.setText(path)
            self._on_bundle_picked(path)

    # ── Bundle preview + auto-fill ─────────────────────────────────────

    def _on_bundle_picked(self, path: str) -> None:
        """Validate + preview a bundle, auto-fill PKL/NPZ.

        Called from the "Browse…" button, ``editingFinished`` on the
        line edit, and directly from tests that poke ``_bundle_edit``
        programmatically. Always safe to call with an empty path —
        that just clears the preview.
        """
        self._bundle_summary = None
        self._bundle_preview.setVisible(False)
        self._bundle_offsets_table.setRowCount(0)

        if not path:
            return

        try:
            from ...io.figure_bundle import bundle_summary, detect_bundle_kind
        except Exception:
            return

        summary = bundle_summary(path)
        if summary is None:
            self._bundle_header.setText(
                "<i>Not a recognised figure bundle.</i>"
            )
            self._bundle_preview.setVisible(True)
            return

        # Auto-switch the type combo when the bundle's kind doesn't
        # match the currently-selected figure type. The detected
        # ``type_id`` always wins — the bundle is the ground truth.
        detected_tid = summary.get("type_id") or detect_bundle_kind(path)
        if detected_tid and detected_tid != self.selected_type_id:
            idx = self._type_combo.findData(detected_tid)
            if idx >= 0:
                self._type_combo.blockSignals(True)
                self._type_combo.setCurrentIndex(idx)
                self._type_combo.blockSignals(False)
                # Manually re-run the slot's side effects since we
                # suppressed the signal above.
                self._rebuild_plugin_fields()
                self._update_bundle_row_visibility()

        self._bundle_summary = summary
        self._render_preview(summary)

        # Auto-fill linked paths from the bundle's source block.
        src = summary.get("source") or {}
        state_pkl = src.get("state_pkl") or ""
        spectrum_npz = src.get("spectrum_npz") or ""
        if state_pkl:
            self._pkl_edit.setText(state_pkl)
            self._load_offset_list(state_pkl)
        if spectrum_npz:
            self._npz_edit.setText(spectrum_npz)

        # Collapse linked-data section when fully auto-filled — the
        # user can always expand if they need to override.
        if state_pkl:
            try:
                self._linked_section.set_expanded(False)
            except Exception:
                pass

        # Populate the offset checklist from the bundle's offsets.
        self._populate_offsets_from_bundle(summary)

    def _render_preview(self, summary: Dict[str, Any]) -> None:
        """Fill the preview card widgets from ``summary``."""
        figure_type = summary.get("figure_type", "(unknown)")
        n_off = int(summary.get("n_offsets", 0))
        saved_at = summary.get("saved_at", "")
        pieces = [f"<b>{figure_type}</b>", f"{n_off} offset(s)"]
        if saved_at:
            pieces.append(f"saved {saved_at}")
        self._bundle_header.setText(" • ".join(pieces))

        offsets = summary.get("offsets") or []
        self._bundle_offsets_table.setRowCount(len(offsets))
        for row, off in enumerate(offsets):
            def _fmt(key, default="—", fmt="{:.2f}"):
                v = off.get(key)
                if v is None:
                    return default
                try:
                    return fmt.format(float(v))
                except (TypeError, ValueError):
                    return str(v)

            cells = [
                str(off.get("label", f"#{row+1}")),
                _fmt("x_bar"),
                _fmt("lambda_max"),
                str(int(off.get("n_contaminated", 0))),
            ]
            for col, text in enumerate(cells):
                self._bundle_offsets_table.setItem(
                    row, col, QtWidgets.QTableWidgetItem(text)
                )
        self._bundle_preview.setVisible(True)

    def _populate_offsets_from_bundle(self, summary: Dict[str, Any]) -> None:
        """Use the bundle's offset list as the checklist source."""
        offsets = summary.get("offsets") or []
        if not offsets:
            return
        labels = [str(o.get("label", "")) for o in offsets if o.get("label") is not None]
        if not labels:
            return
        self._offset_list.clear()
        self._offset_labels = labels
        for label in labels:
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(
                item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Checked)
            self._offset_list.addItem(item)
        self._lbl_status.setText(
            f"{len(labels)} offset(s) from bundle — all selected."
        )

    def _update_bundle_row_visibility(self) -> None:
        """Hide figure-file row for types that don't ship a bundle."""
        tid = self.selected_type_id
        # Only NF-derived figures currently have bundle writers
        # registered; the others use the legacy PKL+NPZ path only.
        try:
            from ...io.figure_bundle import FIGURE_BUNDLE_REGISTRY
            has_bundle = tid in FIGURE_BUNDLE_REGISTRY
        except Exception:
            has_bundle = False
        self._bundle_row_widget.setVisible(has_bundle)
        if not has_bundle:
            self._bundle_preview.setVisible(False)
            # Expand linked data for non-bundle figures so the user
            # sees what they need to fill in.
            try:
                self._linked_section.set_expanded(True)
            except Exception:
                pass

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
    def figure_bundle_path(self) -> str:
        """Path to the self-describing figure bundle, or ``""``."""
        return self._bundle_edit.text().strip()

    @property
    def nf_sidecar_path(self) -> str:
        """Legacy alias — the dialog no longer exposes a separate sidecar.

        Kept so callers that haven't been migrated to
        :attr:`figure_bundle_path` still get a defined attribute.
        Always ``""`` in the new UI; project-load paths still read
        the legacy ``SheetState.nf_sidecar_path`` when set.
        """
        return ""

    @property
    def nacd_bundle_path(self) -> str:
        """Legacy alias — see :attr:`nf_sidecar_path`.

        For NACD-Zone figures, callers should now use
        :attr:`figure_bundle_path`; this shim stays so older
        main-window code keeps compiling during the migration.
        """
        # When the detected bundle IS a NACD-zones bundle we return
        # it here too, so legacy plugin signatures keep working until
        # F4 lands the dispatcher update.
        summary = self._bundle_summary or {}
        if summary.get("type_id") == "nacd_zones":
            return self.figure_bundle_path
        return ""

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
