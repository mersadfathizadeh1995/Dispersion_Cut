from __future__ import annotations

import sys
from typing import Optional

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui     = qt_compat.QtGui
QtCore    = qt_compat.QtCore

from dc_cut.gui.properties import PropertiesDock
# Optional file explorer is not essential; keep simple fallback
class FileExplorerDock(QtWidgets.QDockWidget):
    def __init__(self, start_path: str | None = None, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__("Files", parent)
        try:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
            )
        except AttributeError:
            feats = (
                QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            self.setFeatures(feats)
        import os
        root = start_path or os.getcwd()
        if hasattr(QtWidgets, 'QFileSystemModel'):
            model = QtWidgets.QFileSystemModel(self); model.setReadOnly(True); model.setRootPath(root)
            view = QtWidgets.QTreeView(self); view.setModel(model); view.setRootIndex(model.index(root))
            try: view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            except AttributeError: view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
            for col in range(1, 4):
                try: view.hideColumn(col)
                except Exception: pass
            self.setWidget(view)
        else:
            lst = QtWidgets.QListWidget(self); [lst.addItem(name) for name in sorted(os.listdir(root))]
            self.setWidget(lst)
from dc_cut.gui.layers_dock import LayersDock
from dc_cut.gui.nf_eval_dock import NFEvalDock
from dc_cut.gui.quick_actions import QuickActionsDock


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("MASW Interactive – Shell")
        self.resize(900, 120)
        self._central_placeholder()
        self.props = PropertiesDock(self.controller, self)
        try:
            area = QtCore.Qt.RightDockWidgetArea
        except AttributeError:
            area = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
        self.addDockWidget(area, self.props)

        # File explorer (use legacy one if available)
        try:
            self.files = FileExplorerDock(parent=self)
            try:
                left_area = QtCore.Qt.LeftDockWidgetArea
            except AttributeError:
                left_area = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            self.addDockWidget(left_area, self.files)
        except Exception:
            pass

        self.layers = LayersDock(self.controller, self)
        try:
            self.addDockWidget(area, self.layers)
            self.tabifyDockWidget(self.props, self.layers)
            self.props.raise_()
        except Exception:
            pass
        try:
            setattr(self.controller, 'on_layers_changed', self.layers.rebuild)
        except Exception:
            pass

        self.nf_eval = NFEvalDock(self.controller, self)
        try:
            self.addDockWidget(left_area, self.nf_eval)
        except Exception:
            pass

        self.quick = QuickActionsDock(self.controller, self)
        try:
            try:
                top_area = QtCore.Qt.TopDockWidgetArea
            except AttributeError:
                top_area = QtCore.Qt.DockWidgetArea.TopDockWidgetArea
            self.addDockWidget(top_area, self.quick)
        except Exception:
            pass

        self._build_menu()
        self._build_toolbar()
        self._install_shortcuts()

    def _central_placeholder(self):
        label = QtWidgets.QLabel("Shell window is running. Use the toolbar/menu to control the plot window.")
        try:
            align_center = QtCore.Qt.AlignCenter
        except AttributeError:
            align_center = QtCore.Qt.AlignmentFlag.AlignCenter
        label.setAlignment(align_center)
        self.setCentralWidget(label)

    def adopt_controller(self, controller):
        self.controller = controller
        canvas = controller.fig.canvas
        mgr = getattr(canvas, 'manager', None)
        toolbar = getattr(mgr, 'toolbar', None)
        try:
            mgr.window.hide()
        except Exception:
            pass
        container = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(container); v.setContentsMargins(0, 0, 0, 0)
        try:
            if toolbar is None:
                from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
                toolbar = NavigationToolbar2QT(canvas, container)
            else:
                toolbar.setParent(container)
            v.addWidget(toolbar)
            try:
                from dc_cut.services.mpl_compat import patch_toolbar_home
                patch_toolbar_home(self.controller.fig, on_after=self.controller._apply_axis_limits)
            except Exception:
                pass
        except Exception:
            pass
        try:
            canvas.setParent(container)
        except Exception:
            pass
        v.addWidget(canvas, 1)
        self.setCentralWidget(container)

    def _build_menu(self):
        bar = self.menuBar(); m_file = bar.addMenu("&File"); m_view = bar.addMenu("&View"); m_edit = bar.addMenu("&Edit"); m_tools= bar.addMenu("&Tools")
        act_exit = QtGui.QAction("Exit", self); act_exit.setShortcut("Ctrl+Q"); act_exit.triggered.connect(self.close); m_file.addAction(act_exit)
        reg = getattr(self.controller, 'actions', None)
        if reg is not None:
            a_both = reg.get('view.both'); view_both = QtGui.QAction(a_both.text, self); view_both.triggered.connect(a_both.callback)
            a_freq = reg.get('view.freq'); view_freq = QtGui.QAction(a_freq.text, self); view_freq.triggered.connect(a_freq.callback)
            a_wave = reg.get('view.wave'); view_wave = QtGui.QAction(a_wave.text, self); view_wave.triggered.connect(a_wave.callback)
            try: view_both.setShortcut('Ctrl+1'); view_freq.setShortcut('Ctrl+2'); view_wave.setShortcut('Ctrl+3')
            except Exception: pass
        else:
            view_both = QtGui.QAction("Both plots", self); view_both.triggered.connect(lambda: self.controller._apply_view_mode('both'))
            view_freq = QtGui.QAction("Phase-vel vs Freq", self); view_freq.triggered.connect(lambda: self.controller._apply_view_mode('freq_only'))
            view_wave = QtGui.QAction("Wave vs Vel", self); view_wave.triggered.connect(lambda: self.controller._apply_view_mode('wave_only'))
        sub_fig = m_view.addMenu("Figure"); sub_fig.addActions([view_both, view_freq, view_wave])
        sub_pan = m_view.addMenu("Panels")
        try:
            sub_pan.addAction(self.files.toggleViewAction()); sub_pan.addAction(self.props.toggleViewAction()); sub_pan.addAction(self.layers.toggleViewAction())
        except Exception: pass
        if reg is not None:
            a_undo = reg.get('edit.undo'); undo = QtGui.QAction(a_undo.text, self); 
            if a_undo.shortcut: undo.setShortcut(a_undo.shortcut)
            undo.triggered.connect(a_undo.callback)
            a_redo = reg.get('edit.redo'); redo = QtGui.QAction(a_redo.text, self); 
            if a_redo.shortcut: redo.setShortcut(a_redo.shortcut)
            redo.triggered.connect(a_redo.callback)
            a_del = reg.get('edit.delete'); act_del = QtGui.QAction(a_del.text, self); 
            if a_del.shortcut: act_del.setShortcut(a_del.shortcut)
            act_del.triggered.connect(a_del.callback)
            a_cancel = reg.get('edit.cancel'); act_cancel = QtGui.QAction(a_cancel.text, self);
            if a_cancel.shortcut: act_cancel.setShortcut(a_cancel.shortcut)
            act_cancel.triggered.connect(a_cancel.callback)
            m_edit.addActions([act_del, act_cancel])
        else:
            undo = QtGui.QAction("Undo", self); undo.setShortcut("Ctrl+Z"); undo.triggered.connect(self.controller._on_undo)
            redo = QtGui.QAction("Redo", self); redo.setShortcut("Ctrl+Y"); redo.triggered.connect(self.controller._on_redo)
        m_edit.addActions([undo, redo])

        if reg is not None:
            try:
                a_save = reg.get('file.save_state'); act_save = QtGui.QAction(a_save.text, self);
                if a_save.shortcut: act_save.setShortcut(a_save.shortcut)
                act_save.triggered.connect(a_save.callback)
                m_file.addAction(act_save)
            except Exception: pass
            try:
                a_txt = reg.get('file.save_dc'); act_txt = QtGui.QAction(a_txt.text, self);
                if a_txt.shortcut: act_txt.setShortcut(a_txt.shortcut)
                act_txt.triggered.connect(a_txt.callback)
                m_file.addAction(act_txt)
            except Exception: pass
            try:
                a_psv = reg.get('file.save_passive_stats'); act_psv = QtGui.QAction(a_psv.text, self);
                if a_psv.shortcut: act_psv.setShortcut(a_psv.shortcut)
                act_psv.triggered.connect(a_psv.callback)
                m_file.addAction(act_psv)
            except Exception: pass

    def _build_toolbar(self):
        pass

    def _install_shortcuts(self):
        # Single Esc binding at the window level
        try:
            sc = QtGui.QShortcut(QtGui.QKeySequence('Esc'), self)
            try: sc.setContext(QtCore.Qt.ApplicationShortcut)
            except Exception:
                try: sc.setContext(QtCore.Qt.ShortcutContext.ApplicationShortcut)
                except Exception: pass
            sc.activated.connect(lambda: self.controller._on_cancel(None))
            self._esc_shortcut = sc
        except Exception:
            pass


def show_shell(controller):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = MainWindow(controller); win.show()
    setattr(app, "_masw_shell_window", win)
    try: win.raise_(); win.activateWindow()
    except Exception: pass
    return app


