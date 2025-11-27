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
from dc_cut.gui.spectrum_dock import SpectrumDock
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

        self.spectrum = SpectrumDock(self.controller, self)
        try:
            self.addDockWidget(area, self.spectrum)
            self.tabifyDockWidget(self.layers, self.spectrum)
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
        bar = self.menuBar(); m_file = bar.addMenu("&File"); m_view = bar.addMenu("&View"); m_edit = bar.addMenu("&Edit"); m_layers = bar.addMenu("&Layers"); m_tools= bar.addMenu("&Tools"); m_help = bar.addMenu("&Help")

        # File menu - Preferences
        act_prefs = QtGui.QAction("Preferences...", self)
        act_prefs.setShortcut("Ctrl+,")
        act_prefs.triggered.connect(self._show_preferences)
        m_file.addAction(act_prefs)

        # Export Publication Figure
        act_pub_fig = QtGui.QAction("Export Publication Figure...", self)
        act_pub_fig.triggered.connect(self._show_pub_figure_dialog)
        m_file.addAction(act_pub_fig)

        m_file.addSeparator()

        act_exit = QtGui.QAction("Exit", self); act_exit.setShortcut("Ctrl+Q"); act_exit.triggered.connect(self.close); m_file.addAction(act_exit)
        reg = getattr(self.controller, 'actions', None)
        if reg is not None:
            a_both = reg.get('view.both'); view_both = QtGui.QAction(a_both.text, self); view_both.triggered.connect(a_both.callback)
            a_freq = reg.get('view.freq'); view_freq = QtGui.QAction(a_freq.text, self); view_freq.triggered.connect(a_freq.callback)
            a_wave = reg.get('view.wave'); view_wave = QtGui.QAction(a_wave.text, self); view_wave.triggered.connect(a_wave.callback)
            # Shortcuts handled by QShortcut at window level, not menu actions
        else:
            view_both = QtGui.QAction("Both plots", self); view_both.triggered.connect(lambda: self.controller._apply_view_mode('both'))
            view_freq = QtGui.QAction("Phase-vel vs Freq", self); view_freq.triggered.connect(lambda: self.controller._apply_view_mode('freq_only'))
            view_wave = QtGui.QAction("Wave vs Vel", self); view_wave.triggered.connect(lambda: self.controller._apply_view_mode('wave_only'))
        sub_fig = m_view.addMenu("Figure"); sub_fig.addActions([view_both, view_freq, view_wave])
        sub_pan = m_view.addMenu("Panels")
        try:
            sub_pan.addAction(self.files.toggleViewAction()); sub_pan.addAction(self.props.toggleViewAction()); sub_pan.addAction(self.layers.toggleViewAction()); sub_pan.addAction(self.spectrum.toggleViewAction())
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

        # Layers menu
        act_add_spectrum = QtGui.QAction("Add Spectrum to Layer...", self)
        act_add_spectrum.triggered.connect(self._add_spectrum_to_layer)
        m_layers.addAction(act_add_spectrum)

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

        # Help menu
        act_shortcuts = QtGui.QAction("Keyboard Shortcuts...", self)
        act_shortcuts.setShortcut("F1")
        act_shortcuts.triggered.connect(self._show_shortcuts)
        m_help.addAction(act_shortcuts)

    def _show_shortcuts(self):
        """Show keyboard shortcuts reference."""
        shortcuts_text = """<h2>Keyboard Shortcuts</h2>
        <table cellpadding="5">
        <tr><th align="left">Action</th><th align="left">Shortcut</th></tr>
        <tr><td><b>File</b></td><td></td></tr>
        <tr><td>Preferences</td><td>Ctrl+,</td></tr>
        <tr><td>Save State</td><td>Ctrl+S</td></tr>
        <tr><td>Exit</td><td>Ctrl+Q</td></tr>
        <tr><td><b>Edit</b></td><td></td></tr>
        <tr><td>Undo</td><td>Ctrl+Z</td></tr>
        <tr><td>Redo</td><td>Ctrl+Y</td></tr>
        <tr><td>Delete Selected Area</td><td>Delete</td></tr>
        <tr><td>Cancel Selection</td><td>Esc</td></tr>
        <tr><td><b>View</b></td><td></td></tr>
        <tr><td>Both Plots</td><td>Ctrl+1</td></tr>
        <tr><td>Frequency Plot Only</td><td>Ctrl+2</td></tr>
        <tr><td>Wavelength Plot Only</td><td>Ctrl+3</td></tr>
        <tr><td><b>Near-Field</b></td><td></td></tr>
        <tr><td>Start NF Evaluation</td><td>Ctrl+N</td></tr>
        <tr><td>Apply NF Deletions</td><td>Ctrl+Enter</td></tr>
        <tr><td>Cancel NF Mode</td><td>Esc</td></tr>
        <tr><td><b>Help</b></td><td></td></tr>
        <tr><td>Show Shortcuts</td><td>F1</td></tr>
        </table>
        """
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(QtCore.Qt.TextFormat.RichText if hasattr(QtCore.Qt, 'TextFormat') else QtCore.Qt.RichText)
        msg.setText(shortcuts_text)
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information if hasattr(QtWidgets.QMessageBox, 'Icon') else QtWidgets.QMessageBox.Information)
        msg.exec()

    def _show_preferences(self):
        """Show the preferences dialog."""
        try:
            from dc_cut.gui.preferences_dialog import PreferencesDialog
            dlg = PreferencesDialog(self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open preferences:\n{e}")

    def _show_pub_figure_dialog(self):
        """Show the publication figure export dialog."""
        try:
            from dc_cut.gui.pub_figures_dialog import PublicationFigureDialog
            dlg = PublicationFigureDialog(self.controller, self)
            dlg.exec()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open publication figure dialog:\n{e}")

    def _add_spectrum_to_layer(self):
        """Show dialog to add spectrum background to a layer."""
        try:
            # Check if controller has layers model
            if not hasattr(self.controller, '_layers_model') or self.controller._layers_model is None:
                QtWidgets.QMessageBox.warning(self, "No Layers", "No layers available to add spectrum to.")
                return

            layers = self.controller._layers_model.layers
            if not layers:
                QtWidgets.QMessageBox.warning(self, "No Layers", "No layers available to add spectrum to.")
                return

            # Create dialog for layer selection and spectrum file
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Add Spectrum to Layer")
            dlg.resize(450, 180)

            layout = QtWidgets.QVBoxLayout(dlg)

            # Layer selection
            layer_label = QtWidgets.QLabel("Select layer:", dlg)
            layer_combo = QtWidgets.QComboBox(dlg)
            for i, layer in enumerate(layers):
                layer_combo.addItem(f"{i}: {layer.label}", i)
            layout.addWidget(layer_label)
            layout.addWidget(layer_combo)

            # Spectrum file selection
            spectrum_label = QtWidgets.QLabel("Spectrum file (.npz):", dlg)
            spectrum_layout = QtWidgets.QHBoxLayout()
            spectrum_edit = QtWidgets.QLineEdit(dlg)
            spectrum_edit.setPlaceholderText("Select spectrum .npz file...")
            spectrum_btn = QtWidgets.QPushButton("Browse", dlg)

            def browse_spectrum():
                path, _ = QtWidgets.QFileDialog.getOpenFileName(
                    dlg, "Select Spectrum File", "", "Spectrum Files (*.npz);;All Files (*.*)"
                )
                if path:
                    spectrum_edit.setText(path)

            spectrum_btn.clicked.connect(browse_spectrum)
            spectrum_layout.addWidget(spectrum_edit, 1)
            spectrum_layout.addWidget(spectrum_btn)
            layout.addWidget(spectrum_label)
            layout.addLayout(spectrum_layout)

            # Buttons
            btn_box = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.StandardButton.Ok |
                QtWidgets.QDialogButtonBox.StandardButton.Cancel,
                dlg
            )
            btn_box.accepted.connect(dlg.accept)
            btn_box.rejected.connect(dlg.reject)
            layout.addWidget(btn_box)

            # Show dialog
            if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                layer_idx = layer_combo.currentData()
                spectrum_path = spectrum_edit.text().strip()

                if not spectrum_path:
                    QtWidgets.QMessageBox.warning(self, "No File", "Please select a spectrum file.")
                    return

                # Load spectrum
                if hasattr(self.controller, 'load_spectrum_for_layer'):
                    success = self.controller.load_spectrum_for_layer(layer_idx, spectrum_path)
                    if success:
                        QtWidgets.QMessageBox.information(
                            self, "Success",
                            f"Spectrum loaded for layer {layer_idx}: {layers[layer_idx].label}"
                        )
                        # Refresh spectrum dock to show new controls
                        try:
                            self.spectrum.rebuild()
                        except Exception:
                            pass
                    else:
                        QtWidgets.QMessageBox.critical(
                            self, "Error",
                            "Failed to load spectrum. Check log for details."
                        )
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Not Supported",
                        "Spectrum loading not supported in this version."
                    )

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add spectrum:\n{e}")

    def _build_toolbar(self):
        pass

    def _install_shortcuts(self):
        """Install global keyboard shortcuts at the window level."""
        # Esc - Cancel selection
        try:
            sc_esc = QtGui.QShortcut(QtGui.QKeySequence('Esc'), self)
            sc_esc.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_esc.activated.connect(lambda: self.controller._on_cancel(None))
            sc_esc.setEnabled(True)
            self._esc_shortcut = sc_esc
        except Exception as e:
            print(f"Warning: Could not install Esc shortcut: {e}")

        # Delete - Delete selected area
        try:
            sc_del = QtGui.QShortcut(QtGui.QKeySequence('Delete'), self)
            sc_del.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            # Use the delete action from controller if available
            reg = getattr(self.controller, 'actions', None)
            if reg is not None:
                try:
                    a_del = reg.get('edit.delete')
                    sc_del.activated.connect(a_del.callback)
                except Exception:
                    pass
            sc_del.setEnabled(True)
            self._del_shortcut = sc_del
        except Exception as e:
            print(f"Warning: Could not install Delete shortcut: {e}")

        # View mode shortcuts (Ctrl+1/2/3)
        try:
            sc_both = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+1'), self)
            sc_both.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_both.activated.connect(lambda: self.controller._apply_view_mode('both'))
            sc_both.setEnabled(True)

            sc_freq = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+2'), self)
            sc_freq.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_freq.activated.connect(lambda: self.controller._apply_view_mode('freq_only'))
            sc_freq.setEnabled(True)

            sc_wave = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+3'), self)
            sc_wave.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_wave.activated.connect(lambda: self.controller._apply_view_mode('wave_only'))
            sc_wave.setEnabled(True)

            self._view_shortcuts = [sc_both, sc_freq, sc_wave]
        except Exception as e:
            print(f"Warning: Could not install view shortcuts: {e}")

        # Undo/Redo shortcuts
        try:
            sc_undo = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Z'), self)
            sc_undo.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_undo.activated.connect(lambda: self.controller._on_undo(None))
            sc_undo.setEnabled(True)

            sc_redo = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Y'), self)
            sc_redo.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
            sc_redo.activated.connect(lambda: self.controller._on_redo(None))
            sc_redo.setEnabled(True)

            self._edit_shortcuts = [sc_undo, sc_redo]
        except Exception as e:
            print(f"Warning: Could not install undo/redo shortcuts: {e}")

        # Save shortcuts
        try:
            reg = getattr(self.controller, 'actions', None)
            if reg is not None:
                try:
                    a_save = reg.get('file.save_state')
                    sc_save = QtGui.QShortcut(QtGui.QKeySequence('Ctrl+S'), self)
                    sc_save.setContext(QtCore.Qt.WindowShortcut if hasattr(QtCore.Qt, 'WindowShortcut') else QtCore.Qt.ShortcutContext.WindowShortcut)
                    sc_save.activated.connect(a_save.callback)
                    sc_save.setEnabled(True)
                    self._save_shortcut = sc_save
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Could not install save shortcut: {e}")


def show_shell(controller):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    # Apply theme from preferences
    try:
        from dc_cut.services.prefs import load_prefs
        from dc_cut.services.theme import apply_theme, apply_matplotlib_theme
        prefs = load_prefs()
        theme_name = prefs.get("theme", "light")
        apply_theme(app, theme_name)
        apply_matplotlib_theme(theme_name)
    except Exception:
        pass  # Silently fall back to default theme

    win = MainWindow(controller); win.show()
    setattr(app, "_masw_shell_window", win)
    try: win.raise_(); win.activateWindow()
    except Exception: pass
    return app


