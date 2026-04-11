"""Qt compatibility layer for the Report Studio.

Uses matplotlib's qt_compat to get whichever Qt binding is active
(PyQt5, PyQt6, PySide2, PySide6) instead of hard-coding PySide6.
Also provides Signal/Slot aliases and commonly needed Qt enum values
that differ between Qt5 and Qt6.
"""
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui

try:
    Signal = QtCore.Signal
except AttributeError:
    Signal = QtCore.pyqtSignal

try:
    Slot = QtCore.Slot
except AttributeError:
    Slot = QtCore.pyqtSlot

# --- Qt enum compatibility (Qt5 uses flat enums, Qt6 uses scoped) ---

_Qt = QtCore.Qt

try:
    AlignCenter = _Qt.AlignCenter
except AttributeError:
    AlignCenter = _Qt.AlignmentFlag.AlignCenter

try:
    AlignLeft = _Qt.AlignLeft
except AttributeError:
    AlignLeft = _Qt.AlignmentFlag.AlignLeft

try:
    AlignRight = _Qt.AlignRight
except AttributeError:
    AlignRight = _Qt.AlignmentFlag.AlignRight

try:
    ScrollBarAsNeeded = _Qt.ScrollBarAsNeeded
except AttributeError:
    ScrollBarAsNeeded = _Qt.ScrollBarPolicy.ScrollBarAsNeeded

try:
    WA_DeleteOnClose = _Qt.WA_DeleteOnClose
except AttributeError:
    WA_DeleteOnClose = _Qt.WidgetAttribute.WA_DeleteOnClose

try:
    Horizontal = _Qt.Horizontal
except AttributeError:
    Horizontal = _Qt.Orientation.Horizontal

try:
    Vertical = _Qt.Vertical
except AttributeError:
    Vertical = _Qt.Orientation.Vertical

try:
    CustomContextMenu = _Qt.CustomContextMenu
except AttributeError:
    CustomContextMenu = _Qt.ContextMenuPolicy.CustomContextMenu

try:
    ScrollBarAlwaysOff = _Qt.ScrollBarAlwaysOff
except AttributeError:
    ScrollBarAlwaysOff = _Qt.ScrollBarPolicy.ScrollBarAlwaysOff

try:
    ItemIsUserCheckable = _Qt.ItemIsUserCheckable
except AttributeError:
    ItemIsUserCheckable = _Qt.ItemFlag.ItemIsUserCheckable

try:
    ItemIsSelectable = _Qt.ItemIsSelectable
except AttributeError:
    ItemIsSelectable = _Qt.ItemFlag.ItemIsSelectable

try:
    ItemIsEnabled = _Qt.ItemIsEnabled
except AttributeError:
    ItemIsEnabled = _Qt.ItemFlag.ItemIsEnabled

try:
    ItemIsDragEnabled = _Qt.ItemIsDragEnabled
except AttributeError:
    ItemIsDragEnabled = _Qt.ItemFlag.ItemIsDragEnabled

try:
    ItemIsDropEnabled = _Qt.ItemIsDropEnabled
except AttributeError:
    ItemIsDropEnabled = _Qt.ItemFlag.ItemIsDropEnabled

try:
    MoveAction = _Qt.MoveAction
except AttributeError:
    MoveAction = _Qt.DropAction.MoveAction

try:
    InternalMove = QtWidgets.QAbstractItemView.InternalMove
except AttributeError:
    InternalMove = QtWidgets.QAbstractItemView.DragDropMode.InternalMove

try:
    Checked = _Qt.Checked
except AttributeError:
    Checked = _Qt.CheckState.Checked

try:
    Unchecked = _Qt.Unchecked
except AttributeError:
    Unchecked = _Qt.CheckState.Unchecked

try:
    UserRole = _Qt.UserRole
except AttributeError:
    UserRole = _Qt.ItemDataRole.UserRole

# QAction lives in QtWidgets (PyQt5) or QtGui (PyQt6/PySide6)
try:
    QAction = QtGui.QAction
except AttributeError:
    QAction = QtWidgets.QAction

try:
    QKeySequence = QtGui.QKeySequence
except AttributeError:
    QKeySequence = QtCore.QKeySequence

# QMessageBox standard buttons (flat in Qt5, scoped in Qt6)
_QMB = QtWidgets.QMessageBox
try:
    MsgBoxYes = _QMB.Yes
except AttributeError:
    MsgBoxYes = _QMB.StandardButton.Yes

try:
    MsgBoxNo = _QMB.No
except AttributeError:
    MsgBoxNo = _QMB.StandardButton.No
