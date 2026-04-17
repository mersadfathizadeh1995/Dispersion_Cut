"""Module-level constants and Qt5/Qt6 enum compatibility shims.

Extracted verbatim from :mod:`dc_cut.gui.views.nearfield_dock` so the
rest of the subpackage can import these without touching private
attributes on Qt classes directly.
"""
from __future__ import annotations

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore


# ── Qt5 / Qt6 enum compat ──────────────────────────────────────────
try:
    _UserRole = QtCore.Qt.UserRole
except AttributeError:
    _UserRole = QtCore.Qt.ItemDataRole.UserRole

try:
    _Checked = QtCore.Qt.Checked
    _Unchecked = QtCore.Qt.Unchecked
except AttributeError:
    _Checked = QtCore.Qt.CheckState.Checked
    _Unchecked = QtCore.Qt.CheckState.Unchecked

try:
    _ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemIsEnabled
except AttributeError:
    _ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    _ItemIsEnabled = QtCore.Qt.ItemFlag.ItemIsEnabled

try:
    _ItemIsEditable = QtCore.Qt.ItemIsEditable
except AttributeError:
    _ItemIsEditable = QtCore.Qt.ItemFlag.ItemIsEditable


# ── Default severity → colour mapping ───────────────────────────────
_DEFAULT_COLORS = {
    "clean": "#2196F3",          # blue (Mode 1) / green (Mode 2 override)
    "contaminated": "#F44336",   # red
    "marginal": "#FF9800",       # orange
    "unknown": "#9E9E9E",        # grey
}

_MODE1_COLORS = {
    "clean": "#2196F3",          # blue
    "contaminated": "#F44336",   # red
}

_MODE2_COLORS = {
    "clean": "#4CAF50",          # green
    "contaminated": "#F44336",   # red
    "marginal": "#FF9800",       # orange
    "unknown": "#9E9E9E",        # grey
}


__all__ = [
    "QtWidgets", "QtGui", "QtCore",
    "_UserRole", "_Checked", "_Unchecked",
    "_ItemIsUserCheckable", "_ItemIsEnabled", "_ItemIsEditable",
    "_DEFAULT_COLORS", "_MODE1_COLORS", "_MODE2_COLORS",
]
