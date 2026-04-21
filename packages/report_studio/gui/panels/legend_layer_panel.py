"""Context panel for the Legend layer of one subplot.

Edits the :class:`SubplotLegendConfig` attached to
:attr:`SubplotState.legend`. All controls emit ``legend_changed``
with ``(subplot_key, attr, value)`` so the controller can copy the
value onto the model and re-render.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from ...qt_compat import QtWidgets, Signal
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import SubplotLegendConfig, SubplotState


# Keep this in sync with builder.LOC_ANCHORS keys (matplotlib loc strings).
_LOC_OPTIONS = [
    "best", "upper right", "upper left", "lower left", "lower right",
    "right", "center left", "center right",
    "lower center", "upper center", "center",
]

_PLACEMENT_OPTIONS = [
    ("inside", "Inside the subplot"),
    ("outside_right", "Outside right"),
    ("outside_left", "Outside left"),
    ("outside_top", "Outside top"),
    ("outside_bottom", "Outside bottom"),
]

_ORIENTATION_OPTIONS = [
    ("auto", "Auto (vertical for L/R, horizontal for T/B)"),
    ("vertical", "Vertical (one column)"),
    ("horizontal", "Horizontal (one row)"),
]

# How aggressively to dedupe entries in the combined legend.
_DEDUPE_KIND_OPTIONS = [
    ("exact", "Exact (drop identical labels)"),
    ("prefix", "By name (one λ_max / f_min entry, hide values)"),
    ("range",  "By name with range (e.g. λ_max = 28 – 53 m)"),
]

_ENTRY_ORDER_OPTIONS = [
    ("as_drawn", "As drawn (matplotlib default)"),
    ("by_name",  "Alphabetical (groups similar names)"),
    ("by_kind",  "By kind (curves → NACD → guide lines)"),
]


class LegendLayerPanel(QtWidgets.QWidget):
    """Settings for the per-subplot legend layer.

    Supports two modes:

    * **Single** — a single subplot's legend, edited via :meth:`show_legend`.
    * **Batch** — multiple subplots' legends edited together via
      :meth:`show_legends_batch`. Every change emits ``legend_changed``
      once per selected key so the controller can apply the same value
      to every selected legend (e.g., flip every subplot to
      ``outside_right`` at once for a combined outside legend).
    """

    # subplot_key, attr, value
    legend_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._key: str = ""
        self._lc: Optional["SubplotLegendConfig"] = None
        self._batch_keys: List[str] = []  # non-empty ⇒ batch mode
        self._updating = False

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        # ── Mode banner (only visible in batch mode) ────────────────
        self._batch_banner = QtWidgets.QLabel("")
        self._batch_banner.setStyleSheet(
            "QLabel { background:#3399FF; color:white; padding:4px 6px;"
            " border-radius:3px; font-weight:bold; }"
        )
        self._batch_banner.setVisible(False)
        outer.addWidget(self._batch_banner)

        # ── Visibility ──────────────────────────────────────────────
        self._chk_visible = QtWidgets.QCheckBox("Show legend")
        self._chk_visible.toggled.connect(
            lambda v: self._emit("visible", bool(v))
        )
        outer.addWidget(self._chk_visible)

        # ── Placement & location ────────────────────────────────────
        # Each section uses CollapsibleSection so power users can fold
        # away the parts they're not tweaking — matches the rest of the
        # context panels (curve/NACD/lambda).
        place_sec = CollapsibleSection("Placement", expanded=True)
        pf = place_sec.form
        pf.setSpacing(4)

        self._cmb_placement = QtWidgets.QComboBox()
        for value, label in _PLACEMENT_OPTIONS:
            self._cmb_placement.addItem(label, value)
        self._cmb_placement.currentIndexChanged.connect(
            lambda _: self._emit(
                "placement",
                self._cmb_placement.currentData() or "inside",
            )
        )
        pf.addRow("Placement:", self._cmb_placement)

        self._cmb_loc = QtWidgets.QComboBox()
        for loc in _LOC_OPTIONS:
            self._cmb_loc.addItem(loc, loc)
        self._cmb_loc.currentIndexChanged.connect(
            lambda _: self._emit(
                "location", self._cmb_loc.currentData() or "best"
            )
        )
        pf.addRow("Location:", self._cmb_loc)

        self._cmb_orient = QtWidgets.QComboBox()
        for value, label in _ORIENTATION_OPTIONS:
            self._cmb_orient.addItem(label, value)
        self._cmb_orient.currentIndexChanged.connect(
            lambda _: self._emit(
                "orientation", self._cmb_orient.currentData() or "auto"
            )
        )
        pf.addRow("Orientation:", self._cmb_orient)

        self._chk_combine = QtWidgets.QCheckBox(
            "Combine all outside subplots into one legend"
        )
        self._chk_combine.toggled.connect(
            lambda v: self._emit("combine", bool(v))
        )
        pf.addRow(self._chk_combine)

        self._spn_offx = QtWidgets.QDoubleSpinBox()
        self._spn_offx.setRange(-1.0, 1.0)
        self._spn_offx.setSingleStep(0.02)
        self._spn_offx.setDecimals(2)
        self._spn_offx.valueChanged.connect(
            lambda v: self._emit("offset_x", float(v))
        )
        pf.addRow("Offset X (axes frac):", self._spn_offx)

        self._spn_offy = QtWidgets.QDoubleSpinBox()
        self._spn_offy.setRange(-1.0, 1.0)
        self._spn_offy.setSingleStep(0.02)
        self._spn_offy.setDecimals(2)
        self._spn_offy.valueChanged.connect(
            lambda v: self._emit("offset_y", float(v))
        )
        pf.addRow("Offset Y (axes frac):", self._spn_offy)

        outer.addWidget(place_sec)

        # ── Appearance ──────────────────────────────────────────────
        appear_sec = CollapsibleSection("Appearance", expanded=True)
        af = appear_sec.form
        af.setSpacing(4)

        self._spn_scale = QtWidgets.QDoubleSpinBox()
        self._spn_scale.setRange(0.25, 5.0)
        self._spn_scale.setSingleStep(0.05)
        self._spn_scale.setDecimals(2)
        self._spn_scale.setSuffix("×")
        self._spn_scale.setToolTip(
            "Multiplies font size, marker size and spacing — scales the "
            "whole legend block at once."
        )
        self._spn_scale.valueChanged.connect(
            lambda v: self._emit("scale", float(v))
        )
        af.addRow("Scale:", self._spn_scale)

        self._spn_ncol = QtWidgets.QSpinBox()
        self._spn_ncol.setRange(1, 12)
        self._spn_ncol.valueChanged.connect(
            lambda v: self._emit("ncol", int(v))
        )
        af.addRow("Columns:", self._spn_ncol)

        self._spn_marker = QtWidgets.QDoubleSpinBox()
        self._spn_marker.setRange(0.2, 5.0)
        self._spn_marker.setSingleStep(0.1)
        self._spn_marker.setDecimals(2)
        self._spn_marker.valueChanged.connect(
            lambda v: self._emit("markerscale", float(v))
        )
        af.addRow("Marker scale:", self._spn_marker)

        self._spn_fs = QtWidgets.QDoubleSpinBox()
        self._spn_fs.setRange(0.0, 48.0)  # 0 = inherit typography
        self._spn_fs.setSingleStep(0.5)
        self._spn_fs.setDecimals(1)
        self._spn_fs.setSpecialValueText("inherit")
        self._spn_fs.valueChanged.connect(
            lambda v: self._emit("fontsize", float(v) if v > 0 else None)
        )
        af.addRow("Font size:", self._spn_fs)

        self._chk_frame = QtWidgets.QCheckBox("Frame")
        self._chk_frame.toggled.connect(
            lambda v: self._emit("frame_on", bool(v))
        )
        af.addRow(self._chk_frame)

        self._spn_alpha = QtWidgets.QDoubleSpinBox()
        self._spn_alpha.setRange(0.0, 1.0)
        self._spn_alpha.setSingleStep(0.05)
        self._spn_alpha.setDecimals(2)
        self._spn_alpha.valueChanged.connect(
            lambda v: self._emit("frame_alpha", float(v))
        )
        af.addRow("Frame alpha:", self._spn_alpha)

        self._chk_shadow = QtWidgets.QCheckBox("Shadow")
        self._chk_shadow.toggled.connect(
            lambda v: self._emit("shadow", bool(v))
        )
        af.addRow(self._chk_shadow)

        self._le_title = QtWidgets.QLineEdit()
        self._le_title.setPlaceholderText("(no title)")
        self._le_title.editingFinished.connect(
            lambda: self._emit("title", self._le_title.text())
        )
        af.addRow("Title:", self._le_title)

        outer.addWidget(appear_sec)

        # ── Advanced (entry order, dedupe mode, curve collapse) ──
        adv_sec = CollapsibleSection("Advanced", expanded=False)
        adv = adv_sec.form
        adv.setSpacing(4)

        self._cmb_order = QtWidgets.QComboBox()
        for value, label in _ENTRY_ORDER_OPTIONS:
            self._cmb_order.addItem(label, value)
        self._cmb_order.setToolTip(
            "Reorder the legend rows so similar entries cluster together. "
            "Use 'By kind' if a single curve is appearing far from its "
            "siblings."
        )
        self._cmb_order.currentIndexChanged.connect(
            lambda _: self._emit(
                "entry_order",
                self._cmb_order.currentData() or "as_drawn",
            )
        )
        adv.addRow("Entry order:", self._cmb_order)

        self._chk_dedupe = QtWidgets.QCheckBox(
            "Drop duplicate labels in the combined legend"
        )
        self._chk_dedupe.toggled.connect(
            lambda v: self._emit("dedupe", bool(v))
        )
        adv.addRow(self._chk_dedupe)

        self._cmb_dedupe_kind = QtWidgets.QComboBox()
        for value, label in _DEDUPE_KIND_OPTIONS:
            self._cmb_dedupe_kind.addItem(label, value)
        self._cmb_dedupe_kind.setToolTip(
            "Controls how the combined legend collapses repeated guide-line "
            "entries (only used when 'Drop duplicate labels' is on)."
        )
        self._cmb_dedupe_kind.currentIndexChanged.connect(
            lambda _: self._emit(
                "dedupe_kind",
                self._cmb_dedupe_kind.currentData() or "exact",
            )
        )
        adv.addRow("Dedupe mode:", self._cmb_dedupe_kind)

        self._chk_collapse_curves = QtWidgets.QCheckBox(
            "Replace per-offset curves with a single entry"
        )
        self._chk_collapse_curves.setToolTip(
            "Useful when the legend would otherwise list one row per "
            "source offset (e.g. Love/fdbf -5, -10, -15…). The single "
            "entry uses the label below."
        )
        self._chk_collapse_curves.toggled.connect(
            lambda v: self._emit("collapse_curves", bool(v))
        )
        adv.addRow(self._chk_collapse_curves)

        self._le_curves_label = QtWidgets.QLineEdit()
        self._le_curves_label.setPlaceholderText("Source offset curves")
        self._le_curves_label.editingFinished.connect(
            lambda: self._emit("curves_label", self._le_curves_label.text())
        )
        adv.addRow("Combined name:", self._le_curves_label)

        outer.addWidget(adv_sec)

        # ── Hidden labels ──────────────────────────────────────────
        hidden_sec = CollapsibleSection("Hide entries", expanded=False)
        hl_form = hidden_sec.form
        hl_form.setSpacing(4)
        hint = QtWidgets.QLabel(
            "One label per line. Entries matching exactly are removed."
        )
        hint.setStyleSheet("color: #666;")
        hint.setWordWrap(True)
        hl_form.addRow(hint)
        self._txt_hidden = QtWidgets.QPlainTextEdit()
        self._txt_hidden.setFixedHeight(80)
        self._txt_hidden.textChanged.connect(self._on_hidden_changed)
        hl_form.addRow(self._txt_hidden)
        outer.addWidget(hidden_sec)

        outer.addStretch(1)

    # ── Public API ────────────────────────────────────────────────

    def show_legend(self, key: str, sp: "SubplotState") -> None:
        """Populate the panel from one subplot's legend config."""
        self._updating = True
        try:
            self._key = key
            self._lc = sp.legend
            self._batch_keys = []
            self._batch_banner.setVisible(False)

            self._chk_visible.setChecked(bool(self._lc.visible))

            placement = self._lc.placement or "inside"
            for i in range(self._cmb_placement.count()):
                if self._cmb_placement.itemData(i) == placement:
                    self._cmb_placement.setCurrentIndex(i)
                    break

            loc = self._lc.location or "best"
            idx = self._cmb_loc.findData(loc)
            if idx < 0:
                self._cmb_loc.addItem(loc, loc)
                idx = self._cmb_loc.findData(loc)
            self._cmb_loc.setCurrentIndex(idx)

            orient = self._lc.orientation or "auto"
            for i in range(self._cmb_orient.count()):
                if self._cmb_orient.itemData(i) == orient:
                    self._cmb_orient.setCurrentIndex(i)
                    break
            self._chk_combine.setChecked(bool(self._lc.combine))
            self._chk_dedupe.setChecked(bool(self._lc.dedupe))
            dk = self._lc.dedupe_kind or "exact"
            for i in range(self._cmb_dedupe_kind.count()):
                if self._cmb_dedupe_kind.itemData(i) == dk:
                    self._cmb_dedupe_kind.setCurrentIndex(i)
                    break
            order = self._lc.entry_order or "as_drawn"
            for i in range(self._cmb_order.count()):
                if self._cmb_order.itemData(i) == order:
                    self._cmb_order.setCurrentIndex(i)
                    break
            self._chk_collapse_curves.setChecked(
                bool(self._lc.collapse_curves)
            )
            self._le_curves_label.setText(self._lc.curves_label or "")

            self._spn_offx.setValue(float(self._lc.offset_x or 0.0))
            self._spn_offy.setValue(float(self._lc.offset_y or 0.0))
            self._spn_scale.setValue(float(self._lc.scale or 1.0))
            self._spn_ncol.setValue(int(self._lc.ncol or 1))
            self._spn_marker.setValue(float(self._lc.markerscale or 1.0))
            self._spn_fs.setValue(float(self._lc.fontsize or 0.0))
            self._chk_frame.setChecked(bool(self._lc.frame_on))
            self._spn_alpha.setValue(float(self._lc.frame_alpha or 0.9))
            self._chk_shadow.setChecked(bool(self._lc.shadow))
            self._le_title.setText(self._lc.title or "")
            self._txt_hidden.setPlainText(
                "\n".join(self._lc.hidden_labels or [])
            )
        finally:
            self._updating = False

    def show_legends_batch(
        self, keys: List[str], subplots: Dict[str, "SubplotState"]
    ) -> None:
        """Edit several subplot legends together.

        The first subplot's current values seed the controls so the
        user sees a sensible starting state; any change is then emitted
        once per key in ``keys``. This makes it easy to flip every
        subplot to ``outside_right`` (combined outside) or to align all
        legends to ``upper right`` in a single gesture.
        """
        if not keys:
            return
        if len(keys) == 1:
            sp = subplots.get(keys[0])
            if sp is not None:
                self.show_legend(keys[0], sp)
            return
        seed = subplots.get(keys[0])
        if seed is None or getattr(seed, "legend", None) is None:
            return
        self._updating = True
        try:
            self._key = keys[0]
            self._lc = seed.legend
            self._batch_keys = list(keys)
            self._batch_banner.setText(
                f"Editing {len(keys)} legends together"
            )
            self._batch_banner.setVisible(True)

            lc = seed.legend
            self._chk_visible.setChecked(bool(lc.visible))

            placement = lc.placement or "inside"
            for i in range(self._cmb_placement.count()):
                if self._cmb_placement.itemData(i) == placement:
                    self._cmb_placement.setCurrentIndex(i)
                    break

            loc = lc.location or "best"
            idx = self._cmb_loc.findData(loc)
            if idx < 0:
                self._cmb_loc.addItem(loc, loc)
                idx = self._cmb_loc.findData(loc)
            self._cmb_loc.setCurrentIndex(idx)

            orient = lc.orientation or "auto"
            for i in range(self._cmb_orient.count()):
                if self._cmb_orient.itemData(i) == orient:
                    self._cmb_orient.setCurrentIndex(i)
                    break
            self._chk_combine.setChecked(bool(lc.combine))
            self._chk_dedupe.setChecked(bool(lc.dedupe))
            dk = lc.dedupe_kind or "exact"
            for i in range(self._cmb_dedupe_kind.count()):
                if self._cmb_dedupe_kind.itemData(i) == dk:
                    self._cmb_dedupe_kind.setCurrentIndex(i)
                    break
            order = lc.entry_order or "as_drawn"
            for i in range(self._cmb_order.count()):
                if self._cmb_order.itemData(i) == order:
                    self._cmb_order.setCurrentIndex(i)
                    break
            self._chk_collapse_curves.setChecked(bool(lc.collapse_curves))
            self._le_curves_label.setText(lc.curves_label or "")

            self._spn_offx.setValue(float(lc.offset_x or 0.0))
            self._spn_offy.setValue(float(lc.offset_y or 0.0))
            self._spn_scale.setValue(float(lc.scale or 1.0))
            self._spn_ncol.setValue(int(lc.ncol or 1))
            self._spn_marker.setValue(float(lc.markerscale or 1.0))
            self._spn_fs.setValue(float(lc.fontsize or 0.0))
            self._chk_frame.setChecked(bool(lc.frame_on))
            self._spn_alpha.setValue(float(lc.frame_alpha or 0.9))
            self._chk_shadow.setChecked(bool(lc.shadow))
            self._le_title.setText(lc.title or "")
            self._txt_hidden.setPlainText(
                "\n".join(lc.hidden_labels or [])
            )
        finally:
            self._updating = False

    # ── Internal ─────────────────────────────────────────────────

    def _emit(self, attr: str, value) -> None:
        if self._updating:
            return
        if self._batch_keys:
            for k in self._batch_keys:
                self.legend_changed.emit(k, attr, value)
        elif self._key:
            self.legend_changed.emit(self._key, attr, value)

    def _on_hidden_changed(self) -> None:
        if self._updating:
            return
        text = self._txt_hidden.toPlainText()
        labels = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if self._batch_keys:
            for k in self._batch_keys:
                self.legend_changed.emit(k, "hidden_labels", labels)
        elif self._key:
            self.legend_changed.emit(self._key, "hidden_labels", labels)
