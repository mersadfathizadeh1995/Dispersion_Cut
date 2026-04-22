"""Tab 1: NACD-Only mode (geometry-based, no reference required).

Owns its own widgets (geometry, criteria, colors, ranges, offset
checks, Run button) and implements:

* ``on_criteria_changed`` — auto-fill NACD threshold from source
  type + error level
* ``apply_range_gate`` — enable the range editor only when one
  offset is selected
* ``run`` — execute the NACD-only evaluation, draw overlays, and
  defer limit-line drawing to :class:`LimitsCoordinator`
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from dc_cut.core.processing.nearfield.criteria import (
    SOURCE_TYPE_LABELS,
    ERROR_LEVEL_LABELS,
)
from dc_cut.core.processing.nearfield.nacd_zones import (
    NACDZoneSpec,
    ZoneFill,
    ZoneGroup,
    ZoneThreshold,
    classify_points_into_zones,
    spec_to_derived_limit_set,
    spec_to_zone_bands,
)
from dc_cut.core.processing.nearfield.ranges import (
    EvaluationRange,
    compute_range_mask,
)
from dc_cut.gui.widgets.collapsible_section import CollapsibleSection
from dc_cut.gui.widgets.nf_eval_ranges import NFEvalRangesWidget
from dc_cut.gui.widgets.nf_limit_lines import (
    clear_nf_limit_lines,
    draw_nf_limit_lines,
)
from dc_cut.gui.widgets.nf_zone_bands import (
    clear_nf_zone_artists,
    draw_zone_bands,
    draw_zone_labels,
)

from .common import (
    get_array_positions,
    get_selected_indices,
    make_color_button,
    set_all_offset_checks,
)
from .constants import QtWidgets
from .overlays import draw_nacd_overlay, draw_nacd_overlay_colored
from .zone_editor import MultiGroupEditor, SingleGroupEditor


class NacdTab(QtWidgets.QWidget):
    """The NACD-Only page of the NF Evaluation dock."""

    def __init__(self, dock) -> None:
        super().__init__()
        self.dock = dock
        # Cached multi-zone rendering inputs, populated by ``run()`` and
        # reused by ``_on_limits_state_changed`` so visibility / color
        # edits in the Limit Lines tab can re-paint zone bands and
        # labels without re-running the whole evaluation.
        self._last_spec: Optional[NACDZoneSpec] = None
        self._last_x_bar: float = 0.0
        self._last_f_rep: Optional[np.ndarray] = None
        self._last_v_rep: Optional[np.ndarray] = None
        self._limits_wired: bool = False
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

        # ── View style selector ───────────────────────────────────
        view_row = QtWidgets.QHBoxLayout()
        view_row.addWidget(QtWidgets.QLabel("View style:"))
        self.view_style = QtWidgets.QComboBox()
        for code, label in (
            ("classic", "Classic (single threshold)"),
            ("multi_zone", "Multi-zone (one group)"),
            ("multi_group", "Multi-zone groups"),
        ):
            self.view_style.addItem(label, code)
        self.view_style.currentIndexChanged.connect(self._on_view_style_changed)
        view_row.addWidget(self.view_style, 1)
        layout.addLayout(view_row)

        # ── Array Geometry (collapsible) ──
        geom_sec = CollapsibleSection("Array Geometry", initially_expanded=True)
        geom_form = QtWidgets.QFormLayout()

        self.n_recv = QtWidgets.QSpinBox()
        self.n_recv.setRange(2, 200)
        self.n_recv.setValue(24)
        geom_form.addRow("# Receivers:", self.n_recv)

        self.dx = QtWidgets.QDoubleSpinBox()
        self.dx.setRange(0.1, 50.0)
        self.dx.setDecimals(2)
        self.dx.setValue(2.0)
        geom_form.addRow("Spacing (dx, m):", self.dx)

        self.first_pos = QtWidgets.QDoubleSpinBox()
        self.first_pos.setRange(-500.0, 500.0)
        self.first_pos.setDecimals(1)
        self.first_pos.setValue(0.0)
        geom_form.addRow("First receiver (m):", self.first_pos)

        geom_sec.add_layout(geom_form)
        layout.addWidget(geom_sec)

        # ── NACD Criteria (collapsible) ──
        crit_sec = CollapsibleSection("NACD Criteria", initially_expanded=True)
        self._crit_sec = crit_sec
        crit_form = QtWidgets.QFormLayout()

        self.source_type = QtWidgets.QComboBox()
        for key, label in SOURCE_TYPE_LABELS.items():
            self.source_type.addItem(label, key)
        self.source_type.currentIndexChanged.connect(self.on_criteria_changed)
        crit_form.addRow("Source type:", self.source_type)

        self.error_level = QtWidgets.QComboBox()
        for key, label in ERROR_LEVEL_LABELS.items():
            self.error_level.addItem(label, key)
        self.error_level.currentIndexChanged.connect(self.on_criteria_changed)
        crit_form.addRow("Error level:", self.error_level)

        self.nacd_thr = QtWidgets.QDoubleSpinBox()
        self.nacd_thr.setRange(0.1, 5.0)
        self.nacd_thr.setDecimals(2)
        self.nacd_thr.setSingleStep(0.1)
        self.nacd_thr.setValue(float(getattr(self.dock.c, 'nacd_thresh', 1.0)))
        crit_form.addRow("NACD threshold:", self.nacd_thr)

        crit_sec.add_layout(crit_form)
        layout.addWidget(crit_sec)

        # ── Colors (collapsible) ──
        color_sec = CollapsibleSection("Colors", initially_expanded=False)
        self._color_sec = color_sec
        color_form = QtWidgets.QFormLayout()

        self.clean_color_btn = make_color_button(
            self.dock, self.dock._mode1_colors["clean"], "clean", 1
        )
        color_form.addRow("Clean:", self.clean_color_btn)

        self.contam_color_btn = make_color_button(
            self.dock, self.dock._mode1_colors["contaminated"], "contaminated", 1
        )
        color_form.addRow("Contaminated:", self.contam_color_btn)

        color_sec.add_layout(color_form)
        layout.addWidget(color_sec)

        # ── Offset Selection (BEFORE Evaluation Ranges — the range
        #    editor is only meaningful once a single offset is picked).
        offset_sec = CollapsibleSection("Offset Selection", initially_expanded=True)
        self.offset_layout = QtWidgets.QVBoxLayout()
        btn_row = QtWidgets.QHBoxLayout()
        sel_all = QtWidgets.QPushButton("Select All")
        sel_all.clicked.connect(
            lambda: set_all_offset_checks(self.dock, self.offset_checks, True)
        )
        sel_none = QtWidgets.QPushButton("Select None")
        sel_none.clicked.connect(
            lambda: set_all_offset_checks(self.dock, self.offset_checks, False)
        )
        btn_row.addWidget(sel_all)
        btn_row.addWidget(sel_none)
        self.offset_layout.addLayout(btn_row)
        self.offset_checks: List[QtWidgets.QCheckBox] = []
        offset_sec.add_layout(self.offset_layout)
        layout.addWidget(offset_sec)

        # ── Evaluation Ranges (collapsible) ──
        lim_sec = CollapsibleSection(
            "Evaluation Ranges (f bands + λ bounds)", initially_expanded=True
        )
        self._lim_sec = lim_sec
        self.ranges_widget = NFEvalRangesWidget()
        lim_sec.add_widget(self.ranges_widget)
        layout.addWidget(lim_sec)

        # ── Zones (collapsible, visible for multi_zone) ────────
        self._zones_sec = CollapsibleSection(
            "Zones", initially_expanded=True,
        )
        self.single_zone_editor = SingleGroupEditor(
            show_position=False,
            show_lambda_toggle=True,
            parent=self,
        )
        # Default: one NACD threshold at 1.0 giving two zones
        # (red/contaminated on the left, blue/clean on the right),
        # matching the mock-up the user provided.
        self.single_zone_editor.set_group(ZoneGroup(
            name="Zones",
            thresholds=[ZoneThreshold(nacd=1.0)],
            zones=[
                ZoneFill(zone_label="Zone 2"),
                ZoneFill(zone_label="Zone 1"),
            ],
            draw_lambda=True,
            draw_freq=True,
        ).normalised())
        self.single_zone_editor.group_changed.connect(self._on_spec_edited)
        self._zones_sec.add_widget(self.single_zone_editor)
        layout.addWidget(self._zones_sec)

        # ── Zone groups (collapsible, visible for multi_group) ─
        self._groups_sec = CollapsibleSection(
            "Zone groups", initially_expanded=True,
        )
        self.multi_group_editor = MultiGroupEditor(parent=self)
        self.multi_group_editor.set_groups([
            ZoneGroup(
                name="Group A",
                thresholds=[ZoneThreshold(nacd=1.0)],
                zones=[ZoneFill(), ZoneFill()],
                label_position="top",
                draw_lambda=True,
                draw_freq=True,
            ).normalised(),
            ZoneGroup(
                name="Group B",
                thresholds=[ZoneThreshold(nacd=0.8)],
                zones=[ZoneFill(), ZoneFill()],
                label_position="bottom",
                draw_lambda=True,
                draw_freq=True,
            ).normalised(),
        ])
        self.multi_group_editor.groups_changed.connect(self._on_spec_edited)
        self._groups_sec.add_widget(self.multi_group_editor)
        layout.addWidget(self._groups_sec)

        # ── Run Button ──
        run_btn = QtWidgets.QPushButton("▶  Run NACD Evaluation")
        run_btn.setStyleSheet(
            "font-weight: bold; padding: 10px; font-size: 13px;"
            "background-color: #1565C0; color: white; border-radius: 4px;"
        )
        run_btn.clicked.connect(self.run)
        layout.addWidget(run_btn)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        layout.addStretch()

        # Pre-fill from prefs (geometry only; ranges handled by load_dock_prefs).
        from .prefs_io import m1_load_geometry_prefs
        m1_load_geometry_prefs(self.dock)

        # Initial visibility — classic view hides the zone editors.
        self._on_view_style_changed()

    # ================================================================
    #  Handlers
    # ================================================================
    def on_criteria_changed(self, _=None) -> None:
        try:
            from dc_cut.core.processing.nearfield.criteria import (
                resolve_nacd_threshold,
            )
            st = self.source_type.currentData() or "sledgehammer"
            el = self.error_level.currentData() or "10_15pct"
            thr = resolve_nacd_threshold(source_type=st, error_level=el)
            self.nacd_thr.setValue(thr)
        except Exception:
            pass

    def apply_range_gate(self, *_args, **_kwargs) -> None:
        """Enable the range editor only when ONE offset is selected.

        Rationale: NACD-Only limit lines are derived using the evaluated
        offset's own V(f) curve, so a *per-row* evaluation range only
        makes sense for a single offset.  With multiple offsets selected
        the range is forced empty and only each offset's own auto-
        derived ``\u03bb_max`` is drawn at Run time.
        """
        sel = sum(1 for c in self.offset_checks if c.isChecked())
        if sel == 1:
            self.ranges_widget.set_editing_enabled(True)
        else:
            self.ranges_widget.set_editing_enabled(
                False,
                reason=(
                    "Custom evaluation ranges are only editable when "
                    "exactly one offset is selected.  With multiple "
                    "offsets, only each offset's \u03bb_max line is "
                    "drawn after Run."
                ),
            )
        # Any stale limit lines from a previous run are now invalid.
        self.dock._m1_invalidate_limit_lines()

    def array_positions(self) -> np.ndarray:
        return get_array_positions(
            self.n_recv.value(), self.dx.value(), self.first_pos.value()
        )

    # ================================================================
    #  View-style / Multi-zone spec
    # ================================================================
    def current_style(self) -> str:
        return str(self.view_style.currentData() or "classic")

    def current_spec(self) -> NACDZoneSpec:
        style = self.current_style()
        if style == "multi_zone":
            return NACDZoneSpec(
                style="multi_zone",
                groups=[self.single_zone_editor.get_group()],
                primary_group_index=0,
            )
        if style == "multi_group":
            return NACDZoneSpec(
                style="multi_group",
                groups=list(self.multi_group_editor.get_groups()),
                primary_group_index=0,
            )
        return NACDZoneSpec(style="classic")

    def set_spec(self, spec: Optional[NACDZoneSpec]) -> None:
        spec = spec or NACDZoneSpec()
        idx = max(0, self.view_style.findData(spec.style))
        # Block signals so ``_on_view_style_changed`` fires exactly once
        # after the editors have been populated.
        self.view_style.blockSignals(True)
        try:
            self.view_style.setCurrentIndex(idx)
        finally:
            self.view_style.blockSignals(False)

        if spec.style == "multi_zone" and spec.groups:
            self.single_zone_editor.set_group(spec.groups[0])
        elif spec.style == "multi_group" and spec.groups:
            self.multi_group_editor.set_groups(spec.groups)

        self._on_view_style_changed()

    def _on_view_style_changed(self, *_args) -> None:
        style = self.current_style()
        is_classic = (style == "classic")
        # Classic sections
        self._crit_sec.setVisible(is_classic)
        self._color_sec.setVisible(is_classic)
        self._lim_sec.setVisible(is_classic)
        # Multi-zone editor
        self._zones_sec.setVisible(style == "multi_zone")
        # Multi-group editor
        self._groups_sec.setVisible(style == "multi_group")

    def _on_spec_edited(self) -> None:
        # Any change to the editor contents invalidates previously drawn
        # NF bands / lines.  The actual redraw happens on Run.
        self.dock._m1_invalidate_limit_lines()

    # ================================================================
    #  Run
    # ================================================================
    def run(self) -> None:
        """Run NACD-only evaluation on selected offsets.

        Behaviour depends on the active view style:

        * **classic** — the historical single-threshold path.  Filter
          chosen from the user's range + offset selection:
          * single offset + explicit range → ``contaminated = ~in_range``;
          * otherwise → ``contaminated = (NACD < thr)``
            (Rahimi et al. 2022).
        * **multi_zone** / **multi_group** — the user-configured
          :class:`NACDZoneSpec` drives both the point coloring (in
          ``multi_zone``) and the Limit Lines tree population.  The
          classical ``(NACD < thr)`` mask is still computed (using the
          primary group's lowest-NACD level as the contamination
          threshold) so the Results tab / auto-select / delete flow
          keeps working.
        """
        dock = self.dock
        dock._clear_nf_overlays()
        dock._last_mode = "nacd"

        spec = self.current_spec()
        style = spec.style

        recv = self.array_positions()
        selected = get_selected_indices(self.offset_checks)
        if not selected:
            self.status.setText("Select at least one offset.")
            return

        if style != "classic" and not spec.groups:
            self.status.setText(
                "Configure at least one zone group, then Run again."
            )
            return

        from dc_cut.core.processing.nearfield.nacd import compute_nacd_array
        from dc_cut.core.processing.wavelength_lines import (
            parse_source_offset_from_label,
        )

        # Determine the contamination threshold used for the Results
        # tab's legacy binary mask.  In multi-zone mode we take the
        # lowest NACD threshold of the primary group as "below this is
        # contaminated"; in multi_group we take the global minimum.
        if style == "classic":
            thr = self.nacd_thr.value()
        else:
            all_nacds = [
                float(t.nacd)
                for g in spec.groups
                for t in g.thresholds
                if t.nacd > 0
            ]
            thr = min(all_nacds) if all_nacds else self.nacd_thr.value()

        single_offset = (len(selected) == 1)
        eval_range = (
            self.ranges_widget.get_range() if (single_offset and style == "classic")
            else EvaluationRange()
        )
        use_range_only = (
            style == "classic"
            and single_offset
            and not eval_range.is_empty()
        )

        results = []
        for idx in selected:
            f = np.asarray(dock.c.frequency_arrays[idx], float)
            v = np.asarray(dock.c.velocity_arrays[idx], float)
            w = np.asarray(dock.c.wavelength_arrays[idx], float)
            lbl = (
                dock.c.offset_labels[idx]
                if idx < len(dock.c.offset_labels)
                else f"Offset {idx}"
            )
            so = parse_source_offset_from_label(lbl)
            nacd = compute_nacd_array(recv, f, v, source_offset=so)
            in_range = compute_range_mask(f, v, eval_range)
            if use_range_only:
                mask = ~in_range
            else:
                mask = (nacd < thr)
            x_bar = float(np.mean(np.abs(recv - (so if so is not None else 0.0))))
            lam_max = x_bar / max(thr, 1e-12)
            n_contam = int(np.sum(mask))

            entry = {
                "label": lbl,
                "offset_index": idx,
                "source_offset": so,
                "x_bar": x_bar,
                "lambda_max": lam_max,
                "n_total": len(f),
                "n_contaminated": n_contam,
                "n_clean": len(f) - n_contam,
                "clean_pct": 100.0 * (len(f) - n_contam) / max(len(f), 1),
                "contam_pct": 100.0 * n_contam / max(len(f), 1),
                "f": f, "v": v, "w": w, "nacd": nacd, "mask": mask,
            }

            # ── Point coloring ────────────────────────────────
            if style == "multi_zone" and spec.groups:
                primary = (spec.primary_group() or spec.groups[0]).normalised()
                zone_idx = classify_points_into_zones(
                    nacd, primary.sorted_thresholds(),
                )
                colors = self._zone_colors_for_points(primary, zone_idx)
                draw_nacd_overlay_colored(dock.c, idx, f, v, w, colors)
                entry["zone_idx"] = zone_idx.tolist()
            elif style == "classic":
                # Classic path keeps the binary clean / contaminated
                # scatter overlay the users have relied on.
                draw_nacd_overlay(
                    dock.c, idx, f, v, w, mask, dock._mode1_colors,
                )
            # style == "multi_group" intentionally skips any scatter
            # recoloring — the user asked for lines + background
            # zone tints only, leaving the existing peak colors
            # untouched.

            results.append(entry)

        # ── Limit Lines tab population ────────────────────────────
        dock._limits.active_mode = "m1"
        clear_nf_limit_lines(dock._nf_limit_artists)
        dock._nf_limit_artists = []

        if style == "classic":
            if single_offset and not eval_range.is_empty():
                only_idx = selected[0]
                dock._limits.force_vf_idx = only_idx
                try:
                    dock._limits.rebuild_tree()
                finally:
                    dock._limits.force_vf_idx = None
            elif self.ranges_widget.show_lines() and results:
                from dc_cut.core.processing.nearfield.range_derivation import (
                    derive_limits_from_lambda_values,
                )
                lam_triples = []
                for r in results:
                    lam = float(r.get("lambda_max", 0.0))
                    if lam <= 0:
                        continue
                    f_arr = np.asarray(r.get("f", []), float)
                    v_arr = np.asarray(r.get("v", []), float)
                    lam_triples.append((lam, f_arr, v_arr))
                derived = derive_limits_from_lambda_values(lam_triples)
                dock._limits.rebuild_tree_with_set(
                    derived, hide_freq_by_default=True,
                )
        else:
            # Multi-zone / multi-group: build the DerivedLimitSet from
            # the spec using a representative x_bar and V(f) curve
            # (use the first evaluated offset as representative).
            first = results[0]
            x_bar_rep = float(first["x_bar"])
            f_rep = np.asarray(first["f"], float)
            v_rep = np.asarray(first["v"], float)
            derived = spec_to_derived_limit_set(
                spec, x_bar_rep, f_rep, v_rep,
            )
            dock._limits.rebuild_tree_with_set(
                derived, hide_freq_by_default=False,
            )

            # Cache enough to re-render zone bands / labels on
            # subsequent Limit Lines tree edits without re-running.
            self._last_spec = spec
            self._last_x_bar = x_bar_rep
            self._last_f_rep = f_rep
            self._last_v_rep = v_rep
            self._ensure_limits_wired()

            self._redraw_zone_overlays()

        dock._last_batch = results
        dock._overlay_offsets = selected
        dock._results_tab.populate_batch_table(results)
        dock._results_tab.populate_inspect_combo(results)
        dock._tabs.setCurrentIndex(3)

        n_total = sum(r["n_total"] for r in results)
        n_contam = sum(r["n_contaminated"] for r in results)
        if style == "classic":
            self.status.setText(
                f"Evaluated {len(results)} offset(s), {n_total} points. "
                f"{n_contam} contaminated."
            )
        else:
            n_thr = sum(len(g.thresholds) for g in spec.groups)
            n_zones = sum(
                len(g.thresholds) + 1 for g in spec.groups if g.thresholds
            )
            self.status.setText(
                f"Evaluated {len(results)} offset(s), {n_total} points "
                f"across {n_zones} zone(s) / {n_thr} NACD threshold(s) "
                f"in {len(spec.groups)} group(s)."
            )

        derived_set = dock._limits.current_derived_set
        dock._publish_nf_results(
            mode="nacd",
            results=results,
            eval_range=eval_range,
            derived_set=derived_set,
        )

    # ================================================================
    #  Zone overlay redraw (shared by Run + Limit Lines state edits)
    # ================================================================
    def _ensure_limits_wired(self) -> None:
        """Subscribe to Limit Lines state changes once."""
        if self._limits_wired:
            return
        try:
            self.dock._limits.tab.state_changed.connect(
                self._on_limits_state_changed
            )
            self._limits_wired = True
        except Exception:
            pass

    def _zone_state_from_tree(self) -> tuple:
        """Return ``(visible_keys, color_overrides)`` for zones.

        Keys are ``(group_index, zone_index)``.  Missing entries mean
        "default" — zone visible, band color taken from the spec.
        """
        from dc_cut.core.processing.nearfield.nacd_zones import (
            ZONE_BAND_INDEX_OFFSET,
        )
        visible: dict = {}
        colors: dict = {}
        try:
            state = self.dock._limits.current_state()
        except Exception:
            return visible, colors
        if not state:
            return visible, colors
        # Visibility entries.
        for key, vis in state.visible.items():
            try:
                bi, kind, role = key
            except Exception:
                continue
            if kind != "zone" or not role.startswith("z"):
                continue
            gi = int(bi) - ZONE_BAND_INDEX_OFFSET
            try:
                zi = int(role[1:])
            except ValueError:
                continue
            visible[(gi, zi)] = bool(vis)
        # Explicit color overrides.
        for key, col in state.colors.items():
            try:
                bi, kind, role = key
            except Exception:
                continue
            if kind != "zone" or not role.startswith("z") or not col:
                continue
            gi = int(bi) - ZONE_BAND_INDEX_OFFSET
            try:
                zi = int(role[1:])
            except ValueError:
                continue
            colors[(gi, zi)] = str(col)
        return visible, colors

    def _redraw_zone_overlays(self) -> None:
        """Paint zone bands + labels from the cached spec + tree state.

        Clears any previous zone artists first so this can be called
        on every Limit Lines edit.
        """
        from dc_cut.gui.widgets.nf_zone_bands import clear_nf_zone_artists

        dock = self.dock
        clear_nf_zone_artists(dock._nf_zone_artists)

        spec = self._last_spec
        if spec is None or spec.is_classic() or not spec.groups:
            try:
                dock.c.fig.canvas.draw_idle()
            except Exception:
                pass
            return

        lam_lim = dock.c.ax_wave.get_xlim()
        f_lim = dock.c.ax_freq.get_xlim()
        bands = spec_to_zone_bands(
            spec, self._last_x_bar,
            f_curve=self._last_f_rep,
            v_curve=self._last_v_rep,
            f_axis_min=float(f_lim[0]),
            f_axis_max=float(f_lim[1]),
            lambda_axis_min=float(lam_lim[0]),
            lambda_axis_max=float(lam_lim[1]),
        )
        visible, colors = self._zone_state_from_tree()
        dock._nf_zone_artists.extend(
            draw_zone_bands(
                dock.c.ax_freq, dock.c.ax_wave, bands,
                visible_keys=visible, color_overrides=colors,
            )
        )
        dock._nf_zone_artists.extend(
            draw_zone_labels(
                dock.c.ax_freq, dock.c.ax_wave, bands,
                visible_keys=visible, color_overrides=colors,
            )
        )
        try:
            dock.c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _on_limits_state_changed(self) -> None:
        """Limit Lines tab emitted ``state_changed`` — redraw zones."""
        if self._last_spec is None:
            return
        self._redraw_zone_overlays()

    # ================================================================
    #  Helpers
    # ================================================================
    def _zone_colors_for_points(
        self,
        group: ZoneGroup,
        zone_idx: np.ndarray,
    ) -> List[str]:
        """Return one hex color per pick based on its zone index.

        Uses :attr:`ZoneFill.point_color` of ``zones[zone_idx]``.
        When a zone does not have a point color configured, we fall
        through to the mode1 "clean" / "contaminated" palette so the
        scatter is never invisible: zone 0 reads as contaminated, the
        top zone as clean, and middle zones reuse the contaminated
        palette (user can always override per-zone).
        """
        g = group.normalised()
        zones = list(g.zones)
        n_zones = len(zones)
        n_last = max(0, n_zones - 1)
        colors: List[str] = []
        for z in np.asarray(zone_idx, int).tolist():
            z_clamped = max(0, min(int(z), n_last))
            if zones and zones[z_clamped].point_color:
                colors.append(zones[z_clamped].point_color)
            else:
                if z_clamped == n_last and n_zones > 1:
                    colors.append(self.dock._mode1_colors["clean"])
                else:
                    colors.append(self.dock._mode1_colors["contaminated"])
        return colors


__all__ = ["NacdTab"]
