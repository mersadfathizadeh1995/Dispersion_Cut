"""Common helpers shared across the NF-evaluation tabs.

Module-level functions extracted from the monolithic
:class:`NearFieldEvalDock`.  All functions are stateless or operate
on explicit arguments so tabs (and tests) can call them without
going through the dock.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from dc_cut.core.processing.nearfield.ranges import EvaluationRange

from .constants import QtGui, QtWidgets


def m2_user_lambda_max(eval_range: EvaluationRange) -> Optional[float]:
    """Effective ``user_lambda_max`` for V_R validity in Reference mode.

    Mirrors ``_resolve_user_lambda_max`` in
    :mod:`gui.controller.nf_inspector`: a non-empty range with no
    explicit \u03bb_max returns ``inf`` so the reference's own
    \u03bb-cap doesn't blank points the user asked about.
    """
    if eval_range is None or eval_range.is_empty():
        return None
    if eval_range.lambda_max is not None and eval_range.lambda_max > 0:
        return float(eval_range.lambda_max)
    return float(np.inf)


def make_color_button(
    dock,
    hex_color: str,
    severity_key: str,
    mode: int,
) -> QtWidgets.QPushButton:
    """Create a colored button that opens a color picker.

    Writes the chosen colour back into ``dock._mode1_colors`` or
    ``dock._mode2_colors`` so the caller only has to own the two
    dictionaries (the same contract as the legacy inline helper).
    """
    btn = QtWidgets.QPushButton()
    btn.setFixedSize(28, 22)
    btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")

    def _pick():
        chosen = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(hex_color), dock, f"Color for {severity_key}"
        )
        if chosen.isValid():
            new_hex = chosen.name()
            btn.setStyleSheet(
                f"background-color: {new_hex}; border: 1px solid #888;"
            )
            if mode == 1:
                dock._mode1_colors[severity_key] = new_hex
            else:
                dock._mode2_colors[severity_key] = new_hex

    btn.clicked.connect(_pick)
    return btn


def refresh_offset_checks(
    dock,
    checks_list: list,
    layout: QtWidgets.QVBoxLayout,
) -> None:
    """Rebuild offset checkboxes in ``layout``.

    Labels come from ``dock.c.offset_labels`` (clipped to the shorter
    of the velocity/frequency arrays).  When rebuilding the NACD-Only
    list (``dock._m1_offset_checks``) the per-checkbox toggle is
    wired into ``dock._m1_apply_range_gate`` and the gate is
    re-applied once.
    """
    for chk in checks_list:
        chk.setParent(None)
        chk.deleteLater()
    checks_list.clear()

    try:
        n = min(len(dock.c.velocity_arrays), len(dock.c.frequency_arrays))
        labels = list(dock.c.offset_labels[:n])
    except Exception:
        labels = []

    for lbl in labels:
        chk = QtWidgets.QCheckBox(lbl)
        chk.setChecked(True)
        layout.addWidget(chk)
        checks_list.append(chk)

    if checks_list is getattr(dock, "_m1_offset_checks", None):
        for chk in checks_list:
            try:
                chk.toggled.connect(dock._m1_apply_range_gate)
            except Exception:
                pass
        try:
            dock._m1_apply_range_gate()
        except Exception:
            pass


def set_all_offset_checks(dock, checks_list: list, checked: bool) -> None:
    """Check/uncheck every box, firing the NACD-Only gate if relevant."""
    for chk in checks_list:
        chk.setChecked(checked)
    if checks_list is getattr(dock, "_m1_offset_checks", None):
        try:
            dock._m1_apply_range_gate()
        except Exception:
            pass


def get_selected_indices(checks_list: list) -> List[int]:
    """Return indices of all checked boxes, in order."""
    return [i for i, chk in enumerate(checks_list) if chk.isChecked()]


def get_array_positions(n: int, dx: float, x0: float) -> np.ndarray:
    """Reproduce the geometry used by the legacy ``_get_array_positions``."""
    return np.arange(x0, x0 + dx * n, dx)


__all__ = [
    "m2_user_lambda_max",
    "make_color_button",
    "refresh_offset_checks",
    "set_all_offset_checks",
    "get_selected_indices",
    "get_array_positions",
]
