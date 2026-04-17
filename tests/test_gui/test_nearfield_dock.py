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
    from dc_cut.gui.views.nearfield_dock_new import NearFieldEvalDock
    ctrl = _build_mock_controller()
    return NearFieldEvalDock(ctrl)


# ---------------------------------------------------------------------
#  Tests
# ---------------------------------------------------------------------
def test_import_alias(qt_app):
    from dc_cut.gui.views.nearfield_dock_new import (
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
    from dc_cut.gui.views.nearfield_dock_new.common import refresh_offset_checks
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
    from dc_cut.gui.views.nearfield_dock_new import NearFieldEvalDock
    from dc_cut.gui.views.nearfield_dock_new.prefs_io import save_range_prefs

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
