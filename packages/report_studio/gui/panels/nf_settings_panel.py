"""Settings for :class:`NFAnalysis` overlays."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ...qt_compat import QtWidgets, QtGui, Signal

from .collapsible import CollapsibleSection
from .nf_ranges_panel import NFRangesPanel

if TYPE_CHECKING:
    from ...core.models import NFAnalysis


class NFSettingsPanel(QtWidgets.QWidget):
    nf_setting_changed = Signal(str, str, object)  # nf_uid, attr, value
    nf_recompute_requested = Signal(str)
    nf_ranges_apply_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nf_uid = ""
        self._nf: Optional["NFAnalysis"] = None
        # Populated by :meth:`show_nf_batch`. When set, every attribute
        # edit fan-outs one ``nf_setting_changed`` emit per UID so the
        # change applies to every selected NACD analysis.
        self._batch_uids: List[str] = []

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._batch_banner = QtWidgets.QLabel("")
        self._batch_banner.setStyleSheet(
            "background:#fff3cd;border:1px solid #ffd36e;"
            "border-radius:3px;padding:4px;color:#5a4500;"
            "font-weight:bold;"
        )
        self._batch_banner.setVisible(False)
        outer.addWidget(self._batch_banner)

        form_holder = QtWidgets.QWidget()
        # Do NOT give form_holder stretch=1 — that made the QFormLayout
        # swallow all extra vertical space and pushed the Ranges table
        # well below its section label.  A trailing stretch on the
        # outer layout keeps the form compact at the top instead.
        outer.addWidget(form_holder)
        layout = QtWidgets.QFormLayout(form_holder)

        self._le_legend_label = QtWidgets.QLineEdit()
        self._le_legend_label.setPlaceholderText("(default: Contaminated)")
        self._le_legend_label.editingFinished.connect(
            lambda: self._emit("legend_label", self._le_legend_label.text())
        )
        layout.addRow("Legend name:", self._le_legend_label)

        self._palette_btns = {}
        row = QtWidgets.QHBoxLayout()
        for key in ("clean", "marginal", "contaminated", "unknown"):
            b = QtWidgets.QPushButton(key[:4])
            b.setToolTip(key)
            b.clicked.connect(lambda _=False, k=key: self._pick_palette(k))
            row.addWidget(b)
            self._palette_btns[key] = b
        layout.addRow("Severity palette:", row)

        self._overlay = QtWidgets.QComboBox()
        for m in ("scatter_on_top", "off"):
            self._overlay.addItem(m, m)
        self._overlay.currentIndexChanged.connect(self._emit_overlay)
        layout.addRow("Overlay:", self._overlay)

        # Contaminated-scatter outline group
        self._outline_section = CollapsibleSection(
            "Contaminated outline", expanded=False
        )
        self._chk_outline_visible = QtWidgets.QCheckBox(
            "Show outline around contaminated markers"
        )
        self._chk_outline_visible.toggled.connect(
            lambda on: self._emit("contaminated_edge_visible", bool(on))
        )
        self._outline_section.form.addRow(self._chk_outline_visible)

        self._spin_outline_w = QtWidgets.QDoubleSpinBox()
        self._spin_outline_w.setRange(0.0, 10.0)
        self._spin_outline_w.setSingleStep(0.1)
        self._spin_outline_w.setDecimals(2)
        self._spin_outline_w.valueChanged.connect(
            lambda v: self._emit("contaminated_edge_width", float(v))
        )
        self._outline_section.form.addRow("Outline width:", self._spin_outline_w)

        self._btn_outline_color = QtWidgets.QPushButton()
        self._btn_outline_color.setToolTip("Outline color")
        self._btn_outline_color.clicked.connect(self._pick_outline_color)
        self._outline_section.form.addRow(
            "Outline color:", self._btn_outline_color
        )
        layout.addRow(self._outline_section)

        self._ranges_section = CollapsibleSection(
            "Ranges (per-offset)", expanded=False
        )
        self._ranges = NFRangesPanel()
        self._ranges_section.form.addRow(self._ranges)
        self._use_range_mask = QtWidgets.QCheckBox(
            "Use range as contamination mask"
        )
        self._use_range_mask.toggled.connect(self._emit_use_range_mask)
        self._ranges_section.form.addRow(self._use_range_mask)
        self._apply_ranges = QtWidgets.QPushButton("Apply ranges & re-derive lines")
        self._apply_ranges.clicked.connect(self._on_apply_ranges_clicked)
        self._ranges_section.form.addRow(self._apply_ranges)
        layout.addRow(self._ranges_section)

        btn = QtWidgets.QPushButton("Recompute (reload data)")
        btn.setToolTip("Re-open Add Data with the same PKL to refresh NF from file.")
        btn.clicked.connect(self._on_recompute)
        layout.addRow(btn)

        # Absorb any leftover vertical space so the form above stays
        # packed at the top of the dock.  Without this, switching
        # ``form_holder`` to stretch=0 would leave the panel sitting
        # in the middle of an empty QScrollArea.
        outer.addStretch(1)

    def current_nf_uid(self) -> str:
        return self._nf_uid

    def get_eval_range_dict(self) -> Dict[str, Any]:
        try:
            return self._ranges.get_range_dict()
        except Exception:
            return {}

    def show_nf(self, nf: "NFAnalysis") -> None:
        self._batch_uids = []
        self._batch_banner.setVisible(False)
        self._nf = nf
        self._nf_uid = nf.uid
        self._overlay.blockSignals(True)
        self._use_range_mask.blockSignals(True)
        self._le_legend_label.blockSignals(True)
        self._le_legend_label.setText(getattr(nf, "legend_label", "") or "")
        self._le_legend_label.blockSignals(False)
        idx = self._overlay.findData(nf.severity_overlay_mode)
        self._overlay.setCurrentIndex(max(0, idx))
        for k, b in self._palette_btns.items():
            col = nf.severity_palette.get(k, "#888888")
            b.setStyleSheet(f"background-color: {col}; min-height: 22px;")
        self._ranges.set_range_dict(nf.settings.get("eval_range"))
        self._use_range_mask.setChecked(bool(nf.use_range_as_mask))
        self._chk_outline_visible.blockSignals(True)
        self._spin_outline_w.blockSignals(True)
        self._chk_outline_visible.setChecked(
            bool(getattr(nf, "contaminated_edge_visible", True))
        )
        self._spin_outline_w.setValue(
            float(getattr(nf, "contaminated_edge_width", 0.5) or 0.0)
        )
        outline_col = getattr(nf, "contaminated_edge_color", "#000000") or "#000000"
        self._btn_outline_color.setStyleSheet(
            f"background-color: {outline_col}; min-height: 22px;"
        )
        self._chk_outline_visible.blockSignals(False)
        self._spin_outline_w.blockSignals(False)
        self._overlay.blockSignals(False)
        self._use_range_mask.blockSignals(False)

    def _pick_outline_color(self):
        if not self._nf and not self._batch_uids:
            return
        cur = getattr(self._nf, "contaminated_edge_color", "#000000") \
            if self._nf else "#000000"
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(cur), self, "Outline color"
        )
        if c.isValid():
            name = c.name()
            self._btn_outline_color.setStyleSheet(
                f"background-color: {name}; min-height: 22px;"
            )
            self._emit("contaminated_edge_color", name)

    def _pick_palette(self, key: str):
        if not self._nf and not self._batch_uids:
            return
        cur = (
            self._nf.severity_palette.get(key, "#888888")
            if self._nf else "#888888"
        )
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(cur), self, key)
        if c.isValid():
            self._emit(f"palette:{key}", c.name())

    def _emit_overlay(self, _i: int):
        self._emit("severity_overlay_mode", self._overlay.currentData())

    def _emit_use_range_mask(self, on: bool):
        self._emit("use_range_as_mask", bool(on))

    def _emit(self, attr: str, value) -> None:
        """Fan out a single setting edit to every NACD in batch mode."""
        if self._batch_uids:
            for uid in self._batch_uids:
                self.nf_setting_changed.emit(uid, attr, value)
            return
        if not self._nf_uid:
            return
        self.nf_setting_changed.emit(self._nf_uid, attr, value)

    def show_nf_batch(self, nfs: List["NFAnalysis"]) -> None:
        """Seat the panel on N NACD analyses at once.

        Widgets display the FIRST analysis's values as a seed; any
        subsequent edit fans out to every uid in ``self._batch_uids``.
        """
        if not nfs:
            self._batch_uids = []
            self._batch_banner.setVisible(False)
            return
        first = nfs[0]
        self.show_nf(first)
        self._batch_uids = [nf.uid for nf in nfs]
        self._batch_banner.setText(
            f"Editing {len(self._batch_uids)} NACD layers together"
        )
        self._batch_banner.setVisible(True)

    def _on_apply_ranges_clicked(self):
        if self._nf_uid:
            self.nf_ranges_apply_requested.emit(self._nf_uid)

    def _on_recompute(self):
        if self._nf_uid:
            self.nf_recompute_requested.emit(self._nf_uid)
