"""Headless smoke tests for the refactored NF Evaluation dock.

Each test constructs the dock against a lightweight mock controller
using the Qt ``offscreen`` platform so no display is required.  The
assertions cover every checklist item in the refactor plan:

* Import + alias parity with the old module
* Four-tab layout in the correct order
* NACD-Only range-editor gate (single vs. multi offset)
* Deferred limit-line drawing (no artists before Run)
* Reference derivation via ``derive_limits`` with a synthetic V(f)
* Prefs round-trip for evaluation ranges
* Backward-compat shim properties resolve to the new widgets
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets


# ---------------------------------------------------------------------
#  Fixtures
# ---------------------------------------------------------------------
@pytest.fixture(scope="session")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def _build_mock_controller():
    """A minimal controller the dock can drive without a real app."""
    n_pts = 20
    f = np.linspace(5.0, 50.0, n_pts)
    v = np.linspace(300.0, 600.0, n_pts)
    w = v / f
    fig, (ax_f, ax_w) = plt.subplots(1, 2)
    mock_eval = SimpleNamespace(
        has_reference=False,
        _reference_f=None, _reference_v=None, _reference_source="",
        _lambda_max_ref=100.0,
        _clean_threshold=0.95, _marginal_threshold=0.85,
        _unknown_action="treat_as_unknown",
        _vr_onset_threshold=0.90,
        _current_idx=0,
        thr=1.0,
        compute_reference_from_offsets=lambda *a, **k: None,
        load_reference_file=lambda p: None,
        evaluate_all_offsets=lambda eval_range=None: [],
        start_with=lambda lbl, t: None,
        get_current_arrays=lambda eval_range=None: None,
        set_source_type=lambda st: None,
        set_reference_curve=lambda *a: None,
        apply_deletions=lambda idx: None,
        cancel=lambda: None,
        compute_full_report=lambda: {},
    )
    return SimpleNamespace(
        nf_evaluator=mock_eval,
        ax_freq=ax_f, ax_wave=ax_w, fig=fig,
        frequency_arrays=[f, f, f],
        velocity_arrays=[v, v, v],
        wavelength_arrays=[w, w, w],
        offset_labels=["Offset 1.0", "Offset 3.0", "Offset 5.0"],
        nacd_thresh=1.0,
        _nf_reference_f=None, _nf_reference_v=None, _nf_reference_source="",
    )


def _isolate_prefs(tmp_path, monkeypatch):
    """Point the prefs loader at a tmp-dir JSON so tests don't collide."""
    from dc_cut.services import prefs as prefs_mod
    fake_prefs_file = str(tmp_path / "prefs.json")
    monkeypatch.setattr(prefs_mod, "_prefs_path", lambda: fake_prefs_file)
    return fake_prefs_file


@pytest.fixture
def dock(qt_app, tmp_path, monkeypatch):
    _isolate_prefs(tmp_path, monkeypatch)
    from dc_cut.gui.views.nearfield_dock import NearFieldEvalDock
    ctrl = _build_mock_controller()
    return NearFieldEvalDock(ctrl)


# ---------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------
def test_import_alias(qt_app):
    from dc_cut.gui.views.nearfield_dock import (
        NearFieldEvalDock,
        NearFieldAnalysisDock,
    )
    assert NearFieldEvalDock is NearFieldAnalysisDock


def test_four_tabs_in_order(dock):
    titles = [dock._tabs.tabText(i) for i in range(dock._tabs.count())]
    assert titles == ["NACD-Only", "Reference", "Limit Lines", "Results"]


def test_backward_compat_shims(dock):
    # NACD-Only
    assert dock._m1_ranges is dock._nacd_tab.ranges_widget
    assert dock._m1_offset_layout is dock._nacd_tab.offset_layout
    assert dock._m1_nacd_thr is dock._nacd_tab.nacd_thr
    # Reference
    assert dock._m2_ranges is dock._reference_tab.ranges_widget
    assert dock._m2_ref_combo is dock._reference_tab.ref_combo
    assert dock._m2_offset_layout is dock._reference_tab.offset_layout
    # Results
    assert dock._batch_table is dock._results_tab.batch_table
    assert dock._points_table is dock._results_tab.points_table
    assert dock._inspect_combo is dock._results_tab.inspect_combo
    # Limits
    assert dock._limits_tab is dock._limits.tab
    # Attribute setters through shims propagate.
    dock._active_limits_mode = "m2"
    assert dock._limits.active_mode == "m2"
    dock._m1_force_vf_idx = 7
    assert dock._limits.force_vf_idx == 7


def test_range_gate_single_vs_multi(dock):
    from dc_cut.gui.views.nearfield_dock.common import refresh_offset_checks
    refresh_offset_checks(
        dock, dock._nacd_tab.offset_checks, dock._nacd_tab.offset_layout
    )
    assert len(dock._m1_offset_checks) == 3
    # Default: everything checked -> gate OFF.
    dock._m1_apply_range_gate()
    assert dock._m1_ranges._table.isEnabled() is False
    # Single offset selected -> gate ON.
    for i, chk in enumerate(dock._m1_offset_checks):
        chk.setChecked(i == 0)
    dock._m1_apply_range_gate()
    assert dock._m1_ranges._table.isEnabled() is True


def test_limit_lines_are_deferred_until_run(dock):
    """Editing the range alone must not draw limit-line artists."""
    assert dock._nf_limit_artists == []
    # Pretend the user adds a frequency band; invalidation must keep
    # the list empty (no auto-draw).
    dock._m1_invalidate_limit_lines()
    assert dock._nf_limit_artists == []


def test_reference_derivation_with_synthetic_vf(qt_app):
    from dc_cut.core.processing.nearfield.range_derivation import derive_limits
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    f = np.linspace(1.0, 100.0, 500)
    v = np.full_like(f, 500.0)  # flat V -> lambda = V/f
    rng = EvaluationRange(freq_bands=[(5.0, 25.0)])
    limit_set = derive_limits(rng, f, v)
    # Expect one band; pluck its derived-λ limits and confirm magnitudes.
    lambdas = [ln.value for ln in limit_set.lambda_lines(valid_only=False)]
    assert lambdas, f"no derived lambdas: {limit_set.lines}"
    # With flat V=500 and f in [5, 25], we expect lambdas in {20, 100}.
    lo, hi = min(lambdas), max(lambdas)
    assert lo == pytest.approx(20.0, rel=0.05)
    assert hi == pytest.approx(100.0, rel=0.05)


def test_prefs_round_trip(qt_app, tmp_path, monkeypatch):
    _isolate_prefs(tmp_path, monkeypatch)
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock import NearFieldEvalDock
    from dc_cut.gui.views.nearfield_dock.prefs_io import save_range_prefs

    ctrl = _build_mock_controller()
    dock = NearFieldEvalDock(ctrl)
    # Configure something distinctive and persist it.
    dock._m1_ranges.set_range(EvaluationRange(freq_bands=[(7.0, 22.0)]))
    save_range_prefs(dock)

    # Rebuild a fresh dock and confirm the band came back.
    ctrl2 = _build_mock_controller()
    dock2 = NearFieldEvalDock(ctrl2)
    rng = dock2._m1_ranges.get_range()
    assert rng.freq_bands == [(7.0, 22.0)]


def test_showEvent_refreshes_offsets(dock):
    # Force a show event and verify the offset columns populated.
    dock.show()
    dock.hide()
    assert len(dock._m1_offset_checks) == 3
    assert len(dock._m2_offset_checks) == 3
    # NACD-Only default is opt-in (all boxes unchecked so the user has
    # to pick at least one offset before running).
    assert all(not chk.isChecked() for chk in dock._m1_offset_checks)


def test_collapsible_section_size_policy_toggles(qt_app):
    """When closed, a CollapsibleSection must stop claiming vertical
    stretch from its parent layout — otherwise it leaves a big empty
    hole between the header and the section below it."""
    from dc_cut.gui.widgets.collapsible_section import CollapsibleSection

    try:
        ExpandingV = QtWidgets.QSizePolicy.Policy.Expanding
        MaximumV = QtWidgets.QSizePolicy.Policy.Maximum
    except AttributeError:
        ExpandingV = QtWidgets.QSizePolicy.Expanding
        MaximumV = QtWidgets.QSizePolicy.Maximum

    sec = CollapsibleSection("x", initially_expanded=True)
    assert sec.sizePolicy().verticalPolicy() == ExpandingV
    sec.set_expanded(False)
    assert sec.sizePolicy().verticalPolicy() == MaximumV
    sec.set_expanded(True)
    assert sec.sizePolicy().verticalPolicy() == ExpandingV


def test_limits_tab_leaf_toggle_does_not_hide_whole_band(qt_app):
    """Toggling a single leaf off must NOT hide the band's other
    lines.  Regression test for the old auto-tristate behaviour that
    wrote ``PartiallyChecked`` into the parent's stored visibility.
    """
    from dc_cut.core.processing.nearfield.range_derivation import (
        DerivedLimitSet, DerivedLine,
    )
    from dc_cut.gui.views.nf_limits_tab import NFLimitsTab

    ds = DerivedLimitSet(lines=[
        DerivedLine(band_index=0, kind="lambda", role="min", value=5.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="lambda", role="max", value=50.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="freq", role="min", value=7.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="freq", role="max", value=20.0,
                    source="user", valid=True),
    ])
    tab = NFLimitsTab()
    tab.refresh(ds)

    # Find and uncheck the leaf for (0, 'freq', 'max').
    from matplotlib.backends import qt_compat
    QtCore = qt_compat.QtCore
    try:
        _Unchecked = QtCore.Qt.Unchecked
        _Checked = QtCore.Qt.Checked
    except AttributeError:
        _Unchecked = QtCore.Qt.CheckState.Unchecked
        _Checked = QtCore.Qt.CheckState.Checked

    target_key = (0, "freq", "max")
    found = False
    root = tab._tree
    for bi in range(root.topLevelItemCount()):
        band = root.topLevelItem(bi)
        for gi in range(band.childCount()):
            group = band.child(gi)
            for li in range(group.childCount()):
                leaf = group.child(li)
                if tuple(leaf.data(0, qt_compat.QtCore.Qt.UserRole)) == target_key:
                    leaf.setCheckState(0, _Unchecked)
                    found = True
    assert found, "f_max leaf not found"

    # State: exactly ONE key should be stored as False (the leaf we
    # unchecked); every other leaf's visibility must default to True.
    st = tab.state()
    assert st.get_visible((0, "freq", "max"), True) is False
    assert st.get_visible((0, "freq", "min"), True) is True
    assert st.get_visible((0, "lambda", "min"), True) is True
    assert st.get_visible((0, "lambda", "max"), True) is True
    # Parent keys must NOT leak into the persisted visibility store.
    assert (0, "band", "band") not in st.visible
    assert (0, "freq", "group") not in st.visible
    assert (0, "lambda", "group") not in st.visible


def test_limits_tab_band_toggle_propagates_to_all_leaves(qt_app):
    """Clicking a band checkbox must flip every leaf beneath it."""
    from dc_cut.core.processing.nearfield.range_derivation import (
        DerivedLimitSet, DerivedLine,
    )
    from dc_cut.gui.views.nf_limits_tab import NFLimitsTab
    from matplotlib.backends import qt_compat

    ds = DerivedLimitSet(lines=[
        DerivedLine(band_index=0, kind="lambda", role="min", value=5.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="lambda", role="max", value=50.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="freq", role="min", value=7.0,
                    source="user", valid=True),
        DerivedLine(band_index=0, kind="freq", role="max", value=20.0,
                    source="user", valid=True),
    ])
    tab = NFLimitsTab()
    tab.refresh(ds)

    QtCore = qt_compat.QtCore
    try:
        _Unchecked = QtCore.Qt.Unchecked
    except AttributeError:
        _Unchecked = QtCore.Qt.CheckState.Unchecked

    band_item = tab._tree.topLevelItem(0)
    band_item.setCheckState(0, _Unchecked)

    st = tab.state()
    for role in ("min", "max"):
        assert st.get_visible((0, "lambda", role), True) is False
        assert st.get_visible((0, "freq", role), True) is False


def test_nacd_run_single_offset_empty_range_does_not_crash(dock):
    """Regression test for the TypeError crash on NACD-Only runs with
    a single offset and no user-specified evaluation range.

    Previously the λ_max leaf was emitted as ``source="derived"``
    without a ``derived_from`` value, which made ``_add_leaf`` crash
    in ``f"{ln.derived_from:g}"``.  The fix marks the leaf
    ``source="user"`` and makes the formatter tolerant of a missing
    partner.  Together they must keep the tree populated instead of
    bubbling up a ``TypeError``.
    """
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock.common import refresh_offset_checks

    refresh_offset_checks(
        dock, dock._nacd_tab.offset_checks, dock._nacd_tab.offset_layout
    )
    for i, chk in enumerate(dock._m1_offset_checks):
        chk.setChecked(i == 0)
    dock._m1_ranges.set_range(EvaluationRange())  # empty → no range
    # Must not raise.
    dock._nacd_tab.run()
    # A single band should have been published to the Limit Lines tree.
    tree = dock._limits_tab._tree
    assert tree.topLevelItemCount() >= 1, (
        "Expected the Limit Lines tree to be populated with at least "
        "one band after a no-range NACD-Only run."
    )


def test_multi_offset_run_with_stale_range_gives_lambda_only_bands(dock):
    """Regression: running NACD-Only for MULTIPLE offsets must publish
    one λ-only band per offset to the Limit Lines tree, even if the
    range widget still contains a stale (f_lo, f_hi) band from a
    prior single-offset run.  After switching to the Limit Lines tab
    the tree must still reflect that λ-only set (not a single
    range-derived band that would replace everything with
    ``f_min=… Hz (user)`` / ``f_max=… Hz (user)`` entries).
    """
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock.common import refresh_offset_checks

    refresh_offset_checks(
        dock, dock._nacd_tab.offset_checks, dock._nacd_tab.offset_layout
    )
    # Leftover range from an earlier single-offset run.
    dock._m1_ranges.set_range(EvaluationRange(freq_bands=[(6.0, 25.0)]))
    # Select every offset (multi-offset path).
    for chk in dock._m1_offset_checks:
        chk.setChecked(True)
    dock._nacd_tab.run()

    ds = dock._limits.current_derived_set
    assert ds is not None and ds.lines, "multi-offset run produced no lines"
    # λ-only path: every emitted line is kind=='lambda' (there are no
    # freq-band lines since no user range was applied for multi-offset).
    # Each line's source must be 'user' (the λ_max value) or 'derived'
    # (the derived f_min partner, if present).  There should never be
    # a freq=='max' line, since derive_limits_from_lambda_values only
    # emits λ_max + f_min partners.
    kinds_roles = {(ln.kind, ln.role) for ln in ds.lines}
    assert ("freq", "max") not in kinds_roles, (
        "multi-offset NACD-Only must not install an f_max (user) line; "
        "the tree should stay λ-only (+ hidden f_min partners)."
    )

    # Tab switch must leave the set (and tree) intact.
    tree = dock._limits_tab._tree
    pre_count = tree.topLevelItemCount()
    dock._limits.on_top_tab_changed(2)
    post_count = dock._limits_tab._tree.topLevelItemCount()
    assert post_count == pre_count
    # And none of the freshly-displayed lines may be a user f_max.
    ds_after = dock._limits.current_derived_set
    assert ds_after is not None
    kinds_roles_after = {(ln.kind, ln.role) for ln in ds_after.lines}
    assert ("freq", "max") not in kinds_roles_after


def test_switching_to_limits_tab_preserves_no_range_set(dock):
    """Regression: after a no-range NACD-Only run, clicking the Limit
    Lines tab must NOT clobber the tree or wipe the canvas artists.

    The bug: ``on_top_tab_changed(2)`` unconditionally called
    ``rebuild_tree()``, which re-derives from the (empty) evaluation
    range and replaces the ``DerivedLimitSet`` that ``NacdTab.run()``
    just installed via ``rebuild_tree_with_set``.  The fix only
    auto-rebuilds when the current range is non-empty.
    """
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock.common import refresh_offset_checks

    refresh_offset_checks(
        dock, dock._nacd_tab.offset_checks, dock._nacd_tab.offset_layout
    )
    for i, chk in enumerate(dock._m1_offset_checks):
        chk.setChecked(i == 0)
    dock._m1_ranges.set_range(EvaluationRange())  # no range
    dock._nacd_tab.run()
    # Sanity: the no-range run populated the tree.
    assert dock._limits_tab._tree.topLevelItemCount() >= 1

    # Simulate the user switching to the Limit Lines tab.
    dock._limits.on_top_tab_changed(2)
    # The set must survive and so must the tree.
    assert dock._limits.current_derived_set is not None
    assert dock._limits.current_derived_set.lines, (
        "Limit Lines tab switch wiped the no-range DerivedLimitSet."
    )
    assert dock._limits_tab._tree.topLevelItemCount() >= 1


def test_nacd_run_range_only_when_single_offset_with_range(dock):
    """Single offset + non-empty evaluation range ⇒ mask must be
    driven by the range only (not the NACD < thr rule).  Multi-offset
    or empty-range runs must fall back to the NACD rule."""
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock.common import refresh_offset_checks

    refresh_offset_checks(
        dock, dock._nacd_tab.offset_checks, dock._nacd_tab.offset_layout
    )
    # Pick exactly one offset.
    for i, chk in enumerate(dock._m1_offset_checks):
        chk.setChecked(i == 0)
    # Give it a narrow band that excludes most of the data.
    f = np.asarray(dock.c.frequency_arrays[0], float)
    fmin, fmax = float(f.min()) + 5.0, float(f.max()) - 5.0
    dock._m1_ranges.set_range(EvaluationRange(freq_bands=[(fmin, fmax)]))
    # Run — should succeed and produce a single batch entry.
    dock._nacd_tab.run()
    assert len(dock._last_batch) == 1
    batch = dock._last_batch[0]
    mask = np.asarray(batch["mask"])
    # Range-only: every point flagged contaminated must be outside
    # the user's frequency band.
    outside = (f < fmin) | (f > fmax)
    assert np.array_equal(mask, outside), (
        "Range-only filter expected: every flagged point must lie "
        "outside the user's band."
    )
