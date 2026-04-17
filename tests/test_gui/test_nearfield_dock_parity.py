"""Parity verification between legacy ``nearfield_dock`` and the new
``nearfield_dock_new`` subpackage.

Run :meth:`_m1_run` on both implementations against an identical
synthetic controller and confirm the batch-result payload is
element-wise equal.  This is the single gate the swap relies on.
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


@pytest.fixture(scope="session")
def qt_app():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def _build_ctrl(seed: int = 0):
    rng = np.random.default_rng(seed)
    n_pts = 30
    f = np.linspace(3.0, 45.0, n_pts)
    # Synthetic, reproducible V(f): smooth decreasing curve + small jitter.
    v = 800.0 - 10.0 * f + rng.normal(scale=2.0, size=n_pts)
    w = v / f
    fig, (ax_f, ax_w) = plt.subplots(1, 2)
    mock_eval = SimpleNamespace(
        has_reference=False,
        _reference_f=None, _reference_v=None, _reference_source="",
        _lambda_max_ref=100.0,
        _clean_threshold=0.95, _marginal_threshold=0.85,
        _unknown_action="treat_as_unknown",
        _vr_onset_threshold=0.90,
        _current_idx=0, thr=1.0,
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
    from dc_cut.services import prefs as prefs_mod
    fake = str(tmp_path / "prefs.json")
    monkeypatch.setattr(prefs_mod, "_prefs_path", lambda: fake)


def _run_m1(dock, *, select_only=None):
    """Helper: fire `_m1_run` with a deterministic selection."""
    # Populate the offset checks the same way showEvent would.
    from dc_cut.gui.views.nearfield_dock_new.common import refresh_offset_checks
    refresh_offset_checks(
        dock, dock._m1_offset_checks, dock._m1_offset_layout
    )
    if select_only is not None:
        for i, chk in enumerate(dock._m1_offset_checks):
            chk.setChecked(i in select_only)
    # Trigger the run.
    dock._nacd_tab.run() if hasattr(dock, "_nacd_tab") else dock._m1_run()
    return dock._last_batch


def _run_m1_legacy(dock, *, select_only=None):
    """Legacy variant: populates offset checks via the dock method."""
    dock._refresh_offset_checks(dock._m1_offset_checks, dock._m1_offset_layout)
    if select_only is not None:
        for i, chk in enumerate(dock._m1_offset_checks):
            chk.setChecked(i in select_only)
    dock._m1_run()
    return dock._last_batch


def _compare_batches(b1, b2):
    assert len(b1) == len(b2), (len(b1), len(b2))
    for r1, r2 in zip(b1, b2):
        for key in ("label", "offset_index", "x_bar", "lambda_max",
                     "n_total", "n_contaminated", "n_clean",
                     "clean_pct", "contam_pct"):
            v1, v2 = r1[key], r2[key]
            if isinstance(v1, float):
                assert v1 == pytest.approx(v2, rel=1e-9, abs=1e-12), (
                    key, v1, v2
                )
            else:
                assert v1 == v2, (key, v1, v2)
        for key in ("f", "v", "w", "nacd", "mask"):
            np.testing.assert_array_equal(r1[key], r2[key])


def test_m1_run_parity_multi_offset(qt_app, tmp_path, monkeypatch):
    _isolate_prefs(tmp_path, monkeypatch)
    from dc_cut.gui.views.nearfield_dock import NearFieldEvalDock as Legacy
    from dc_cut.gui.views.nearfield_dock_new import NearFieldEvalDock as New

    ctrl_a = _build_ctrl(seed=42)
    ctrl_b = _build_ctrl(seed=42)
    old = Legacy(ctrl_a)
    new = New(ctrl_b)

    b_old = _run_m1_legacy(old, select_only=None)  # all offsets
    b_new = _run_m1(new, select_only=None)
    _compare_batches(b_old, b_new)


def test_m1_run_parity_single_offset_with_range(qt_app, tmp_path, monkeypatch):
    _isolate_prefs(tmp_path, monkeypatch)
    from dc_cut.core.processing.nearfield.ranges import EvaluationRange
    from dc_cut.gui.views.nearfield_dock import NearFieldEvalDock as Legacy
    from dc_cut.gui.views.nearfield_dock_new import NearFieldEvalDock as New

    ctrl_a = _build_ctrl(seed=7)
    ctrl_b = _build_ctrl(seed=7)
    old = Legacy(ctrl_a)
    new = New(ctrl_b)
    band = EvaluationRange(freq_bands=[(10.0, 30.0)])
    old._m1_ranges.set_range(band)
    new._m1_ranges.set_range(band)

    b_old = _run_m1_legacy(old, select_only=[1])
    b_new = _run_m1(new, select_only=[1])
    _compare_batches(b_old, b_new)
