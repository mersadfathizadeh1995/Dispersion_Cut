"""
Data tree — hierarchical QTreeWidget with drag-drop between subplots.

Structure:
    Subplot 1
      ├─ Offset +10m  [✓] (draggable)
      │    ├─ Data: 50 points (freq / vel)
      │    └─ Spectrum: fdbf  [✓]
      ├─ Offset +20m  [✓]
      │    ├─ Data: 45 points (freq / vel)
      │    └─ Spectrum: fdbf  [✓]
      └─ Offset +30m  [ ]
           └─ Data: 48 points (freq / vel)
    Subplot 2
      └─ ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Checked, Unchecked, UserRole, CheckStateRole,
    ItemIsEnabled, ItemIsSelectable, ItemIsUserCheckable,
    ItemIsDragEnabled, ItemIsDropEnabled,
    NoEditTriggers, DragDrop, MoveAction,
)

if TYPE_CHECKING:
    from ...core.models import SheetState, OffsetCurve


# Role for storing uid / subplot_key
_UID_ROLE = UserRole
_KEY_ROLE = UserRole + 1
_ITEM_TYPE_ROLE = UserRole + 2

_TYPE_SUBPLOT = "subplot"
_TYPE_CURVE = "curve"
_TYPE_INFO = "info"
_TYPE_SPECTRUM = "spectrum"
_TYPE_AGGREGATED = "aggregated"
_TYPE_AGG_GROUP = "agg_group"
_TYPE_AGG_AVG = "agg_avg"
_TYPE_AGG_UNC = "agg_unc"
_TYPE_AGG_SHADOW_GROUP = "agg_shadow_group"
_TYPE_AGG_SHADOW = "agg_shadow"
_TYPE_NF_ANALYSIS = "nf_analysis"
_TYPE_NF_GUIDE = "nf_guide_line"
_TYPE_NF_PER_OFFSET = "nf_per_offset"
_TYPE_LAMBDA_LINE = "lambda_line"
_TYPE_LEGEND = "legend"

_LAMBDA_UID_ROLE = UserRole + 5
_NF_LINE_UID_ROLE = UserRole + 6
_NF_OFFSET_INDEX_ROLE = UserRole + 7
# Store the raw kind/role/lambda_max_curve flags from NFLine on the tree
# item so the bottom selection toolbar can filter without parsing the
# display label back out.
_NF_KIND_ROLE = UserRole + 8
_NF_ROLE_ROLE = UserRole + 9
_NF_LAMBDA_MAX_CURVE_ROLE = UserRole + 10


class _DragTreeWidget(QtWidgets.QTreeWidget):
    """QTreeWidget with drag-drop support for moving curves between subplots."""

    curve_moved = Signal(str, str)       # uid, new_subplot_key
    aggregated_moved = Signal(str, str)  # agg_uid, new_subplot_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(DragDrop)
        self.setDefaultDropAction(MoveAction)
        self.setEditTriggers(NoEditTriggers)
        try:
            self.setSelectionMode(
                QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        except AttributeError:
            self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _find_subplot_ancestor(item):
        """Walk up the tree to find the nearest subplot root item."""
        node = item
        while node is not None:
            if node.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
                return node
            node = node.parent()
        return None

    # ── drag / drop ──────────────────────────────────────────────────

    def startDrag(self, supportedActions):
        """Allow dragging curve items and aggregated group nodes."""
        item = self.currentItem()
        if item:
            itype = item.data(0, _ITEM_TYPE_ROLE)
            if itype in (_TYPE_CURVE, _TYPE_AGG_GROUP):
                super().startDrag(supportedActions)

    def dragEnterEvent(self, event):
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Accept drops on or inside any subplot root item."""
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        target = self.itemAt(pos)
        if target and self._find_subplot_ancestor(target) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Move curve or aggregated group to the target subplot."""
        try:
            pos = event.position().toPoint()
        except AttributeError:
            pos = event.pos()
        target = self.itemAt(pos)
        if not target:
            return

        # Walk up to find the subplot root
        sp_item = self._find_subplot_ancestor(target)
        if sp_item is None:
            return
        new_key = sp_item.data(0, _KEY_ROLE)

        dragged = self.currentItem()
        if not dragged:
            return

        itype = dragged.data(0, _ITEM_TYPE_ROLE)
        uid = dragged.data(0, _UID_ROLE)
        if not uid or not new_key:
            return

        if itype == _TYPE_CURVE:
            self.curve_moved.emit(uid, new_key)
        elif itype == _TYPE_AGG_GROUP:
            self.aggregated_moved.emit(uid, new_key)
        event.acceptProposedAction()


class DataTreePanel(QtWidgets.QWidget):
    """
    Left dock panel — hierarchical data tree with visibility checkboxes.

    Signals
    -------
    curve_selected(str)
    curve_visibility_changed(str, bool)
    spectrum_visibility_changed(str, bool)
    curve_moved(str, str)
    remove_curve_requested(str)
    add_data_requested()
    """

    curve_selected = Signal(str)
    curves_selected = Signal(list)       # List[str] — multi-select curve UIDs
    spectrum_selected = Signal(str)      # curve uid whose spectrum was selected
    spectra_selected = Signal(list)      # List[str] — multi-select spectrum UIDs
    subplot_selected = Signal(str)       # subplot key
    subplots_selected = Signal(list)     # List[str] — multi-select subplot keys
    curve_visibility_changed = Signal(str, bool)
    spectrum_visibility_changed = Signal(str, bool)
    curve_moved = Signal(str, str)
    remove_curve_requested = Signal(str)
    remove_curves_requested = Signal(list)  # List[str] — batch removal
    add_data_requested = Signal(str)  # subplot_key
    subplot_renamed = Signal(str, str)  # (key, new_name)
    aggregated_selected = Signal(str)  # aggregated uid
    aggregated_visibility_changed = Signal(str, str, bool)  # (agg_uid, sub_layer, visible)
    aggregated_moved = Signal(str, str)  # (agg_uid, new_subplot_key)
    remove_aggregated_requested = Signal(str)  # aggregated uid
    lambda_visibility_changed = Signal(str, str, bool)
    lambda_line_selected = Signal(str, str)
    nf_analysis_selected = Signal(str)
    nf_guide_visibility_changed = Signal(str, str, bool)
    nf_guide_line_selected = Signal(str, str)
    nf_layer_visibility_changed = Signal(str, bool)
    nf_per_offset_visibility_changed = Signal(str, int, bool)
    nf_per_offset_selected = Signal(str, int)
    legend_layer_selected = Signal(str)            # subplot_key
    legend_visibility_changed = Signal(str, bool)  # (subplot_key, visible)
    legends_selected = Signal(list)                # list[str] subplot_keys
    # list[tuple[str, str]] — (nf_uid, line_uid) pairs for batch NF-line edit.
    nf_guides_selected = Signal(list)
    # list[str] — NACD analysis UIDs for batch NF-settings edit
    nacd_analyses_selected = Signal(list)
    clear_subplot_requested = Signal(str)          # subplot_key

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Header with add button
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Data"))
        add_btn = QtWidgets.QToolButton()
        add_btn.setText("+")
        add_btn.setToolTip("Add data to selected subplot")
        add_btn.clicked.connect(self._on_add_clicked)
        header.addStretch()
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Tree widget
        self._tree = _DragTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemChanged.connect(self._on_item_changed)
        self._tree.curve_moved.connect(self.curve_moved.emit)
        self._tree.aggregated_moved.connect(self.aggregated_moved.emit)
        # Windows Explorer-style strong blue selection highlight
        self._tree.setStyleSheet(
            "QTreeWidget::item:selected {"
            "  background-color: #3399FF;"
            "  color: white;"
            "}"
            "QTreeWidget::item:selected:!active {"
            "  background-color: #5CACEE;"
            "  color: white;"
            "}"
        )
        layout.addWidget(self._tree)

        # ── Bottom toolbar: collapse/expand, select-by-type, bulk on/off
        self._build_bottom_toolbar(layout)

        # Context menu
        self._tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu
                                        if not hasattr(QtCore.Qt, "ContextMenuPolicy")
                                        else QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)

        self._subplot_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}
        self._curve_items: Dict[str, QtWidgets.QTreeWidgetItem] = {}

    # ── Public API ─────────────────────────────────────────────────────

    def populate(self, sheet: "SheetState"):
        """Rebuild the tree from a SheetState."""
        self._tree.blockSignals(True)
        self._tree.clear()
        self._subplot_items.clear()
        self._curve_items.clear()

        # Collect all shadow curve UIDs so they can be excluded from regular loop
        shadow_uids: set = set()
        for agg in sheet.aggregated.values():
            shadow_uids.update(agg.shadow_curve_uids)

        for key in sheet.subplot_keys_ordered():
            sp = sheet.subplots[key]
            sp_item = QtWidgets.QTreeWidgetItem([sp.display_name])
            sp_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_SUBPLOT)
            sp_item.setData(0, _KEY_ROLE, key)
            sp_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsDropEnabled
            )

            # Bold font for subplot headers
            font = sp_item.font(0)
            font.setBold(True)
            sp_item.setFont(0, font)

            # ── Aggregated group (if linked) ──────────────────────────
            if sp.aggregated_uid:
                agg = sheet.aggregated.get(sp.aggregated_uid)
                if agg:
                    agg_group = self._make_aggregated_group(agg, sheet)
                    sp_item.addChild(agg_group)

            # ── Regular curves (skip shadow curves) ───────────────────
            for uid in sp.curve_uids:
                if uid in shadow_uids:
                    continue
                curve = sheet.curves.get(uid)
                if not curve:
                    continue
                c_item = self._make_curve_item(curve, key, sheet)
                sp_item.addChild(c_item)
                self._curve_items[uid] = c_item

            self._add_nf_items_for_subplot(sp_item, sp, sheet)

            # ── Legend layer node (always present) ─────────────────────
            lc = getattr(sp, "legend", None)
            if lc is not None:
                leg_item = QtWidgets.QTreeWidgetItem(["Legend"])
                leg_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_LEGEND)
                leg_item.setData(0, _KEY_ROLE, key)
                leg_item.setFlags(
                    ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
                )
                leg_item.setCheckState(
                    0, Checked if bool(lc.visible) else Unchecked
                )
                leg_item.setForeground(0, QtGui.QColor("#444477"))
                sp_item.addChild(leg_item)

            self._tree.addTopLevelItem(sp_item)
            self._subplot_items[key] = sp_item
            sp_item.setExpanded(True)

        self._tree.blockSignals(False)

    def _make_aggregated_group(self, agg, sheet) -> QtWidgets.QTreeWidgetItem:
        """Build the hierarchical aggregated layer group."""
        # ── Group root: 📊 Name ──
        group = QtWidgets.QTreeWidgetItem([f"📊 {agg.display_name}"])
        group.setData(0, _ITEM_TYPE_ROLE, _TYPE_AGG_GROUP)
        group.setData(0, _UID_ROLE, agg.uid)
        group.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
        # Group is checked if ANY sub-layer is visible
        all_on = agg.avg_visible or agg.uncertainty_visible or agg.shadow_visible
        group.setCheckState(0, Checked if all_on else Unchecked)
        font = group.font(0)
        font.setBold(True)
        font.setItalic(True)
        group.setFont(0, font)

        # ── Average Line child ──
        avg_item = QtWidgets.QTreeWidgetItem(["Average Line"])
        avg_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_AGG_AVG)
        avg_item.setData(0, _UID_ROLE, agg.uid)
        avg_item.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
        avg_item.setCheckState(0, Checked if agg.avg_visible else Unchecked)
        # Color swatch
        px = QtGui.QPixmap(12, 12)
        px.fill(QtGui.QColor(agg.avg_color))
        avg_item.setIcon(0, QtGui.QIcon(px))
        group.addChild(avg_item)

        # ── Uncertainty child ──
        unc_item = QtWidgets.QTreeWidgetItem(["Uncertainty"])
        unc_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_AGG_UNC)
        unc_item.setData(0, _UID_ROLE, agg.uid)
        unc_item.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
        unc_item.setCheckState(0, Checked if agg.uncertainty_visible else Unchecked)
        unc_color = agg.effective_uncertainty_color
        px2 = QtGui.QPixmap(12, 12)
        px2.fill(QtGui.QColor(unc_color))
        unc_item.setIcon(0, QtGui.QIcon(px2))
        group.addChild(unc_item)

        # ── Shadow Curves sub-group ──
        shadow_group = QtWidgets.QTreeWidgetItem(["Shadow Curves"])
        shadow_group.setData(0, _ITEM_TYPE_ROLE, _TYPE_AGG_SHADOW_GROUP)
        shadow_group.setData(0, _UID_ROLE, agg.uid)
        shadow_group.setFlags(
            ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
        shadow_group.setCheckState(0, Checked if agg.shadow_visible else Unchecked)
        shadow_group.setForeground(0, QtGui.QColor("#666666"))

        for sc_uid in agg.shadow_curve_uids:
            sc = sheet.curves.get(sc_uid)
            if not sc:
                continue
            sc_item = QtWidgets.QTreeWidgetItem([sc.display_name])
            sc_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_AGG_SHADOW)
            sc_item.setData(0, _UID_ROLE, sc.uid)
            sc_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
            sc_item.setCheckState(0, Checked if sc.visible else Unchecked)
            if sc.color:
                px3 = QtGui.QPixmap(12, 12)
                px3.fill(QtGui.QColor(sc.color))
                sc_item.setIcon(0, QtGui.QIcon(px3))
            shadow_group.addChild(sc_item)
            self._curve_items[sc.uid] = sc_item

        group.addChild(shadow_group)

        # ── Binning info ──
        info_item = QtWidgets.QTreeWidgetItem(
            [f"Binning: {agg.num_bins} bins (bias {agg.log_bias:.1f})"])
        info_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_INFO)
        info_item.setData(0, _UID_ROLE, agg.uid)
        info_item.setFlags(ItemIsEnabled | ItemIsSelectable)
        info_item.setForeground(0, QtGui.QColor("#888888"))
        group.addChild(info_item)

        group.setExpanded(True)
        shadow_group.setExpanded(False)
        return group

    def select_curve(self, uid: str):
        """Programmatically select a curve in the tree."""
        item = self._curve_items.get(uid)
        if item:
            self._tree.setCurrentItem(item)

    # ── Tree item construction ─────────────────────────────────────────

    def _make_curve_item(self, curve, key: str, sheet) -> QtWidgets.QTreeWidgetItem:
        """Build a curve tree item with data info and spectrum sub-layers."""
        c_item = QtWidgets.QTreeWidgetItem([curve.display_name])
        c_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_CURVE)
        c_item.setData(0, _UID_ROLE, curve.uid)
        c_item.setData(0, _KEY_ROLE, key)
        c_item.setFlags(
            ItemIsEnabled | ItemIsSelectable
            | ItemIsUserCheckable | ItemIsDragEnabled
        )
        c_item.setCheckState(0, Checked if curve.visible else Unchecked)

        # Color indicator
        if curve.color:
            px = QtGui.QPixmap(12, 12)
            px.fill(QtGui.QColor(curve.color))
            c_item.setIcon(0, QtGui.QIcon(px))

        # Sub-layer: Data info
        n_pts = curve.n_points
        if curve.point_mask is not None:
            n_active = int(curve.point_mask.sum())
            data_text = f"Data: {n_active}/{n_pts} points"
        else:
            data_text = f"Data: {n_pts} points"
        info_item = QtWidgets.QTreeWidgetItem([data_text])
        info_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_INFO)
        info_item.setData(0, _UID_ROLE, curve.uid)
        info_item.setFlags(ItemIsEnabled | ItemIsSelectable)
        # Dimmed style for info rows
        info_item.setForeground(0, QtGui.QColor("#888888"))
        c_item.addChild(info_item)

        # Sub-layer: Spectrum (if linked)
        if curve.spectrum_uid:
            spec = sheet.spectra.get(curve.spectrum_uid)
            spec_label = f"Spectrum"
            if spec:
                spec_label += f": {spec.method}"
            spec_item = QtWidgets.QTreeWidgetItem([spec_label])
            spec_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_SPECTRUM)
            spec_item.setData(0, _UID_ROLE, curve.uid)
            spec_item.setFlags(
                ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
            )
            spec_item.setCheckState(
                0, Checked if curve.spectrum_visible else Unchecked
            )
            spec_item.setForeground(0, QtGui.QColor("#666699"))
            c_item.addChild(spec_item)

        if curve.lambda_lines:
            lam_root = QtWidgets.QTreeWidgetItem(["λ guide lines"])
            lam_root.setData(0, _ITEM_TYPE_ROLE, _TYPE_INFO)
            lam_root.setData(0, _UID_ROLE, curve.uid)
            lam_root.setFlags(ItemIsEnabled | ItemIsSelectable)
            for ll in curve.lambda_lines:
                li = QtWidgets.QTreeWidgetItem([
                    f"λ = {ll.lambda_value:.1f} m",
                ])
                li.setData(0, _ITEM_TYPE_ROLE, _TYPE_LAMBDA_LINE)
                li.setData(0, _UID_ROLE, curve.uid)
                li.setData(0, _LAMBDA_UID_ROLE, ll.uid)
                li.setFlags(
                    ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
                )
                li.setCheckState(0, Checked if ll.visible else Unchecked)
                lam_root.addChild(li)
            c_item.addChild(lam_root)

        return c_item

    def _add_nf_items_for_subplot(self, sp_item, sp, sheet: "SheetState"):
        """Nest NACD analyses under this subplot with guide-line toggles."""
        for nf_uid in getattr(sp, "nf_uids", None) or []:
            nf = sheet.nf_analyses.get(nf_uid)
            if not nf:
                continue
            nf_item = QtWidgets.QTreeWidgetItem([nf.display_name])
            nf_item.setData(0, _ITEM_TYPE_ROLE, _TYPE_NF_ANALYSIS)
            nf_item.setData(0, _UID_ROLE, nf.uid)
            nf_item.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
            nf_item.setCheckState(0, Checked if getattr(nf, "visible", True) else Unchecked)

            guide_root = QtWidgets.QTreeWidgetItem(["Guide lines"])
            guide_root.setData(0, _ITEM_TYPE_ROLE, _TYPE_INFO)
            guide_root.setData(0, _UID_ROLE, nf.uid)
            guide_root.setFlags(ItemIsEnabled | ItemIsSelectable)
            from ...rendering.label_format import fmt_freq, fmt_lambda
            freq_dec = int(getattr(sheet.typography, "freq_decimals", 1))
            lam_dec = int(getattr(sheet.typography, "lambda_decimals", 1))
            for ln in nf.lines:
                # Legacy projects may still carry
                # ``NFLine(lambda_max_curve=True)`` rows. The hyperbola
                # now lives on the dispersion curve's "λ guide lines"
                # sub-tab, so hide the duplicate NACD tree entry.
                if bool(getattr(ln, "lambda_max_curve", False)):
                    continue
                disp = (ln.display_label or "").strip()
                if not disp:
                    if ln.kind == "freq":
                        disp = (
                            f"{ln.kind} / {ln.role} = "
                            f"{fmt_freq(ln.value, freq_dec)} Hz"
                        )
                    else:
                        disp = (
                            f"{ln.kind} / {ln.role} = "
                            f"{fmt_lambda(ln.value, lam_dec)} m"
                        )
                li = QtWidgets.QTreeWidgetItem([disp])
                li.setData(0, _ITEM_TYPE_ROLE, _TYPE_NF_GUIDE)
                li.setData(0, _UID_ROLE, nf.uid)
                li.setData(0, _NF_LINE_UID_ROLE, ln.uid)
                li.setData(0, _NF_KIND_ROLE, str(ln.kind or ""))
                li.setData(0, _NF_ROLE_ROLE, str(ln.role or ""))
                li.setData(
                    0, _NF_LAMBDA_MAX_CURVE_ROLE,
                    bool(getattr(ln, "lambda_max_curve", False)),
                )
                li.setFlags(
                    ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable
                )
                li.setCheckState(0, Checked if ln.visible else Unchecked)
                if ln.color:
                    px = QtGui.QPixmap(12, 12)
                    px.fill(QtGui.QColor(ln.color))
                    li.setIcon(0, QtGui.QIcon(px))
                guide_root.addChild(li)
            nf_item.addChild(guide_root)
            guide_root.setExpanded(True)

            for offset_idx, r in enumerate(nf.per_offset):
                stats = QtWidgets.QTreeWidgetItem(
                    [
                        f"Per-offset stats: {r.label or '—'}: "
                        f"λ_max={r.lambda_max:.1f} m, "
                        f"{r.n_contaminated}/{r.n_total} flagged"
                    ]
                )
                stats.setData(0, _ITEM_TYPE_ROLE, _TYPE_NF_PER_OFFSET)
                stats.setData(0, _UID_ROLE, nf.uid)
                stats.setData(0, _NF_OFFSET_INDEX_ROLE, int(offset_idx))
                stats.setFlags(ItemIsEnabled | ItemIsSelectable | ItemIsUserCheckable)
                stats.setCheckState(
                    0,
                    Checked if bool(getattr(r, "scatter_visible", True)) else Unchecked,
                )
                stats.setForeground(0, QtGui.QColor("#555555"))
                nf_item.addChild(stats)
            sp_item.addChild(nf_item)
            nf_item.setExpanded(True)

    # ── Bottom toolbar ─────────────────────────────────────────────────

    # Display name → internal filter key. Kept in one place so the popup
    # menu and ``_select_by_mode`` stay in sync.
    _SELECTION_MODES = (
        ("Legend",                      "legend"),
        ("Spectrum",                    "spectrum"),
        ("Source offset data",          "curve"),
        ("Source-offset guide lines",   "source_offset_guide"),
        ("NACD guide lines",            "guide"),
        ("NACD",                        "nacd"),
        ("NACD \u03bb_max",             "nacd_lambda_max"),
        ("NACD f_min",                  "nacd_f_min"),
        ("Subplots",                    "subplot"),
    )

    def _build_bottom_toolbar(self, parent_layout):
        """Create the collapse/expand + select-by-type + on/off bar.

        Ordered to match the left-to-right flow the user asked for:
        fold/unfold the tree, pick *what* to select, then act on the
        selection. The selection menu opens **upwards** so it does not
        clip against the bottom of the dock.
        """
        bar = QtWidgets.QWidget(self)
        hl = QtWidgets.QHBoxLayout(bar)
        hl.setContentsMargins(0, 4, 0, 0)
        hl.setSpacing(4)

        btn_collapse = QtWidgets.QToolButton(bar)
        btn_collapse.setText("Collapse all")
        btn_collapse.clicked.connect(self._collapse_all)
        hl.addWidget(btn_collapse)

        btn_expand = QtWidgets.QToolButton(bar)
        btn_expand.setText("Expand all")
        btn_expand.clicked.connect(self._expand_all)
        hl.addWidget(btn_expand)

        self._btn_select = QtWidgets.QToolButton(bar)
        self._btn_select.setText("Select by \u25b2")
        self._btn_select.setToolTip(
            "Select every item of a given kind across all subplots."
        )
        self._btn_select.clicked.connect(self._show_selection_popup)
        hl.addWidget(self._btn_select)

        hl.addStretch(1)

        btn_on = QtWidgets.QToolButton(bar)
        btn_on.setText("Turn on")
        btn_on.setToolTip("Turn every selected layer on.")
        btn_on.clicked.connect(lambda: self._set_selected_visibility(True))
        hl.addWidget(btn_on)

        btn_off = QtWidgets.QToolButton(bar)
        btn_off.setText("Turn off")
        btn_off.setToolTip("Turn every selected layer off.")
        btn_off.clicked.connect(lambda: self._set_selected_visibility(False))
        hl.addWidget(btn_off)

        parent_layout.addWidget(bar)

    def _collapse_all(self) -> None:
        self._tree.collapseAll()

    def _expand_all(self) -> None:
        self._tree.expandAll()

    def _show_selection_popup(self) -> None:
        """Pop the selection menu *above* the button (drop-up behaviour)."""
        menu = QtWidgets.QMenu(self)
        for label, mode in self._SELECTION_MODES:
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _checked=False, m=mode: self._select_by_mode(m)
            )
        size = menu.sizeHint()
        anchor = self._btn_select.mapToGlobal(
            QtCore.QPoint(0, -size.height())
        )
        menu.exec(anchor)

    def _iter_all_items(self):
        """Yield every QTreeWidgetItem in the tree, depth-first."""
        def _walk(parent):
            for i in range(parent.childCount()):
                child = parent.child(i)
                yield child
                yield from _walk(child)
        root = self._tree.invisibleRootItem()
        yield from _walk(root)

    def _item_matches_mode(self, item, mode: str) -> bool:
        itype = item.data(0, _ITEM_TYPE_ROLE)
        if mode == "legend":
            return itype == _TYPE_LEGEND
        if mode == "spectrum":
            return itype == _TYPE_SPECTRUM
        if mode == "curve":
            return itype == _TYPE_CURVE
        if mode == "source_offset_guide":
            return itype == _TYPE_LAMBDA_LINE
        if mode == "guide":
            return itype == _TYPE_NF_GUIDE
        if mode == "nacd":
            return itype == _TYPE_NF_ANALYSIS
        if mode == "subplot":
            return itype == _TYPE_SUBPLOT
        if mode == "nacd_lambda_max":
            if itype != _TYPE_NF_GUIDE:
                return False
            if bool(item.data(0, _NF_LAMBDA_MAX_CURVE_ROLE)):
                return True
            return (
                item.data(0, _NF_KIND_ROLE) == "lambda"
                and item.data(0, _NF_ROLE_ROLE) == "max"
            )
        if mode == "nacd_f_min":
            if itype != _TYPE_NF_GUIDE:
                return False
            return (
                item.data(0, _NF_KIND_ROLE) == "freq"
                and item.data(0, _NF_ROLE_ROLE) == "min"
            )
        return False

    def _select_by_mode(self, mode: str) -> None:
        """Clear the current selection and select every matching item.

        Uses the selection model's ``NoUpdate`` flag when seating the
        "current" item so it doesn't wipe out the multi-select we just
        built up.
        """
        selection_model = self._tree.selectionModel()
        self._tree.blockSignals(True)
        try:
            self._tree.clearSelection()
            last = None
            for item in self._iter_all_items():
                if self._item_matches_mode(item, mode):
                    item.setSelected(True)
                    last = item
        finally:
            self._tree.blockSignals(False)
        if last is not None:
            try:
                NoUpdate = QtCore.QItemSelectionModel.SelectionFlag.NoUpdate
            except AttributeError:
                NoUpdate = QtCore.QItemSelectionModel.NoUpdate
            index = self._tree.indexFromItem(last)
            selection_model.setCurrentIndex(index, NoUpdate)
            # Drive the click path once so the right panel's batch-select
            # signals fire with every selected item.
            self._on_item_clicked(last, 0)

    def _set_selected_visibility(self, visible: bool) -> None:
        """Turn every selected (check-able) item on or off in one pass.

        Re-uses the existing ``itemChanged`` path so each visibility
        handler updates the sheet model exactly as it would for a user
        click. The main window's render timer coalesces the flurry of
        signals into a single redraw.
        """
        state = Checked if visible else Unchecked
        items = [it for it in self._tree.selectedItems()
                 if (it.flags() & ItemIsUserCheckable)]
        for it in items:
            if it.checkState(0) != state:
                it.setCheckState(0, state)

    # ── Event handlers ─────────────────────────────────────────────────

    def _on_item_clicked(self, item, column):
        item_type = item.data(0, _ITEM_TYPE_ROLE)
        uid = item.data(0, _UID_ROLE)
        key = item.data(0, _KEY_ROLE)

        # ── Single-click signal based on item type ────────────────────
        if item_type == _TYPE_SUBPLOT and key:
            self.subplot_selected.emit(key)
        elif item_type == _TYPE_SPECTRUM and uid:
            self.spectrum_selected.emit(uid)
        elif item_type in (_TYPE_AGG_GROUP, _TYPE_AGG_AVG, _TYPE_AGG_UNC,
                           _TYPE_AGGREGATED) and uid:
            self.aggregated_selected.emit(uid)
        elif item_type == _TYPE_AGG_SHADOW and uid:
            # Clicking individual shadow curve selects its curve settings
            self.curve_selected.emit(uid)
        elif item_type == _TYPE_AGG_SHADOW_GROUP and uid:
            self.aggregated_selected.emit(uid)
        elif item_type == _TYPE_NF_ANALYSIS and uid:
            self.nf_analysis_selected.emit(uid)
        elif item_type == _TYPE_NF_GUIDE and uid:
            line_uid = item.data(0, _NF_LINE_UID_ROLE)
            if line_uid:
                self.nf_guide_line_selected.emit(uid, line_uid)
        elif item_type == _TYPE_NF_PER_OFFSET and uid:
            offset_idx = item.data(0, _NF_OFFSET_INDEX_ROLE)
            if offset_idx is not None:
                self.nf_per_offset_selected.emit(uid, int(offset_idx))
        elif item_type == _TYPE_LAMBDA_LINE and uid:
            lam_uid = item.data(0, _LAMBDA_UID_ROLE)
            if lam_uid:
                self.lambda_line_selected.emit(uid, lam_uid)
        elif item_type == _TYPE_LEGEND and key:
            self.legend_layer_selected.emit(key)
        elif item_type in (_TYPE_CURVE, _TYPE_INFO) and uid:
            if item_type == _TYPE_CURVE:
                self.curve_selected.emit(uid)
            elif item.parent() and item.parent().data(0, _ITEM_TYPE_ROLE) == _TYPE_CURVE:
                self.curve_selected.emit(uid)

        # ── Multi-select: gather per type ─────────────────────────────
        sel_curve_uids = []
        sel_spectrum_uids = []
        sel_subplot_keys = []
        sel_legend_keys: list = []
        sel_nf_guides: list = []  # list[tuple[str, str]]
        sel_nacd_uids: list = []

        for sel_item in self._tree.selectedItems():
            sel_type = sel_item.data(0, _ITEM_TYPE_ROLE)
            sel_uid = sel_item.data(0, _UID_ROLE)
            sel_key = sel_item.data(0, _KEY_ROLE)

            if sel_type == _TYPE_SUBPLOT and sel_key:
                if sel_key not in sel_subplot_keys:
                    sel_subplot_keys.append(sel_key)
            elif sel_type == _TYPE_SPECTRUM and sel_uid:
                if sel_uid not in sel_spectrum_uids:
                    sel_spectrum_uids.append(sel_uid)
            elif sel_type in (_TYPE_CURVE, _TYPE_AGG_SHADOW) and sel_uid:
                if sel_uid not in sel_curve_uids:
                    sel_curve_uids.append(sel_uid)
            elif sel_type == _TYPE_INFO and sel_uid:
                if sel_uid not in sel_curve_uids:
                    sel_curve_uids.append(sel_uid)
            elif sel_type == _TYPE_LEGEND and sel_key:
                if sel_key not in sel_legend_keys:
                    sel_legend_keys.append(sel_key)
            elif sel_type == _TYPE_NF_GUIDE and sel_uid:
                line_uid = sel_item.data(0, _NF_LINE_UID_ROLE)
                if line_uid:
                    pair = (sel_uid, line_uid)
                    if pair not in sel_nf_guides:
                        sel_nf_guides.append(pair)
            elif sel_type == _TYPE_NF_ANALYSIS and sel_uid:
                if sel_uid not in sel_nacd_uids:
                    sel_nacd_uids.append(sel_uid)

        # Emit batch signals when >1 items of same type
        if len(sel_curve_uids) > 1:
            self.curves_selected.emit(sel_curve_uids)
        if len(sel_spectrum_uids) > 1:
            self.spectra_selected.emit(sel_spectrum_uids)
        if len(sel_subplot_keys) > 1:
            self.subplots_selected.emit(sel_subplot_keys)
        if len(sel_legend_keys) > 1:
            self.legends_selected.emit(sel_legend_keys)
        if len(sel_nf_guides) > 1:
            self.nf_guides_selected.emit(sel_nf_guides)
        if len(sel_nacd_uids) > 1:
            self.nacd_analyses_selected.emit(sel_nacd_uids)

    def _on_item_changed(self, item, column):
        item_type = item.data(0, _ITEM_TYPE_ROLE)
        uid = item.data(0, _UID_ROLE)

        if item_type == _TYPE_CURVE:
            checked = item.checkState(0) == Checked
            if uid:
                self.curve_visibility_changed.emit(uid, checked)

        elif item_type == _TYPE_SPECTRUM:
            checked = item.checkState(0) == Checked
            if uid:
                self.spectrum_visibility_changed.emit(uid, checked)

        elif item_type == _TYPE_AGG_GROUP and uid:
            # Group toggle → propagate to all sub-layers
            checked = item.checkState(0) == Checked
            self._tree.blockSignals(True)
            for i in range(item.childCount()):
                child = item.child(i)
                ctype = child.data(0, _ITEM_TYPE_ROLE)
                if ctype in (_TYPE_AGG_AVG, _TYPE_AGG_UNC, _TYPE_AGG_SHADOW_GROUP):
                    child.setCheckState(0, Checked if checked else Unchecked)
                    # Propagate shadow group → individual shadows
                    if ctype == _TYPE_AGG_SHADOW_GROUP:
                        for j in range(child.childCount()):
                            sc = child.child(j)
                            if sc.data(0, _ITEM_TYPE_ROLE) == _TYPE_AGG_SHADOW:
                                sc.setCheckState(0, Checked if checked else Unchecked)
            self._tree.blockSignals(False)
            # Emit signals
            self.aggregated_visibility_changed.emit(uid, "all", checked)

        elif item_type == _TYPE_AGG_AVG and uid:
            checked = item.checkState(0) == Checked
            self.aggregated_visibility_changed.emit(uid, "avg", checked)

        elif item_type == _TYPE_AGG_UNC and uid:
            checked = item.checkState(0) == Checked
            self.aggregated_visibility_changed.emit(uid, "uncertainty", checked)

        elif item_type == _TYPE_AGG_SHADOW_GROUP and uid:
            # Shadow group toggle → propagate to individual shadows
            checked = item.checkState(0) == Checked
            self._tree.blockSignals(True)
            for i in range(item.childCount()):
                sc = item.child(i)
                if sc.data(0, _ITEM_TYPE_ROLE) == _TYPE_AGG_SHADOW:
                    sc.setCheckState(0, Checked if checked else Unchecked)
            self._tree.blockSignals(False)
            self.aggregated_visibility_changed.emit(uid, "shadow", checked)

        elif item_type == _TYPE_AGG_SHADOW and uid:
            checked = item.checkState(0) == Checked
            self.curve_visibility_changed.emit(uid, checked)

        elif item_type == _TYPE_LAMBDA_LINE and uid:
            lam_uid = item.data(0, _LAMBDA_UID_ROLE)
            checked = item.checkState(0) == Checked
            if lam_uid:
                self.lambda_visibility_changed.emit(uid, lam_uid, checked)

        elif item_type == _TYPE_NF_GUIDE and uid:
            line_uid = item.data(0, _NF_LINE_UID_ROLE)
            checked = item.checkState(0) == Checked
            if line_uid:
                self.nf_guide_visibility_changed.emit(uid, line_uid, checked)

        elif item_type == _TYPE_NF_ANALYSIS and uid:
            checked = item.checkState(0) == Checked
            self.nf_layer_visibility_changed.emit(uid, checked)

        elif item_type == _TYPE_LEGEND:
            key = item.data(0, _KEY_ROLE)
            checked = item.checkState(0) == Checked
            if key:
                self.legend_visibility_changed.emit(key, checked)

        elif item_type == _TYPE_NF_PER_OFFSET and uid:
            offset_idx = item.data(0, _NF_OFFSET_INDEX_ROLE)
            checked = item.checkState(0) == Checked
            if offset_idx is not None:
                self.nf_per_offset_visibility_changed.emit(
                    uid, int(offset_idx), checked
                )

    def _on_add_clicked(self):
        """Determine target subplot and emit add_data_requested(subplot_key)."""
        # Use currently selected subplot, or the first one
        item = self._tree.currentItem()
        key = ""
        if item:
            itype = item.data(0, _ITEM_TYPE_ROLE)
            if itype == _TYPE_SUBPLOT:
                key = item.data(0, _KEY_ROLE) or ""
            elif item.parent():
                parent = item.parent()
                if parent.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
                    key = parent.data(0, _KEY_ROLE) or ""
        # Fallback to first subplot
        if not key and self._subplot_items:
            key = next(iter(self._subplot_items))
        self.add_data_requested.emit(key or "main")

    def _on_context_menu(self, pos):
        item = self._tree.itemAt(pos)
        if not item:
            return

        menu = QtWidgets.QMenu(self)
        item_type = item.data(0, _ITEM_TYPE_ROLE)

        if item_type == _TYPE_SUBPLOT:
            key = item.data(0, _KEY_ROLE)
            act_add = menu.addAction("Add data...")
            act_add.triggered.connect(
                lambda: self.add_data_requested.emit(key or "main"))
            act_rename = menu.addAction("Rename subplot")
            act_rename.triggered.connect(lambda: self._begin_rename(item))
            menu.addSeparator()
            act_clear = menu.addAction("Clear subplot...")
            act_clear.triggered.connect(
                lambda: self._confirm_clear_subplot(key or "main", item.text(0))
            )

        if item_type == _TYPE_CURVE:
            # Collect all selected curve UIDs
            selected_uids = []
            for sel in self._tree.selectedItems():
                if sel.data(0, _ITEM_TYPE_ROLE) in (_TYPE_CURVE, _TYPE_AGG_SHADOW):
                    uid = sel.data(0, _UID_ROLE)
                    if uid:
                        selected_uids.append(uid)

            uid = item.data(0, _UID_ROLE)
            if len(selected_uids) > 1:
                act_remove = menu.addAction(
                    f"Remove {len(selected_uids)} curves")
                act_remove.triggered.connect(
                    lambda: self.remove_curves_requested.emit(selected_uids))
            else:
                act_remove = menu.addAction("Remove curve")
                act_remove.triggered.connect(
                    lambda: self.remove_curve_requested.emit(uid))

        if item_type == _TYPE_AGG_GROUP:
            uid = item.data(0, _UID_ROLE)
            act_remove = menu.addAction("Remove aggregated figure")
            act_remove.triggered.connect(
                lambda: self.remove_aggregated_requested.emit(uid))

        if item_type == _TYPE_AGG_SHADOW:
            uid = item.data(0, _UID_ROLE)
            act_remove = menu.addAction("Remove shadow curve")
            act_remove.triggered.connect(
                lambda: self.remove_curve_requested.emit(uid))

        if menu.actions():
            menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _confirm_clear_subplot(self, key: str, display: str) -> None:
        """Ask before wiping every layer from a subplot cell."""
        try:
            Yes = QtWidgets.QMessageBox.StandardButton.Yes
            No = QtWidgets.QMessageBox.StandardButton.No
        except AttributeError:
            Yes = QtWidgets.QMessageBox.Yes
            No = QtWidgets.QMessageBox.No
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear subplot",
            f"Remove all data from \"{display}\"?\n\n"
            "This drops its curves, aggregated figure, and NACD analyses. "
            "The subplot cell itself stays in the grid.",
            Yes | No,
            No,
        )
        if reply == Yes:
            self.clear_subplot_requested.emit(key)

    def _begin_rename(self, item):
        """Start inline editing of a subplot name."""
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        self._tree.editItem(item, 0)
        # Connect once to capture the edit
        self._tree.itemChanged.disconnect(self._on_item_changed)
        self._tree.itemChanged.connect(self._on_rename_finished)

    def _on_rename_finished(self, item, column):
        """Handle subnet rename completion."""
        # Reconnect normal handler
        self._tree.itemChanged.disconnect(self._on_rename_finished)
        self._tree.itemChanged.connect(self._on_item_changed)
        # Remove editable flag
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

        if item.data(0, _ITEM_TYPE_ROLE) == _TYPE_SUBPLOT:
            key = item.data(0, _KEY_ROLE)
            new_name = item.text(0).strip()
            if key and new_name:
                self.subplot_renamed.emit(key, new_name)
