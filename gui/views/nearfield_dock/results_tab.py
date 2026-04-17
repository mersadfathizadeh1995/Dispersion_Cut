"""Tab 4: Results & Export.

Owns the batch summary, the per-offset inspect combo, the points
table, auto-select / apply / cancel actions, export buttons, and
the NACD vs V_R scatter window launcher.
"""
from __future__ import annotations

import numpy as np

from dc_cut.gui.widgets.collapsible_section import CollapsibleSection

from .constants import (
    QtGui,
    QtWidgets,
    _Checked,
    _ItemIsEnabled,
    _ItemIsEditable,
    _ItemIsUserCheckable,
    _Unchecked,
)


class ResultsTab(QtWidgets.QWidget):
    """Results & Export page of the NF Evaluation dock."""

    def __init__(self, dock) -> None:
        super().__init__()
        self.dock = dock
        self._build()

    # ================================================================
    #  UI build
    # ================================================================
    def _build(self) -> None:
        scroll_layout = QtWidgets.QVBoxLayout(self)
        scroll_layout.setContentsMargins(0, 0, 0, 0)

        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        scroll_layout.addWidget(scroll)

        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(6, 6, 6, 6)

        # ── Batch Summary (collapsible) ──
        batch_sec = CollapsibleSection("Batch Summary", initially_expanded=True)
        self.batch_table = QtWidgets.QTableWidget()
        self.batch_table.setColumnCount(7)
        self.batch_table.setHorizontalHeaderLabels([
            "Offset", "x̄ (m)", "λ_max (m)", "Onset λ (m)",
            "Clean %", "Marginal %", "Contam %",
        ])
        try:
            self.batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self.batch_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        self.batch_table.setMaximumHeight(200)
        batch_sec.add_widget(self.batch_table)
        layout.addWidget(batch_sec)

        # ── Inspect Offset (collapsible) ──
        # The points table, auto-select filter and Delete/Cancel
        # actions all belong to this section, so they collapse and
        # expand together with the header.
        inspect_sec = CollapsibleSection("Inspect Offset", initially_expanded=True)
        inspect_form = QtWidgets.QFormLayout()

        self.inspect_combo = QtWidgets.QComboBox()
        self.inspect_combo.currentIndexChanged.connect(self.on_inspect_changed)
        inspect_form.addRow("Offset:", self.inspect_combo)

        self.inspect_summary = QtWidgets.QLabel("")
        inspect_form.addRow(self.inspect_summary)

        inspect_sec.add_layout(inspect_form)

        # Points table (inside the collapsible)
        self.points_table = QtWidgets.QTableWidget()
        self.points_table.setColumnCount(7)
        self.points_table.setHorizontalHeaderLabels(
            ["f (Hz)", "V (m/s)", "λ (m)", "NACD", "V_R", "Severity", "☑"]
        )
        try:
            self.points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Stretch
            )
        except AttributeError:
            self.points_table.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.ResizeMode.Stretch
            )
        try:
            self.points_table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectRows
            )
        except AttributeError:
            self.points_table.setSelectionBehavior(
                QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
            )
        self.points_table.setMinimumHeight(180)
        self.points_table.itemChanged.connect(self.on_flag_toggled)
        inspect_sec.add_widget(self.points_table)

        # Filter + actions (inside the same collapsible)
        filt_row = QtWidgets.QHBoxLayout()
        filt_row.addWidget(QtWidgets.QLabel("Auto-select:"))
        self.del_filter = QtWidgets.QComboBox()
        self.del_filter.addItems([
            "All flagged (NF ≥ marginal)",
            "Contaminated only (V_R < 0.85)",
            "NACD below threshold",
        ])
        filt_row.addWidget(self.del_filter, stretch=1)
        select_btn = QtWidgets.QPushButton("Select")
        select_btn.clicked.connect(self.on_auto_select)
        filt_row.addWidget(select_btn)
        inspect_sec.add_layout(filt_row)

        action_row = QtWidgets.QHBoxLayout()
        self.btn_apply = QtWidgets.QPushButton("Delete")
        self.btn_apply.setStyleSheet("font-weight: bold; color: #F44336;")
        self.btn_apply.clicked.connect(self.on_apply_deletions)
        action_row.addWidget(self.btn_apply)
        self.btn_cancel = QtWidgets.QPushButton("Cancel / Clear")
        self.btn_cancel.clicked.connect(self.on_cancel)
        action_row.addWidget(self.btn_cancel)
        inspect_sec.add_layout(action_row)

        layout.addWidget(inspect_sec, stretch=1)

        # ── Export ──
        export_sec = CollapsibleSection("Export", initially_expanded=False)
        export_row = QtWidgets.QHBoxLayout()
        csv_btn = QtWidgets.QPushButton("Export CSV")
        csv_btn.clicked.connect(lambda: self.on_export("csv"))
        export_row.addWidget(csv_btn)
        json_btn = QtWidgets.QPushButton("Export JSON")
        json_btn.clicked.connect(lambda: self.on_export("json"))
        export_row.addWidget(json_btn)
        export_sec.add_layout(export_row)

        export_row2 = QtWidgets.QHBoxLayout()
        scatter_btn = QtWidgets.QPushButton("NACD vs V_R Scatter")
        scatter_btn.clicked.connect(self.open_scatter_window)
        export_row2.addWidget(scatter_btn)
        npz_btn = QtWidgets.QPushButton("Export NPZ (figure data)")
        npz_btn.clicked.connect(self.on_export_npz)
        export_row2.addWidget(npz_btn)
        export_sec.add_layout(export_row2)

        layout.addWidget(export_sec)

        layout.addStretch()

    # ================================================================
    #  Population
    # ================================================================
    def populate_batch_table(self, results: list) -> None:
        self.batch_table.setRowCount(0)
        if not results:
            return
        self.batch_table.setRowCount(len(results))
        for row, entry in enumerate(results):
            lbl = entry.get("label", "?")
            if entry.get("is_reference"):
                lbl += " ★"
            ro_lam = entry.get("rolloff_wavelength", np.nan)
            vals = [
                lbl,
                f"{entry.get('x_bar', 0):.1f}",
                f"{entry.get('lambda_max', 0):.1f}",
                f"{ro_lam:.1f}" if np.isfinite(ro_lam) else "—",
                f"{entry.get('clean_pct', 0):.0f}",
                f"{100 * entry.get('n_marginal', 0) / max(entry.get('n_total', 1), 1):.0f}"
                    if 'n_marginal' in entry else "—",
                f"{entry.get('contam_pct', 0):.0f}",
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                if entry.get("contam_pct", 0) > 30:
                    item.setForeground(QtGui.QColor("#F44336"))
                elif entry.get("is_reference"):
                    item.setForeground(QtGui.QColor("#1976D2"))
                self.batch_table.setItem(row, col, item)

    def populate_inspect_combo(self, results: list) -> None:
        self.inspect_combo.blockSignals(True)
        self.inspect_combo.clear()
        for r in results:
            self.inspect_combo.addItem(r.get("label", "?"), r.get("offset_index"))
        self.inspect_combo.blockSignals(False)
        if results:
            self.inspect_combo.setCurrentIndex(0)
            self.on_inspect_changed(0)

    def on_inspect_changed(self, idx: int) -> None:
        dock = self.dock
        if idx < 0 or not dock._last_batch:
            return
        offset_idx = self.inspect_combo.itemData(idx)
        if offset_idx is None:
            return

        thr = (
            dock._nacd_tab.nacd_thr.value() if dock._last_mode == "nacd"
            else dock._reference_tab.nacd_thr.value()
        )
        label = self.inspect_combo.currentText()

        dock.eval.start_with(label, thr)
        self.populate_points_table()

    def populate_points_table(self) -> None:
        dock = self.dock
        rng = dock._active_eval_range()
        data = dock.eval.get_current_arrays(eval_range=rng)
        self.points_table.blockSignals(True)
        self.points_table.setRowCount(0)
        if not data:
            self.points_table.blockSignals(False)
            return

        idx, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        n = len(f_arr)
        self.points_table.setRowCount(n)

        colors = (
            dock._mode1_colors if dock._last_mode == "nacd"
            else dock._mode2_colors
        )
        n_flagged = 0
        for i in range(n):
            if severity is not None:
                issue = severity[i]
            else:
                issue = "contaminated" if mask[i] else "clean"

            row_color = QtGui.QColor(colors.get(issue, "#9E9E9E"))

            vals = [
                f"{f_arr[i]:.2f}",
                f"{v_arr[i]:.1f}",
                f"{w_arr[i]:.2f}",
                f"{nacd[i]:.3f}",
                f"{vr[i]:.3f}" if vr is not None and np.isfinite(vr[i]) else "—",
                issue,
            ]
            for col, txt in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(txt)
                item.setForeground(row_color)
                item.setFlags(item.flags() & ~_ItemIsEditable)
                self.points_table.setItem(i, col, item)

            flag_item = QtWidgets.QTableWidgetItem()
            flag_item.setFlags(
                flag_item.flags() | _ItemIsUserCheckable | _ItemIsEnabled
            )
            is_flagged = bool(mask[i])
            if severity is not None and severity[i] in ("contaminated", "marginal"):
                is_flagged = True
            flag_item.setCheckState(_Checked if is_flagged else _Unchecked)
            self.points_table.setItem(i, 6, flag_item)
            if is_flagged:
                n_flagged += 1

        self.points_table.blockSignals(False)
        pct = 100 * n_flagged / n if n else 0
        self.inspect_summary.setText(f"{n_flagged}/{n} flagged ({pct:.0f}%)")

    # ================================================================
    #  Flag toggles / auto-select
    # ================================================================
    def on_flag_toggled(self, changed_item) -> None:
        if changed_item is not None:
            col = changed_item.column() if hasattr(changed_item, 'column') else -1
            if col != 6:
                return

    def on_auto_select(self) -> None:
        dock = self.dock
        rng = dock._active_eval_range()
        data = dock.eval.get_current_arrays(eval_range=rng)
        if not data:
            return
        _, f_arr, v_arr, w_arr, nacd, mask, vr, severity = data
        filt = self.del_filter.currentIndex()

        self.points_table.blockSignals(True)
        for row in range(self.points_table.rowCount()):
            if row >= len(f_arr):
                break
            match = False
            if filt == 0:
                match = bool(mask[row])
                if severity is not None and severity[row] in ("contaminated", "marginal"):
                    match = True
            elif filt == 1:
                if severity is not None:
                    match = severity[row] == "contaminated"
                else:
                    match = bool(mask[row])
            elif filt == 2:
                match = bool(mask[row])

            flag_item = self.points_table.item(row, 6)
            if flag_item:
                flag_item.setCheckState(_Checked if match else _Unchecked)
        self.points_table.blockSignals(False)

    # ================================================================
    #  Apply / Cancel
    # ================================================================
    def on_apply_deletions(self) -> None:
        indices = []
        for row in range(self.points_table.rowCount()):
            flag_item = self.points_table.item(row, 6)
            if flag_item and flag_item.checkState() == _Checked:
                indices.append(row)
        self.dock.eval.apply_deletions(indices)
        self.dock._clear_nf_overlays()
        self.points_table.setRowCount(0)
        self.inspect_summary.setText(f"Removed {len(indices)} point(s).")

    def on_cancel(self) -> None:
        self.dock._clear_nf_overlays()
        try:
            self.dock.eval.cancel()
        except Exception:
            pass
        self.points_table.setRowCount(0)
        self.batch_table.setRowCount(0)
        self.inspect_summary.setText("")

    # ================================================================
    #  Export
    # ================================================================
    def on_export(self, fmt: str) -> None:
        dock = self.dock
        report = dock._last_report
        if not report:
            try:
                report = dock.eval.compute_full_report()
                dock._last_report = report
            except Exception:
                self.inspect_summary.setText("Run evaluation first.")
                return
        ext = {"csv": "CSV files (*.csv)", "json": "JSON files (*.json)"}
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, f"Export NF Report ({fmt.upper()})", "",
            ext.get(fmt, "All files (*)"),
        )
        if not path:
            return
        try:
            from dc_cut.api.analysis_ops import export_nearfield_report
            result = export_nearfield_report(report, path, fmt=fmt)
            if result["success"]:
                self.inspect_summary.setText(f"Exported to {result['path']}")
            else:
                self.inspect_summary.setText(
                    f"Export error: {'; '.join(result['errors'])}"
                )
        except Exception as exc:
            self.inspect_summary.setText(f"Export error: {exc}")

    def on_export_npz(self) -> None:
        """Export figure data as NPZ for Report Studio."""
        dock = self.dock
        if not dock._last_batch:
            self.inspect_summary.setText("Run evaluation first.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export NF Figure Data", "nf_evaluation_data.npz",
            "NumPy files (*.npz);;All (*)",
        )
        if not path:
            return
        try:
            arrays = {}
            for i, r in enumerate(dock._last_batch):
                prefix = f"offset_{i}"
                for key in ("f", "v", "w", "nacd", "mask"):
                    if key in r:
                        arrays[f"{prefix}_{key}"] = np.asarray(r[key])
                arrays[f"{prefix}_label"] = np.array(r.get("label", ""))
            arrays["n_offsets"] = np.array(len(dock._last_batch))
            arrays["mode"] = np.array(dock._last_mode or "")
            if dock.eval.has_reference:
                arrays["ref_f"] = dock.eval._reference_f
                arrays["ref_v"] = dock.eval._reference_v
            np.savez_compressed(path, **arrays)
            self.inspect_summary.setText(f"Exported to {path}")
        except Exception as exc:
            self.inspect_summary.setText(f"Export error: {exc}")

    def open_scatter_window(self) -> None:
        dock = self.dock
        from dc_cut.gui.views.nf_scatter_window import ScatterWindow
        if dock._scatter_window is None or not dock._scatter_window.isVisible():
            dock._scatter_window = ScatterWindow(dock.eval, parent=dock)
        else:
            dock._scatter_window.refresh()
        dock._scatter_window.show()
        dock._scatter_window.raise_()


__all__ = ["ResultsTab"]
