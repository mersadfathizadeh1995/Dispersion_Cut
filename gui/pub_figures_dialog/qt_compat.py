"""Qt version compatibility helpers."""

from __future__ import annotations

from matplotlib.backends import qt_compat

QtCore = qt_compat.QtCore
QtWidgets = qt_compat.QtWidgets

# Qt version compatibility helpers
def _get_qt_orientation_horizontal():
    """Get Qt.Horizontal with version compatibility."""
    try:
        return QtCore.Qt.Orientation.Horizontal  # Qt6
    except AttributeError:
        return QtCore.Qt.Horizontal  # Qt5


def _get_qt_align_top():
    """Get Qt.AlignTop with version compatibility."""
    try:
        return QtCore.Qt.AlignmentFlag.AlignTop  # Qt6
    except AttributeError:
        return QtCore.Qt.AlignTop  # Qt5


def _get_qt_user_role():
    """Get Qt.UserRole with version compatibility."""
    try:
        return QtCore.Qt.ItemDataRole.UserRole  # Qt6
    except AttributeError:
        return QtCore.Qt.UserRole  # Qt5


def _get_qt_item_is_selectable():
    """Get Qt.ItemIsSelectable with version compatibility."""
    try:
        return QtCore.Qt.ItemFlag.ItemIsSelectable  # Qt6
    except AttributeError:
        return QtCore.Qt.ItemIsSelectable  # Qt5


def _get_qt_item_is_enabled():
    """Get Qt.ItemIsEnabled with version compatibility."""
    try:
        return QtCore.Qt.ItemFlag.ItemIsEnabled  # Qt6
    except AttributeError:
        return QtCore.Qt.ItemIsEnabled  # Qt5


def _get_qt_item_is_user_checkable():
    """Get Qt.ItemIsUserCheckable with version compatibility."""
    try:
        return QtCore.Qt.ItemFlag.ItemIsUserCheckable  # Qt6
    except AttributeError:
        return QtCore.Qt.ItemIsUserCheckable  # Qt5


def _get_qt_checked():
    """Get Qt.Checked with version compatibility."""
    try:
        return QtCore.Qt.CheckState.Checked  # Qt6
    except AttributeError:
        return QtCore.Qt.Checked  # Qt5


def _get_qt_unchecked():
    """Get Qt.Unchecked with version compatibility."""
    try:
        return QtCore.Qt.CheckState.Unchecked  # Qt6
    except AttributeError:
        return QtCore.Qt.Unchecked  # Qt5


def _get_qt_extended_selection():
    """Get QAbstractItemView.ExtendedSelection with version compatibility."""
    try:
        return QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection  # Qt6
    except AttributeError:
        return QtWidgets.QAbstractItemView.ExtendedSelection  # Qt5


def _get_qt_msgbox_yes():
    """Get QMessageBox.Yes with version compatibility."""
    try:
        return QtWidgets.QMessageBox.StandardButton.Yes  # Qt6
    except AttributeError:
        return QtWidgets.QMessageBox.Yes  # Qt5


def _get_qt_msgbox_no():
    """Get QMessageBox.No with version compatibility."""
    try:
        return QtWidgets.QMessageBox.StandardButton.No  # Qt6
    except AttributeError:
        return QtWidgets.QMessageBox.No  # Qt5


# Figure type definitions organized by category

