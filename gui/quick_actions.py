from __future__ import annotations

from typing import Optional
from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore


class QuickActionsDock(QtWidgets.QDockWidget):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Actions", parent)
        self.setObjectName("QuickActionsDock"); self.c = controller
        try:
            areas = (
                QtCore.Qt.LeftDockWidgetArea
                | QtCore.Qt.RightDockWidgetArea
                | QtCore.Qt.TopDockWidgetArea
                | QtCore.Qt.BottomDockWidgetArea
            )
        except AttributeError:
            areas = (
                QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
                | QtCore.Qt.DockWidgetArea.RightDockWidgetArea
                | QtCore.Qt.DockWidgetArea.TopDockWidgetArea
                | QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
            )
        self.setAllowedAreas(areas)
        host = QtWidgets.QToolBar(self); host.setMovable(False)
        try: host.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
        except AttributeError: host.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        try: host.setIconSize(QtCore.QSize(20, 20))
        except Exception: pass
        try: pol = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        except AttributeError: pol = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        host.setSizePolicy(pol); host.setMinimumHeight(28); host.setMinimumWidth(420); self.setWidget(host); self.tb = host
        reg = getattr(self.c, 'actions', None)

        def _mk_action(id_: str, fallback_text: str, cb):
            try:
                a = reg.get(id_) if reg is not None else None
                act = QtGui.QAction(a.text if a else fallback_text, self)
                act.triggered.connect(a.callback if a else cb)
                return act
            except Exception:
                act = QtGui.QAction(fallback_text, self); act.triggered.connect(cb); return act

        style = QtWidgets.QApplication.style()
        def _std_icon(name: str) -> QtGui.QIcon:
            std = QtWidgets.QStyle
            mapping = {
                'undo': getattr(std, 'SP_ArrowBack', None),
                'redo': getattr(std, 'SP_ArrowForward', None),
                'delete': getattr(std, 'SP_TrashIcon', None) or getattr(std, 'SP_DialogDiscardButton', None),
                'cancel': getattr(std, 'SP_DialogCancelButton', None),
                'save': getattr(std, 'SP_DialogSaveButton', None),
                'add': getattr(std, 'SP_FileDialogNewFolder', None),
            }
            sp = mapping.get(name)
            try: return style.standardIcon(sp) if sp is not None else QtGui.QIcon()
            except Exception: return QtGui.QIcon()

        def _funnel_icon() -> QtGui.QIcon:
            pix = QtGui.QPixmap(20, 20)
            try: pix.fill(QtCore.Qt.transparent)
            except AttributeError:
                try: pix.fill(QtCore.Qt.GlobalColor.transparent)
                except AttributeError: pix.fill(QtGui.QColor(0, 0, 0, 0))
            p = QtGui.QPainter(pix)
            try: p.setRenderHint(QtGui.QPainter.Antialiasing)
            except AttributeError: p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            pen = QtGui.QPen(QtGui.QColor(60, 60, 60)); pen.setWidth(2); p.setPen(pen)
            path = QtGui.QPainterPath(); path.moveTo(3, 4); path.lineTo(17, 4); path.lineTo(12, 10); path.lineTo(12, 16); path.arcTo(10, 16, 4, 4, 0, -180); path.lineTo(8, 10); path.lineTo(3, 4); p.drawPath(path); p.end()
            return QtGui.QIcon(pix)

        def _box_icon() -> QtGui.QIcon:
            pix = QtGui.QPixmap(20, 20)
            try: pix.fill(QtCore.Qt.transparent)
            except AttributeError:
                try: pix.fill(QtCore.Qt.GlobalColor.transparent)
                except AttributeError: pix.fill(QtGui.QColor(0, 0, 0, 0))
            p = QtGui.QPainter(pix)
            try: p.setRenderHint(QtGui.QPainter.Antialiasing)
            except AttributeError: p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            pen = QtGui.QPen(QtGui.QColor(60, 60, 60)); pen.setWidth(2); p.setPen(pen)
            try: p.setBrush(QtCore.Qt.NoBrush)
            except AttributeError: p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            p.drawRect(4, 4, 12, 12); p.end()
            return QtGui.QIcon(pix)

        def _line_icon() -> QtGui.QIcon:
            pix = QtGui.QPixmap(20, 20)
            try: pix.fill(QtCore.Qt.transparent)
            except AttributeError:
                try: pix.fill(QtCore.Qt.GlobalColor.transparent)
                except AttributeError: pix.fill(QtGui.QColor(0, 0, 0, 0))
            p = QtGui.QPainter(pix)
            try: p.setRenderHint(QtGui.QPainter.Antialiasing)
            except AttributeError: p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            pen = QtGui.QPen(QtGui.QColor(200, 60, 60)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(3, 16, 17, 4)
            pen2 = QtGui.QPen(QtGui.QColor(200, 60, 60)); pen2.setWidth(2); p.setPen(pen2)
            p.drawLine(14, 4, 17, 4); p.drawLine(17, 4, 17, 7)
            p.end()
            return QtGui.QIcon(pix)

        act_filter = _mk_action('tools.filter', 'Filter', lambda: self.c._on_filter_values(None)); act_filter.setIcon(_funnel_icon()); act_filter.setToolTip('Filter points (Delete Above/Below threshold)')
        act_undo = _mk_action('edit.undo', 'Undo', lambda: self.c._on_undo(None)); act_undo.setIcon(_std_icon('undo'))
        act_redo = _mk_action('edit.redo', 'Redo', lambda: self.c._on_redo(None)); act_redo.setIcon(_std_icon('redo'))
        # Avoid duplicate accelerators on actions and QShortcuts; do not set shortcuts on QAction here
        act_delete = _mk_action('edit.delete', 'Delete', lambda: self.c._on_delete(None)); act_delete.setIcon(_std_icon('delete'))
        act_cancel = _mk_action('edit.cancel', 'Can', lambda: self.c._on_cancel(None)); act_cancel.setIcon(_std_icon('cancel'))
        
        # Tool selection buttons (Box vs Line)
        act_box_tool = _mk_action('edit.box_select', 'Box', lambda: self._activate_box_tool()); act_box_tool.setIcon(_box_icon()); act_box_tool.setToolTip('Box Select Tool (draw rectangle to select points)')
        act_box_tool.setCheckable(True); act_box_tool.setChecked(True)
        act_line_tool = _mk_action('edit.line_delete', 'Line', lambda: self._activate_line_tool()); act_line_tool.setIcon(_line_icon()); act_line_tool.setToolTip('Line Delete Tool (draw line, delete points on one side)\nUp/Down arrows to toggle direction')
        act_line_tool.setCheckable(True); act_line_tool.setChecked(False)
        self._act_box_tool = act_box_tool; self._act_line_tool = act_line_tool
        act_avg = _mk_action('tools.avg_resolution', 'Avg', lambda: self.c._on_set_average_resolution(None)); act_avg.setIcon(_std_icon('add'))
        act_add_data = _mk_action('data.add', 'Add Data', lambda: self.c._on_add_data(None)); act_add_data.setIcon(_std_icon('add'))
        act_add_layer = _mk_action('data.add_layer', 'Add Layer', lambda: self.c._on_add_layer(None)); act_add_layer.setIcon(_std_icon('add'))
        act_save_added = _mk_action('data.save_added', 'Save Data', lambda: self.c._on_save_added_data(None)); act_save_added.setIcon(_std_icon('save'))
        act_save_state = _mk_action('file.save_state', 'Save State', lambda: self.c._on_save_session(None)); act_save_state.setIcon(_std_icon('save'))
        act_save_txt = _mk_action('file.save_dc', 'Save Txt', lambda: self.c._on_quit(None)); act_save_txt.setIcon(_std_icon('save'))
        actions = [act_box_tool, act_line_tool, act_filter, act_undo, act_redo, act_delete, act_cancel, act_avg, act_add_data, act_add_layer, act_save_added, act_save_state, act_save_txt]
        for i, act in enumerate(actions):
            self.tb.addAction(act)
            if i in (1, 2, 4, 7, 9, 10): self.tb.addSeparator()
        try:
            btn_all_on = QtWidgets.QAction("All On", self); btn_all_off = QtWidgets.QAction("All Off", self)
            btn_all_on.triggered.connect(lambda: self.c._set_all_layers(True) if hasattr(self.c, '_set_all_layers') else None)
            btn_all_off.triggered.connect(lambda: self.c._set_all_layers(False) if hasattr(self.c, '_set_all_layers') else None)
            self.tb.addSeparator(); self.tb.addAction(btn_all_on); self.tb.addAction(btn_all_off)
        except Exception: pass
        act_save_added.setEnabled(bool(getattr(self.c, 'add_mode', False))); self._act_save_added = act_save_added
        try: self.dockLocationChanged.connect(self._on_dock_loc)
        except Exception: pass
        self._timer = QtCore.QTimer(self); self._timer.setInterval(300); self._timer.timeout.connect(self._sync_enabled); self._timer.start()
        try:
            # Centralize shortcuts in the main window; avoid duplicate bindings here to prevent ambiguity
            pass
        except Exception: pass

    def _on_dock_loc(self, area):
        try: top = QtCore.Qt.TopDockWidgetArea; bottom = QtCore.Qt.BottomDockWidgetArea
        except AttributeError: top = QtCore.Qt.DockWidgetArea.TopDockWidgetArea; bottom = QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
        is_horizontal = area in (top, bottom)
        try: self.tb.setOrientation(QtCore.Qt.Horizontal if is_horizontal else QtCore.Qt.Vertical)
        except AttributeError: ori = QtCore.Qt.Orientation.Horizontal if is_horizontal else QtCore.Qt.Orientation.Vertical; self.tb.setOrientation(ori)

    def _sync_enabled(self):
        on = bool(getattr(self.c, 'add_mode', False)); self._act_save_added.setEnabled(on)
        # Sync tool button states
        try:
            current_tool = self.c.get_current_tool() if hasattr(self.c, 'get_current_tool') else 'box'
            self._act_box_tool.setChecked(current_tool == 'box')
            self._act_line_tool.setChecked(current_tool == 'line')
        except Exception:
            pass

    def _activate_box_tool(self) -> None:
        """Switch to box select tool."""
        try:
            self.c._activate_box_tool()
            self._act_box_tool.setChecked(True)
            self._act_line_tool.setChecked(False)
        except Exception:
            pass

    def _activate_line_tool(self) -> None:
        """Switch to line delete tool."""
        try:
            self.c._activate_line_tool()
            self._act_box_tool.setChecked(False)
            self._act_line_tool.setChecked(True)
        except Exception:
            pass


