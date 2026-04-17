"""Limit-lines tab coordinator.

Owns the :class:`NFLimitsTab` widget, the two per-mode
:class:`LimitsLineState` objects, and the drawing pipeline that maps
the active :class:`DerivedLimitSet` onto the frequency / wavelength
axes.  Lives as a plain ``object`` (not a QWidget): it adds behaviour
to the dock without creating a second widget tree.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from dc_cut.core.processing.nearfield.range_derivation import (
    DerivedLimitSet,
    derive_limits,
)
from dc_cut.core.processing.nearfield.ranges import EvaluationRange
from dc_cut.gui.views.nf_limits_tab import NFLimitsTab, LimitsLineState
from dc_cut.gui.widgets.nf_limit_lines import (
    clear_nf_limit_lines,
    draw_nf_limits_from_set,
)


class LimitsCoordinator:
    """Encapsulate the Limit Lines tab + its drawing coordination."""

    def __init__(self, dock) -> None:
        self.dock = dock
        self.tab = NFLimitsTab()
        self.state_m1 = LimitsLineState()
        self.state_m2 = LimitsLineState()
        self.active_mode = "m1"  # 'm1' (NACD) or 'm2' (Reference)
        # NACD-Only: pin V(f) derivation to this offset when set.
        self.force_vf_idx: Optional[int] = None
        self.current_derived_set: Optional[DerivedLimitSet] = None
        self.tab.state_changed.connect(self._on_state_changed)

    # ---- state helpers -------------------------------------------------
    def current_state(self) -> LimitsLineState:
        return self.state_m2 if self.active_mode == "m2" else self.state_m1

    def current_eval_range(self) -> EvaluationRange:
        if self.active_mode == "m2":
            return self.dock._m2_ranges.get_range()
        return self.dock._m1_ranges.get_range()

    def get_vf_curve(self):
        """Return ``(f, v)`` used for cross-domain derivation."""
        dock = self.dock
        if self.active_mode == "m2" and dock.eval.has_reference:
            return dock.eval._reference_f, dock.eval._reference_v
        idx = self.force_vf_idx
        if idx is None and hasattr(dock.eval, "_current_idx"):
            idx = dock.eval._current_idx
        if idx is not None:
            try:
                f = np.asarray(dock.c.frequency_arrays[idx], float)
                v = np.asarray(dock.c.velocity_arrays[idx], float)
                return f, v
            except Exception:
                pass
        return None, None

    # ---- pipeline ------------------------------------------------------
    def rebuild_tree(self) -> None:
        """Recompute the DerivedLimitSet and refresh the tree + canvas."""
        eval_range = self.current_eval_range()
        f_curve, v_curve = self.get_vf_curve()
        self.current_derived_set = derive_limits(eval_range, f_curve, v_curve)
        self.tab.set_state(self.current_state())
        self.tab.refresh(self.current_derived_set)
        self.redraw_on_canvas()

    def rebuild_tree_with_set(
        self,
        derived: DerivedLimitSet,
        *,
        hide_freq_by_default: bool = False,
    ) -> None:
        """Install an already-computed :class:`DerivedLimitSet`.

        Used by the no-range run paths (NACD-Only and Reference) to
        publish ``λ``/``f`` lines derived directly from per-offset
        ``λ_max`` values so they appear in the Limit Lines tree.

        If ``hide_freq_by_default`` is true, every ``freq`` leaf in
        the set whose visibility hasn't been touched by the user yet
        is seeded to ``False`` — this is the behaviour requested for
        NACD-Only with no evaluation range, where the user wanted the
        ``f`` lines drawable (via the tree) but off at first sight.
        """
        self.current_derived_set = derived
        state = self.current_state()
        if hide_freq_by_default and derived is not None:
            for ln in derived.lines:
                if ln.kind != "freq":
                    continue
                leaf_key = (ln.band_index, "freq", ln.role)
                # Only seed the first time we see this key; never
                # overwrite an explicit user choice.
                if leaf_key not in state.visible:
                    state.visible[leaf_key] = False
        if self.active_mode == "m2":
            self.state_m2 = state
        else:
            self.state_m1 = state
        self.tab.set_state(state)
        self.tab.refresh(derived)
        self.redraw_on_canvas()

    def redraw_on_canvas(self) -> None:
        """Clear and redraw NF limit lines from the active DerivedLimitSet."""
        dock = self.dock
        clear_nf_limit_lines(dock._nf_limit_artists)
        limit_set = self.current_derived_set
        if limit_set is None or not limit_set.lines:
            try:
                dock.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return
        active_ranges_widget = (
            dock._m2_ranges if self.active_mode == "m2" else dock._m1_ranges
        )
        if not active_ranges_widget.show_lines():
            try:
                dock.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return
        state = self.current_state()
        if not state.show_all:
            try:
                dock.c.ax_freq.figure.canvas.draw_idle()
            except Exception:
                pass
            return

        def _style(key):
            # Visibility is driven PURELY by the per-leaf flag.  Band
            # and group rows exist only as visual aggregators; when
            # the user clicks them the tab propagates the new state
            # into every leaf beneath, so reading the leaf here is
            # enough.  (This fixes the earlier "one leaf toggles
            # everything" bug caused by Qt auto-tristate writing
            # PartiallyChecked into the parent's stored visibility.)
            if not state.get_visible(key, True):
                return False, "#000000"
            group_key = (key[0], key[1], "group")
            band_key = (key[0], "band", "band")
            color = state.get_color(key, default="")
            if not color:
                color = state.get_color(
                    group_key,
                    default=state.get_color(band_key, default=""),
                )
            if not color:
                from dc_cut.gui.views.nf_limits_tab import default_band_color
                color = default_band_color(key[0])
            return True, color

        dock._nf_limit_artists = draw_nf_limits_from_set(
            dock.c.ax_freq, dock.c.ax_wave,
            limit_set, style_fn=_style,
        )

    # ---- event hooks ---------------------------------------------------
    def on_top_tab_changed(self, idx: int) -> None:
        """Remember which mode is active for the Limit Lines tab."""
        # Tab order: 0 NACD, 1 Reference, 2 Limit Lines, 3 Results.
        if idx == 0:
            self.active_mode = "m1"
        elif idx == 1:
            self.active_mode = "m2"
        if idx == 2:
            # Tab switching is pure navigation: re-sync the tab widget
            # with whatever DerivedLimitSet is already installed, but
            # NEVER re-derive from the range.  Re-deriving on tab
            # change used to clobber the multi-band λ-only set that
            # NacdTab/ReferenceTab install via ``rebuild_tree_with_set``
            # (no-range runs) whenever the range widget still held a
            # stale single-offset band.  If the user wants fresh lines
            # they click Run.
            self.tab.set_state(self.current_state())
            self.tab.refresh(self.current_derived_set)
            self.redraw_on_canvas()

    def _on_state_changed(self) -> None:
        """React to visibility/color edits made in the Limit Lines tab."""
        new_state = self.tab.state()
        if self.active_mode == "m2":
            self.state_m2 = new_state
        else:
            self.state_m1 = new_state
        self.redraw_on_canvas()
        try:
            self.dock._save_range_prefs()
        except Exception:
            pass

    # ---- mode shortcuts ------------------------------------------------
    def redraw_m1_for_current_range(self) -> None:
        self.active_mode = "m1"
        self.rebuild_tree()

    def redraw_m2_for_current_range(self) -> None:
        self.active_mode = "m2"
        self.rebuild_tree()

    def invalidate_m1(self) -> None:
        """Clear M1 limit-line artists and the derived set.

        Called when the user edits the range (before Run) or toggles
        the offset selection.
        """
        dock = self.dock
        try:
            clear_nf_limit_lines(dock._nf_limit_artists)
            dock._nf_limit_artists = []
        except Exception:
            pass
        if self.active_mode == "m1":
            try:
                self.current_derived_set = None
                self.tab.refresh(None)
            except Exception:
                pass
        try:
            dock.c.ax_freq.figure.canvas.draw_idle()
        except Exception:
            pass


__all__ = ["LimitsCoordinator"]
