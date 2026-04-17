"""Preference persistence for the NF evaluation dock.

These helpers encapsulate the ``load_prefs`` / ``save_prefs`` wiring
so the dock only hands itself (and its tabs) over; the functions read
from / write to the familiar widgets.
"""
from __future__ import annotations

from dc_cut.core.processing.nearfield.ranges import EvaluationRange
from dc_cut.gui.views.nf_limits_tab import LimitsLineState


def m1_load_geometry_prefs(dock) -> None:
    """Load geometry defaults (# receivers, dx) from prefs."""
    try:
        from dc_cut.services.prefs import load_prefs
        P = load_prefs()
        dock._m1_n_recv.setValue(int(P.get('default_n_phones', 24)))
        dock._m1_dx.setValue(float(P.get('default_receiver_dx', 2.0)))
    except Exception:
        pass


def load_dock_prefs(dock) -> None:
    """Restore evaluation-range widgets from prefs and wire auto-save.

    Mirrors the legacy ``NearFieldEvalDock._load_dock_prefs`` exactly:
    prefill ranges + show-lines + limits-state, then connect the save
    callbacks and the mode-specific redraw hooks.
    """
    try:
        from dc_cut.services.prefs import load_prefs
        P = load_prefs()
        m1_rng = EvaluationRange.from_dict(P.get("nf_m1_eval_range"))
        dock._m1_ranges.set_range(m1_rng)
        dock._m1_ranges.set_show_lines(
            bool(P.get("nf_m1_show_limit_lines", True))
        )
        m2_rng = EvaluationRange.from_dict(P.get("nf_m2_eval_range"))
        dock._m2_ranges.set_range(m2_rng)
        dock._m2_ranges.set_show_lines(
            bool(P.get("nf_m2_show_limit_lines", True))
        )
        dock._limits_state_m1 = LimitsLineState.from_dict(
            P.get("nf_limits_state_m1")
        )
        dock._limits_state_m2 = LimitsLineState.from_dict(
            P.get("nf_limits_state_m2")
        )
    except Exception:
        pass

    dock._m1_ranges.range_changed.connect(dock._save_range_prefs)
    dock._m1_ranges.show_lines_toggled.connect(dock._save_range_prefs)
    dock._m2_ranges.range_changed.connect(dock._save_range_prefs)
    dock._m2_ranges.show_lines_toggled.connect(dock._save_range_prefs)

    # NACD-Only: range edits only invalidate stale lines -- no live
    # redraw (lines are owned by Run).
    dock._m1_ranges.range_changed.connect(dock._m1_invalidate_limit_lines)
    dock._m1_ranges.show_lines_toggled.connect(
        lambda _c: dock._m1_invalidate_limit_lines()
    )

    # Reference mode: limit lines follow the reference curve so we can
    # redraw live on every range edit.
    dock._m2_ranges.range_changed.connect(
        dock._redraw_m2_limits_for_current_range
    )
    dock._m2_ranges.show_lines_toggled.connect(
        lambda _checked: dock._redraw_m2_limits_for_current_range()
    )


def save_range_prefs(dock) -> None:
    """Persist both evaluation-range widgets + limits state to user prefs."""
    try:
        from dc_cut.services.prefs import load_prefs, save_prefs
        prefs = load_prefs()
        prefs["nf_m1_eval_range"] = dock._m1_ranges.get_range().to_dict()
        prefs["nf_m1_show_limit_lines"] = dock._m1_ranges.show_lines()
        prefs["nf_m2_eval_range"] = dock._m2_ranges.get_range().to_dict()
        prefs["nf_m2_show_limit_lines"] = dock._m2_ranges.show_lines()
        try:
            prefs["nf_limits_state_m1"] = dock._limits_state_m1.to_dict()
            prefs["nf_limits_state_m2"] = dock._limits_state_m2.to_dict()
        except Exception:
            pass
        save_prefs(prefs)
    except Exception:
        pass


__all__ = ["m1_load_geometry_prefs", "load_dock_prefs", "save_range_prefs"]
