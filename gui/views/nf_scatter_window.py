"""Standalone NACD-vs-V_R scatter window with full settings panel."""
from __future__ import annotations

from typing import Optional

import numpy as np
from matplotlib.backends import qt_compat
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

_OFFSET_PALETTE = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]


class ScatterWindow(QtWidgets.QMainWindow):
    """Standalone window for NACD-vs-V_R scatter with settings."""

    def __init__(
        self,
        evaluator,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Near-Field Scatter Plot")
        self.resize(900, 600)
        self.eval = evaluator

        self._marker_size = 18
        self._marker_alpha = 0.6
        self._x_log = True
        self._y_min = 0.5
        self._y_max = 1.15
        self._show_grid = True
        self._show_zones = True
        self._clean_line = 0.95
        self._marginal_line = 0.85
        self._export_dpi = 200
        self._offset_visible: dict = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)

        # ── Left: canvas ──
        canvas_widget = QtWidgets.QWidget()
        cv_layout = QtWidgets.QVBoxLayout(canvas_widget)
        cv_layout.setContentsMargins(2, 2, 2, 2)

        self._fig = Figure(figsize=(7, 5), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, canvas_widget)

        cv_layout.addWidget(self._toolbar)
        cv_layout.addWidget(self._canvas, stretch=1)
        splitter.addWidget(canvas_widget)

        # ── Right: settings ──
        settings = QtWidgets.QWidget()
        sl = QtWidgets.QVBoxLayout(settings)
        sl.setContentsMargins(4, 4, 4, 4)

        # Data group
        data_grp = QtWidgets.QGroupBox("Data (offsets)")
        self._data_layout = QtWidgets.QVBoxLayout(data_grp)
        self._offset_checks: list = []
        self._data_layout.addWidget(QtWidgets.QLabel("(refresh to populate)"))
        sl.addWidget(data_grp)

        # Appearance group
        app_grp = QtWidgets.QGroupBox("Appearance")
        af = QtWidgets.QFormLayout(app_grp)

        self._size_spin = QtWidgets.QSpinBox()
        self._size_spin.setRange(2, 80)
        self._size_spin.setValue(self._marker_size)
        self._size_spin.valueChanged.connect(self._on_appearance)
        af.addRow("Marker size:", self._size_spin)

        self._alpha_spin = QtWidgets.QDoubleSpinBox()
        self._alpha_spin.setRange(0.1, 1.0)
        self._alpha_spin.setDecimals(2)
        self._alpha_spin.setSingleStep(0.05)
        self._alpha_spin.setValue(self._marker_alpha)
        self._alpha_spin.valueChanged.connect(self._on_appearance)
        af.addRow("Marker alpha:", self._alpha_spin)

        sl.addWidget(app_grp)

        # Axes group
        ax_grp = QtWidgets.QGroupBox("Axes")
        axf = QtWidgets.QFormLayout(ax_grp)

        self._xlog_chk = QtWidgets.QCheckBox("Log X-axis")
        self._xlog_chk.setChecked(True)
        self._xlog_chk.toggled.connect(self._on_appearance)
        axf.addRow(self._xlog_chk)

        self._ymin_spin = QtWidgets.QDoubleSpinBox()
        self._ymin_spin.setRange(0.0, 2.0)
        self._ymin_spin.setDecimals(2)
        self._ymin_spin.setSingleStep(0.05)
        self._ymin_spin.setValue(self._y_min)
        self._ymin_spin.valueChanged.connect(self._on_appearance)
        axf.addRow("Y min:", self._ymin_spin)

        self._ymax_spin = QtWidgets.QDoubleSpinBox()
        self._ymax_spin.setRange(0.5, 2.0)
        self._ymax_spin.setDecimals(2)
        self._ymax_spin.setSingleStep(0.05)
        self._ymax_spin.setValue(self._y_max)
        self._ymax_spin.valueChanged.connect(self._on_appearance)
        axf.addRow("Y max:", self._ymax_spin)

        self._grid_chk = QtWidgets.QCheckBox("Show grid")
        self._grid_chk.setChecked(True)
        self._grid_chk.toggled.connect(self._on_appearance)
        axf.addRow(self._grid_chk)

        sl.addWidget(ax_grp)

        # Zone lines group
        zone_grp = QtWidgets.QGroupBox("Zone Lines")
        zf = QtWidgets.QFormLayout(zone_grp)

        self._zones_chk = QtWidgets.QCheckBox("Show zones & bands")
        self._zones_chk.setChecked(True)
        self._zones_chk.toggled.connect(self._on_appearance)
        zf.addRow(self._zones_chk)

        self._clean_spin = QtWidgets.QDoubleSpinBox()
        self._clean_spin.setRange(0.50, 1.00)
        self._clean_spin.setDecimals(3)
        self._clean_spin.setSingleStep(0.01)
        self._clean_spin.setValue(self._clean_line)
        self._clean_spin.valueChanged.connect(self._on_appearance)
        zf.addRow("Clean line (V_R):", self._clean_spin)

        self._marginal_spin = QtWidgets.QDoubleSpinBox()
        self._marginal_spin.setRange(0.30, 1.00)
        self._marginal_spin.setDecimals(3)
        self._marginal_spin.setSingleStep(0.01)
        self._marginal_spin.setValue(self._marginal_line)
        self._marginal_spin.valueChanged.connect(self._on_appearance)
        zf.addRow("Marginal line (V_R):", self._marginal_spin)

        sl.addWidget(zone_grp)

        # Export group
        exp_grp = QtWidgets.QGroupBox("Export")
        ef = QtWidgets.QFormLayout(exp_grp)

        self._dpi_spin = QtWidgets.QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(self._export_dpi)
        ef.addRow("DPI:", self._dpi_spin)

        self._fmt_combo = QtWidgets.QComboBox()
        self._fmt_combo.addItems(["PNG", "PDF", "SVG"])
        ef.addRow("Format:", self._fmt_combo)

        export_btn = QtWidgets.QPushButton("Export…")
        export_btn.clicked.connect(self._on_export)
        ef.addRow(export_btn)

        sl.addWidget(exp_grp)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Data")
        refresh_btn.setStyleSheet("font-weight: bold; padding: 6px;")
        refresh_btn.clicked.connect(self.refresh)
        sl.addWidget(refresh_btn)

        sl.addStretch()

        splitter.addWidget(settings)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

    # ── Data fetching and plotting ──

    def refresh(self) -> None:
        self._fetch_data()
        self._rebuild_offset_checks()
        self._replot()

    def _fetch_data(self) -> None:
        self._scatter_data = []
        if not self.eval.has_reference:
            return
        all_data = self.eval.get_all_offsets_vr()
        ref_idx = self.eval._reference_index
        for i, (label, nacd, vr) in enumerate(all_data):
            if i == ref_idx:
                continue
            valid = np.isfinite(nacd) & np.isfinite(vr) & (nacd > 0)
            if not np.any(valid):
                continue
            self._scatter_data.append({
                'label': label,
                'nacd': nacd[valid],
                'vr': vr[valid],
                'index': i,
            })
            if label not in self._offset_visible:
                self._offset_visible[label] = True

    def _rebuild_offset_checks(self) -> None:
        for chk in self._offset_checks:
            chk.setParent(None)
            chk.deleteLater()
        self._offset_checks.clear()

        while self._data_layout.count():
            child = self._data_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self._scatter_data:
            self._data_layout.addWidget(QtWidgets.QLabel("No data available"))
            return

        for item in self._scatter_data:
            chk = QtWidgets.QCheckBox(item['label'])
            chk.setChecked(self._offset_visible.get(item['label'], True))
            chk.toggled.connect(self._on_offset_toggle)
            self._data_layout.addWidget(chk)
            self._offset_checks.append(chk)

    def _on_offset_toggle(self, _=None) -> None:
        for chk in self._offset_checks:
            self._offset_visible[chk.text()] = chk.isChecked()
        self._replot()

    def _on_appearance(self, _=None) -> None:
        self._marker_size = self._size_spin.value()
        self._marker_alpha = self._alpha_spin.value()
        self._x_log = self._xlog_chk.isChecked()
        self._y_min = self._ymin_spin.value()
        self._y_max = self._ymax_spin.value()
        self._show_grid = self._grid_chk.isChecked()
        self._show_zones = self._zones_chk.isChecked()
        self._clean_line = self._clean_spin.value()
        self._marginal_line = self._marginal_spin.value()
        self._replot()

    def _replot(self) -> None:
        ax = self._ax
        ax.clear()

        if not self._scatter_data:
            ax.text(0.5, 0.5, "No reference curve set.\nBuild one in the NF Eval tab.",
                    ha='center', va='center', transform=ax.transAxes, fontsize=11)
            self._canvas.draw_idle()
            return

        for idx, item in enumerate(self._scatter_data):
            if not self._offset_visible.get(item['label'], True):
                continue
            c = _OFFSET_PALETTE[idx % len(_OFFSET_PALETTE)]
            ax.scatter(
                item['nacd'], item['vr'],
                s=self._marker_size, alpha=self._marker_alpha,
                label=item['label'], color=c, edgecolors='none',
            )

        if self._show_zones:
            cl = self._clean_line
            ml = self._marginal_line
            ax.axhline(cl, color='green', ls='--', lw=1.0, alpha=0.6)
            ax.axhline(ml, color='orange', ls='--', lw=1.0, alpha=0.6)
            ax.axvline(1.0, color='grey', ls=':', lw=0.8, alpha=0.5)
            ax.axvline(1.5, color='grey', ls=':', lw=0.8, alpha=0.5)

            xmax = 10
            ax.fill_between([0, xmax], cl, self._y_max, alpha=0.04, color='green')
            ax.fill_between([0, xmax], ml, cl, alpha=0.04, color='orange')
            ax.fill_between([0, xmax], self._y_min, ml, alpha=0.04, color='red')

        if self._x_log:
            ax.set_xscale('log')
        else:
            ax.set_xscale('linear')

        ax.set_xlim(left=0.05 if self._x_log else 0)
        ax.set_ylim(self._y_min, self._y_max)
        ax.set_xlabel("NACD (x̄ / λ)", fontsize=10)
        ax.set_ylabel("V_R  (V_meas / V_true)", fontsize=10)
        ax.set_title("Near-Field Contamination Scatter", fontsize=11)
        ax.grid(self._show_grid, alpha=0.3)
        ax.legend(fontsize=7, loc='lower right', framealpha=0.8)
        self._fig.tight_layout()
        self._canvas.draw_idle()

    def _on_export(self) -> None:
        fmt = self._fmt_combo.currentText().lower()
        filters = {
            "png": "PNG files (*.png)",
            "pdf": "PDF files (*.pdf)",
            "svg": "SVG files (*.svg)",
        }
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Scatter Plot",
            f"nacd_vr_scatter.{fmt}",
            filters.get(fmt, "All (*)"),
        )
        if path:
            self._fig.savefig(
                path, dpi=self._dpi_spin.value(), bbox_inches='tight',
            )
