from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore    = qt_compat.QtCore


class NFEvalDock(QtWidgets.QDockWidget):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("NF Eval", parent)
        self.setObjectName("NFEvalDock")
        self.c = controller
        self.eval = controller.nf_evaluator
        try:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
            )
        except AttributeError:
            feats = (
                QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            self.setFeatures(feats)

        host = QtWidgets.QWidget(self); self.setWidget(host)
        form = QtWidgets.QFormLayout(host)
        # Create combo box but don't populate yet - will be populated in showEvent() when data is ready
        self.combo_off = QtWidgets.QComboBox(host); form.addRow("Offset:", self.combo_off)
        self.spin_nacd = QtWidgets.QDoubleSpinBox(host); self.spin_nacd.setDecimals(2); self.spin_nacd.setRange(0.10, 3.00); self.spin_nacd.setSingleStep(0.02); self.spin_nacd.setValue(float(getattr(self.c, 'nacd_thresh', 1.0))); form.addRow("NACD ≤", self.spin_nacd)
        row = QtWidgets.QHBoxLayout(); self.btn_start  = QtWidgets.QPushButton("Start", host); self.btn_cancel = QtWidgets.QPushButton("Cancel", host); self.btn_apply  = QtWidgets.QPushButton("Apply", host); row.addWidget(self.btn_start); row.addWidget(self.btn_cancel); row.addWidget(self.btn_apply); form.addRow(row)
        form.addRow(QtWidgets.QLabel("Blue: normal  |  Red: NF-flagged", host))
        self.list_widget = QtWidgets.QListWidget(host)
        try:
            pol = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        except AttributeError:
            pol = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.list_widget.setSizePolicy(pol); self.list_widget.setMinimumHeight(240)
        try:
            self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        except AttributeError:
            self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        form.addRow(self.list_widget)
        self.btn_start.clicked.connect(self._on_start); self.btn_cancel.clicked.connect(self._on_cancel); self.btn_apply.clicked.connect(self._on_apply); self.spin_nacd.valueChanged.connect(self._on_thresh); self.list_widget.itemChanged.connect(self._on_item_changed)
        try:
            from matplotlib.backends import qt_compat as _qt
            QtGui = _qt.QtGui
            self._sc_start = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self); self._sc_start.activated.connect(self._on_start)
            self._sc_cancel = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self); self._sc_cancel.activated.connect(self._on_cancel)
            self._sc_apply = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self); self._sc_apply.activated.connect(self._on_apply)
        except Exception:
            pass
    
    def showEvent(self, event):
        """Override showEvent to refresh offsets when dock becomes visible."""
        super().showEvent(event)
        self._refresh_offsets()

    def _on_start(self):
        # Refresh offset list before starting (in case data was reloaded)
        self._refresh_offsets()
        try: idx = int(self.combo_off.currentIndex()); label = self.c.offset_labels[idx]
        except Exception: label = self.combo_off.currentText()
        thr = float(self.spin_nacd.value()); self.eval.start_with(label, thr, open_checklist=False)
        QtCore.QTimer.singleShot(0, self._populate)

    def _on_cancel(self):
        # Clear overlays from canvas before clearing list
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try: lf.remove(); lw.remove()
                except Exception: pass
            self.c._nf_point_overlay = {}
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass
        try: self.eval.cancel()
        finally: self.list_widget.clear()

    def _on_apply(self):
        try: role_user = QtCore.Qt.UserRole; chk_on = QtCore.Qt.Checked
        except AttributeError: role_user = QtCore.Qt.ItemDataRole.UserRole; chk_on = QtCore.Qt.CheckState.Checked
        indices = []
        for j in range(self.list_widget.count()):
            it = self.list_widget.item(j)
            if it.checkState() == chk_on:
                indices.append(int(it.data(role_user)))
        self.eval.apply_deletions(indices)
        # Clear overlays after applying deletions
        try:
            for lf, lw in list(getattr(self.c, '_nf_point_overlay', {}).values()):
                try: lf.remove(); lw.remove()
                except Exception: pass
            self.c._nf_point_overlay = {}
        except Exception:
            pass
        self.list_widget.clear()

    def _on_thresh(self, val: float):
        try: self.c.nacd_thresh = float(val)
        except Exception: pass
        self.eval.update_threshold(float(val)); self._populate()

    def _on_item_changed(self, item):
        self._apply_checks_to_overlays()

    def _populate(self):
        data = self.eval.get_current_arrays()
        self.list_widget.blockSignals(True); self.list_widget.clear()
        if not data:
            self.list_widget.blockSignals(False); return
        idx, f_arr, v_arr, w_arr, nacd, mask = data
        try: role_user = QtCore.Qt.UserRole; chk_on = QtCore.Qt.Checked; chk_off = QtCore.Qt.Unchecked
        except AttributeError: role_user = QtCore.Qt.ItemDataRole.UserRole; chk_on = QtCore.Qt.CheckState.Checked; chk_off = QtCore.Qt.CheckState.Unchecked
        for i in range(len(f_arr)):
            txt = f"{i:3d}  f={f_arr[i]:6.2f} Hz   v={v_arr[i]:5.1f}  λ={w_arr[i]:6.2f}  NACD={nacd[i]:4.2f}"
            item = QtWidgets.QListWidgetItem(txt)
            try: item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            except AttributeError: item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
            if mask is not None and bool(mask[i]): item.setCheckState(chk_on)
            else: item.setCheckState(chk_off)
            item.setData(role_user, int(i)); self.list_widget.addItem(item)
        self.list_widget.blockSignals(False); self._apply_checks_to_overlays()

    def _refresh_offsets(self):
        """Refresh the offset dropdown to reflect current data."""
        try:
            # Get current selection
            current_text = self.combo_off.currentText()
            
            # Clear and repopulate
            self.combo_off.blockSignals(True)
            self.combo_off.clear()
            offsets_no_avg = list(self.c.offset_labels[:-2]) if len(self.c.offset_labels) >= 2 else list(self.c.offset_labels)
            self.combo_off.addItems(offsets_no_avg)
            
            # Restore selection if possible
            idx = self.combo_off.findText(current_text)
            if idx >= 0:
                self.combo_off.setCurrentIndex(idx)
            self.combo_off.blockSignals(False)
        except Exception:
            pass
    
    def _apply_checks_to_overlays(self):
        data = self.eval.get_current_arrays()
        if not data: return
        idx, f_arr, v_arr, w_arr, nacd, mask = data; c = self.c
        # Clear existing overlays
        for lf, lw in list(getattr(c, '_nf_point_overlay', {}).values()):
            try: lf.remove(); lw.remove()
            except Exception: pass
        c._nf_point_overlay = {}
        try: role_user = QtCore.Qt.UserRole; chk_on = QtCore.Qt.Checked
        except AttributeError: role_user = QtCore.Qt.ItemDataRole.UserRole; chk_on = QtCore.Qt.CheckState.Checked
        
        # Add overlays for ALL points: Red for checked (NF-flagged), Blue for unchecked (normal)
        for j in range(self.list_widget.count()):
            it = self.list_widget.item(j)
            i = int(it.data(role_user))
            
            if it.checkState() == chk_on:
                # RED overlay for near-field flagged points (checked)
                lf = c.ax_freq.semilogx([f_arr[i]], [v_arr[i]], 'o', linestyle='None', mfc='none', mec='red', mew=1.6, ms=6, zorder=10, label='_nf_overlay')[0]
                lw = c.ax_wave.semilogx([w_arr[i]], [v_arr[i]], 'o', linestyle='None', mfc='none', mec='red', mew=1.6, ms=6, zorder=10, label='_nf_overlay')[0]
            else:
                # BLUE overlay for normal points (unchecked)
                lf = c.ax_freq.semilogx([f_arr[i]], [v_arr[i]], 'o', linestyle='None', mfc='none', mec='blue', mew=1.6, ms=6, zorder=10, label='_nf_overlay')[0]
                lw = c.ax_wave.semilogx([w_arr[i]], [v_arr[i]], 'o', linestyle='None', mfc='none', mec='blue', mew=1.6, ms=6, zorder=10, label='_nf_overlay')[0]
            
            c._nf_point_overlay[i] = (lf, lw)
        c.fig.canvas.draw_idle()


