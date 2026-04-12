"""
Qt5 / Qt6 compatibility layer — single source of truth.

Every module in report_studio imports Qt objects from here, never directly.
"""

from matplotlib.backends.qt_compat import QtWidgets, QtCore, QtGui

# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------
try:
    from PySide6.QtCore import Signal
except ImportError:
    try:
        from PyQt6.QtCore import pyqtSignal as Signal
    except ImportError:
        try:
            from PySide2.QtCore import Signal
        except ImportError:
            from PyQt5.QtCore import pyqtSignal as Signal

# ---------------------------------------------------------------------------
# Orientation
# ---------------------------------------------------------------------------
Horizontal = QtCore.Qt.Orientation.Horizontal if hasattr(QtCore.Qt, "Orientation") else QtCore.Qt.Horizontal
Vertical = QtCore.Qt.Orientation.Vertical if hasattr(QtCore.Qt, "Orientation") else QtCore.Qt.Vertical

# ---------------------------------------------------------------------------
# QDialog.Accepted / Rejected
# ---------------------------------------------------------------------------
try:
    DialogAccepted = QtWidgets.QDialog.DialogCode.Accepted
    DialogRejected = QtWidgets.QDialog.DialogCode.Rejected
except AttributeError:
    DialogAccepted = QtWidgets.QDialog.Accepted
    DialogRejected = QtWidgets.QDialog.Rejected

# ---------------------------------------------------------------------------
# QSizePolicy
# ---------------------------------------------------------------------------
try:
    PolicyMinimum = QtWidgets.QSizePolicy.Policy.Minimum
    PolicyPreferred = QtWidgets.QSizePolicy.Policy.Preferred
    PolicyExpanding = QtWidgets.QSizePolicy.Policy.Expanding
    PolicyFixed = QtWidgets.QSizePolicy.Policy.Fixed
except AttributeError:
    PolicyMinimum = QtWidgets.QSizePolicy.Minimum
    PolicyPreferred = QtWidgets.QSizePolicy.Preferred
    PolicyExpanding = QtWidgets.QSizePolicy.Expanding
    PolicyFixed = QtWidgets.QSizePolicy.Fixed

# ---------------------------------------------------------------------------
# QAbstractItemView enums (tree drag-drop)
# ---------------------------------------------------------------------------
try:
    NoEditTriggers = QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
except AttributeError:
    NoEditTriggers = QtWidgets.QAbstractItemView.NoEditTriggers

try:
    DragDrop = QtWidgets.QAbstractItemView.DragDropMode.DragDrop
except AttributeError:
    DragDrop = QtWidgets.QAbstractItemView.DragDrop

try:
    NoSelection = QtWidgets.QAbstractItemView.SelectionMode.NoSelection
    SingleSelection = QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
except AttributeError:
    NoSelection = QtWidgets.QAbstractItemView.NoSelection
    SingleSelection = QtWidgets.QAbstractItemView.SingleSelection

# ---------------------------------------------------------------------------
# Qt.ItemFlag (for tree items)
# ---------------------------------------------------------------------------
try:
    ItemIsEnabled = QtCore.Qt.ItemFlag.ItemIsEnabled
    ItemIsSelectable = QtCore.Qt.ItemFlag.ItemIsSelectable
    ItemIsUserCheckable = QtCore.Qt.ItemFlag.ItemIsUserCheckable
    ItemIsDragEnabled = QtCore.Qt.ItemFlag.ItemIsDragEnabled
    ItemIsDropEnabled = QtCore.Qt.ItemFlag.ItemIsDropEnabled
    ItemNeverHasChildren = QtCore.Qt.ItemFlag.ItemNeverHasChildren
except AttributeError:
    ItemIsEnabled = QtCore.Qt.ItemIsEnabled
    ItemIsSelectable = QtCore.Qt.ItemIsSelectable
    ItemIsUserCheckable = QtCore.Qt.ItemIsUserCheckable
    ItemIsDragEnabled = QtCore.Qt.ItemIsDragEnabled
    ItemIsDropEnabled = QtCore.Qt.ItemIsDropEnabled
    ItemNeverHasChildren = QtCore.Qt.ItemNeverHasChildren

# ---------------------------------------------------------------------------
# Qt.CheckState
# ---------------------------------------------------------------------------
try:
    Checked = QtCore.Qt.CheckState.Checked
    Unchecked = QtCore.Qt.CheckState.Unchecked
except AttributeError:
    Checked = QtCore.Qt.Checked
    Unchecked = QtCore.Qt.Unchecked

# ---------------------------------------------------------------------------
# Qt roles & alignment
# ---------------------------------------------------------------------------
try:
    UserRole = QtCore.Qt.ItemDataRole.UserRole
    DisplayRole = QtCore.Qt.ItemDataRole.DisplayRole
    CheckStateRole = QtCore.Qt.ItemDataRole.CheckStateRole
except AttributeError:
    UserRole = QtCore.Qt.UserRole
    DisplayRole = QtCore.Qt.DisplayRole
    CheckStateRole = QtCore.Qt.CheckStateRole

try:
    AlignLeft = QtCore.Qt.AlignmentFlag.AlignLeft
    AlignCenter = QtCore.Qt.AlignmentFlag.AlignCenter
    AlignRight = QtCore.Qt.AlignmentFlag.AlignRight
except AttributeError:
    AlignLeft = QtCore.Qt.AlignLeft
    AlignCenter = QtCore.Qt.AlignCenter
    AlignRight = QtCore.Qt.AlignRight

# ---------------------------------------------------------------------------
# Qt.MoveAction (drag-drop)
# ---------------------------------------------------------------------------
try:
    MoveAction = QtCore.Qt.DropAction.MoveAction
except AttributeError:
    MoveAction = QtCore.Qt.MoveAction

# ---------------------------------------------------------------------------
# DockWidget areas
# ---------------------------------------------------------------------------
try:
    LeftDockWidgetArea = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
    RightDockWidgetArea = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    BottomDockWidgetArea = QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
except AttributeError:
    LeftDockWidgetArea = QtCore.Qt.LeftDockWidgetArea
    RightDockWidgetArea = QtCore.Qt.RightDockWidgetArea
    BottomDockWidgetArea = QtCore.Qt.BottomDockWidgetArea

__all__ = [
    "QtWidgets", "QtCore", "QtGui", "Signal",
    "Horizontal", "Vertical",
    "DialogAccepted", "DialogRejected",
    "PolicyMinimum", "PolicyPreferred", "PolicyExpanding", "PolicyFixed",
    "NoEditTriggers", "DragDrop", "NoSelection", "SingleSelection",
    "ItemIsEnabled", "ItemIsSelectable", "ItemIsUserCheckable",
    "ItemIsDragEnabled", "ItemIsDropEnabled", "ItemNeverHasChildren",
    "Checked", "Unchecked",
    "UserRole", "DisplayRole", "CheckStateRole",
    "AlignLeft", "AlignCenter", "AlignRight",
    "MoveAction",
    "LeftDockWidgetArea", "RightDockWidgetArea", "BottomDockWidgetArea",
]
