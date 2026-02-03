from __future__ import annotations

import sys
from typing import Optional

import numpy as np

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
from dc_cut.gui.layer_tree_dock import LayerTreeDock


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

        try:
            left_area = QtCore.Qt.LeftDockWidgetArea
        except AttributeError:
            left_area = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea

        self.layers = LayersDock(self.controller, self)
        try:
            self.addDockWidget(area, self.layers)
            self.tabifyDockWidget(self.props, self.layers)
            self.props.raise_()
        except Exception:
            pass
        self.spectrum = SpectrumDock(self.controller, self)
        try:
            self.addDockWidget(area, self.spectrum)
            self.tabifyDockWidget(self.layers, self.spectrum)
        except Exception:
            pass
        
        # Layer Tree dock (left side, with files)
        self.layer_tree = LayerTreeDock(self.controller, self)
        try:
            self.addDockWidget(left_area, self.layer_tree)
        except Exception:
            pass

        # Set up rebuild hooks for all docks when layers change
        try:
            def on_layers_changed():
                self.layers.rebuild()
                self.spectrum.rebuild()
                if hasattr(self, 'layer_tree'):
                    self.layer_tree._populate_tree()
            setattr(self.controller, 'on_layers_changed', on_layers_changed)
        except Exception:
            pass
        
        # Set up rebuild hook for spectrum dock when spectrum is loaded
        try:
            def on_spectrum_loaded():
                self.spectrum.rebuild()
            setattr(self.controller, 'on_spectrum_loaded', on_spectrum_loaded)
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
        
        self._setup_circular_array_dock()

    def _setup_circular_array_dock(self):
        """Add workflow dock if controller has circular array orchestrator."""
        orchestrator = getattr(self.controller, '_circular_array_orchestrator', None)
        if orchestrator is None:
            return
        
        try:
            from dc_cut.circular_array.workflow_dock import CircularArrayWorkflowDock
            
            if hasattr(self, 'workflow_dock') and self.workflow_dock is not None:
                return
            
            self.workflow_dock = CircularArrayWorkflowDock(
                orchestrator,
                self,
                on_save_next=self._on_workflow_save_next,
                on_back=self._on_workflow_back,
                on_complete=self._on_workflow_complete,
            )
            
            try:
                left_area = QtCore.Qt.LeftDockWidgetArea
            except AttributeError:
                left_area = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
            
            self.addDockWidget(left_area, self.workflow_dock)
            self.controller._workflow_dock = self.workflow_dock
            
        except Exception as e:
            try:
                from dc_cut.services import log
                log.warning(f"Failed to setup circular array dock: {e}")
            except Exception:
                pass

    def _on_workflow_save_next(self):
        """Handle Save & Next from workflow dock."""
        orchestrator = getattr(self.controller, '_circular_array_orchestrator', None)
        if orchestrator is None:
            return
        
        try:
            if orchestrator.is_last_stage:
                pkl_path, mat_path = orchestrator.complete_stage()
                dinver_path = orchestrator.export_final_dinver()
                QtWidgets.QMessageBox.information(
                    self,
                    "Workflow Complete!",
                    f"Final exports saved:\n• {pkl_path.name}\n• {mat_path.name}\n• {dinver_path.name}",
                )
            else:
                pkl_path, mat_path = orchestrator.complete_stage()
                orchestrator.advance_stage()
                if hasattr(self, 'workflow_dock'):
                    self.workflow_dock.refresh()
                QtWidgets.QMessageBox.information(
                    self,
                    "Stage Complete",
                    f"Saved:\n• {pkl_path.name}\n• {mat_path.name}\n\nAdvanced to {orchestrator.current_stage.display_name} stage.",
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Save failed:\n{e}")

    def _on_workflow_back(self):
        """Handle Back from workflow dock."""
        orchestrator = getattr(self.controller, '_circular_array_orchestrator', None)
        if orchestrator is None:
            return
        
        prev_path = orchestrator.get_previous_stage_path()
        if prev_path is None or not prev_path.exists():
            QtWidgets.QMessageBox.warning(
                self, "Go Back", "No previous stage state file found."
            )
            return
        
        try:
            yes_btn = QtWidgets.QMessageBox.StandardButton.Yes
            no_btn = QtWidgets.QMessageBox.StandardButton.No
        except AttributeError:
            yes_btn = QtWidgets.QMessageBox.Yes
            no_btn = QtWidgets.QMessageBox.No
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Go Back",
            f"Load previous stage from:\n{prev_path.name}?\n\nCurrent unsaved changes will be lost.",
            yes_btn | no_btn,
        )
        if reply == yes_btn:
            try:
                from dc_cut.io.state import load_session
                S = load_session(str(prev_path))
                
                if 'velocity_arrays' in S and 'frequency_arrays' in S:
                    self.controller.velocity_arrays = [np.array(v) for v in S['velocity_arrays']]
                    self.controller.frequency_arrays = [np.array(f) for f in S['frequency_arrays']]
                    self.controller.wavelength_arrays = [np.array(w) for w in S['wavelength_arrays']]
                    self.controller.offset_labels = S.get('set_leg', [f"Layer {i+1}" for i in range(len(S['velocity_arrays']))])
                    
                    if hasattr(self.controller, 'layers_model') and self.controller.layers_model is not None:
                        self.controller.layers_model.clear()
                        for i, (v, f, w) in enumerate(zip(
                            self.controller.velocity_arrays,
                            self.controller.frequency_arrays,
                            self.controller.wavelength_arrays
                        )):
                            label = self.controller.offset_labels[i] if i < len(self.controller.offset_labels) else f"Layer {i+1}"
                            self.controller.layers_model.add_layer(v, f, w, label)
                    
                    self.controller._replot()
                
                if 'workflow_config' in S:
                    orchestrator.config = orchestrator.config.__class__.from_dict(S['workflow_config'])
                    if hasattr(orchestrator, '_workflow_dock') and orchestrator._workflow_dock:
                        orchestrator._workflow_dock._update_display()
                
                QtWidgets.QMessageBox.information(
                    self, "Go Back", f"Loaded previous stage from:\n{prev_path.name}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load previous stage:\n{e}")

    def _on_workflow_complete(self):
        """Handle Complete Stage from workflow dock."""
        orchestrator = getattr(self.controller, '_circular_array_orchestrator', None)
        if orchestrator is None:
            return
        
        try:
            pkl_path, mat_path = orchestrator.complete_stage()
            QtWidgets.QMessageBox.information(
                self,
                "Stage Complete",
                f"Saved:\n• {pkl_path.name}\n• {mat_path.name}",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Save failed:\n{e}")

    def _build_menu(self):
        bar = self.menuBar(); m_file = bar.addMenu("&File"); m_view = bar.addMenu("&View"); m_edit = bar.addMenu("&Edit"); m_layers = bar.addMenu("&Layers"); m_tools= bar.addMenu("&Tools"); m_help = bar.addMenu("&Help")

        # File menu - Open Data (append to current session)
        act_open_data = QtGui.QAction("Open Data...", self)
        act_open_data.setShortcut("Ctrl+Shift+O")
        act_open_data.triggered.connect(self._open_data_append)
        m_file.addAction(act_open_data)
        
        m_file.addSeparator()
        
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

        # Tools menu - selection tools
        act_box_tool = QtGui.QAction("Box Select Tool", self)
        act_box_tool.setCheckable(True); act_box_tool.setChecked(True)
        act_box_tool.triggered.connect(lambda: self._switch_tool('box'))
        
        act_line_tool = QtGui.QAction("Line Delete Tool", self)
        act_line_tool.setCheckable(True)
        act_line_tool.triggered.connect(lambda: self._switch_tool('line'))
        
        act_inclined_tool = QtGui.QAction("Inclined Rectangle Tool", self)
        act_inclined_tool.setCheckable(True)
        act_inclined_tool.triggered.connect(lambda: self._switch_tool('inclined_rect'))
        
        self._tool_actions = {'box': act_box_tool, 'line': act_line_tool, 'inclined_rect': act_inclined_tool}
        m_tools.addAction(act_box_tool)
        m_tools.addAction(act_line_tool)
        m_tools.addAction(act_inclined_tool)

        # Layers menu
        act_add_point = QtGui.QAction("Add Point to Layer...", self)
        act_add_point.setShortcut("Ctrl+P")
        act_add_point.triggered.connect(self._add_point_to_layer)
        m_layers.addAction(act_add_point)
        
        act_add_spectrum = QtGui.QAction("Add Spectrum to Layer...", self)
        act_add_spectrum.triggered.connect(self._add_spectrum_to_layer)
        m_layers.addAction(act_add_spectrum)

        if reg is not None:
            try:
                a_load_spec = reg.get('file.load_spectrum'); act_load_spec = QtGui.QAction(a_load_spec.text, self);
                if a_load_spec.shortcut: act_load_spec.setShortcut(a_load_spec.shortcut)
                act_load_spec.triggered.connect(a_load_spec.callback)
                m_file.addAction(act_load_spec)
            except Exception: pass
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

        # Tools menu - Export Wizard
        m_tools.addSeparator()
        act_export_wizard = QtGui.QAction("Export Wizard...", self)
        act_export_wizard.setShortcut("Ctrl+E")
        act_export_wizard.triggered.connect(self._open_export_wizard)
        m_tools.addAction(act_export_wizard)

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
        <tr><td>Append Data</td><td>Ctrl+Shift+O</td></tr>
        <tr><td>Save State</td><td>Ctrl+S</td></tr>
        <tr><td>Exit</td><td>Ctrl+Q</td></tr>
        <tr><td><b>Edit</b></td><td></td></tr>
        <tr><td>Undo</td><td>Ctrl+Z</td></tr>
        <tr><td>Redo</td><td>Ctrl+Y</td></tr>
        <tr><td>Delete Selected Area</td><td>Delete</td></tr>
        <tr><td>Cancel Selection</td><td>Esc</td></tr>
        <tr><td><b>Layers</b></td><td></td></tr>
        <tr><td>Add Point to Layer</td><td>Ctrl+P</td></tr>
        <tr><td><b>Tools</b></td><td></td></tr>
        <tr><td>Export Wizard</td><td>Ctrl+E</td></tr>
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

    def _add_point_to_layer(self):
        """Show dialog to add a point to a specific layer."""
        try:
            from dc_cut.gui.add_point_dialog import AddPointDialog
            import numpy as np
            
            ctrl = self.controller
            if not hasattr(ctrl, 'model') or not ctrl.model or not ctrl.model.layers:
                QtWidgets.QMessageBox.warning(self, "Add Point", "No layers available.")
                return
            
            layer_names = [layer.label for layer in ctrl.model.layers]
            
            dlg = AddPointDialog(layer_names, self)
            
            # Populate layer data for interpolation mode
            def update_layer_data(idx):
                if idx < len(ctrl.model.layers):
                    layer = ctrl.model.layers[idx]
                    dlg.set_layer_data(layer.frequency, layer.velocity)
            
            dlg.layer_combo.currentIndexChanged.connect(update_layer_data)
            update_layer_data(0)  # Initialize with first layer
            
            if dlg.exec():
                result = dlg.get_result()
                if result:
                    layer_idx, f, v = result
                    self._do_add_point(layer_idx, f, v)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add point:\n{e}")
    
    def _do_add_point(self, layer_idx: int, frequency: float, velocity: float):
        """Add a point to the specified layer."""
        import numpy as np
        
        ctrl = self.controller
        if not hasattr(ctrl, 'model') or not ctrl.model:
            return
        
        model = ctrl.model
        if layer_idx >= len(model.layers):
            return
        
        layer = model.layers[layer_idx]
        wavelength = velocity / max(frequency, 1e-10)
        
        # Add to layer data
        layer.frequency = np.append(layer.frequency, frequency)
        layer.velocity = np.append(layer.velocity, velocity)
        layer.wavelength = np.append(layer.wavelength, wavelength)
        
        # Sort by frequency
        order = np.argsort(layer.frequency)
        layer.frequency = layer.frequency[order]
        layer.velocity = layer.velocity[order]
        layer.wavelength = layer.wavelength[order]
        
        # Also update controller arrays
        if layer_idx < len(ctrl.velocity_arrays):
            ctrl.velocity_arrays[layer_idx] = layer.velocity
            ctrl.frequency_arrays[layer_idx] = layer.frequency
            ctrl.wavelength_arrays[layer_idx] = layer.wavelength
        
        # Update matplotlib line data
        if layer_idx < len(getattr(ctrl, 'lines_freq', [])):
            ctrl.lines_freq[layer_idx].set_data(layer.frequency, layer.velocity)
        if layer_idx < len(getattr(ctrl, 'lines_wave', [])):
            ctrl.lines_wave[layer_idx].set_data(layer.wavelength, layer.velocity)
        
        # Recalculate average
        if hasattr(ctrl, '_update_average_line'):
            ctrl._update_average_line()
        
        # Redraw
        if hasattr(ctrl, 'fig') and ctrl.fig:
            ctrl.fig.canvas.draw_idle()
        
        # Notify layers changed
        if hasattr(ctrl, 'on_layers_changed') and ctrl.on_layers_changed:
            ctrl.on_layers_changed()
    
    def _open_export_wizard(self):
        """Open the Export Wizard - prompts user to select a file to load."""
        try:
            from dc_cut.export_wizard import ExportWizardWindow
            
            # Get suggested file path (last saved file if available)
            suggested_file = None
            ctrl = self.controller
            if hasattr(ctrl, '_last_saved_file'):
                suggested_file = ctrl._last_saved_file
            
            # Create wizard with suggested file path (does not auto-load)
            self._export_wizard = ExportWizardWindow(self, suggested_file=suggested_file)
            self._export_wizard.show()
            
            # Prompt user to select a file to load
            self._export_wizard.prompt_for_file()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open Export Wizard:\n{e}")

    def _open_data_append(self):
        """Open data dialog to append data to the current session."""
        try:
            from dc_cut.gui.open_data import OpenDataDialog
            dlg = OpenDataDialog(self)
            if dlg.exec() != 1 or not dlg.result:
                return
            
            spec = dlg.result
            mode = spec.get('mode', '')
            
            # Handle different modes
            if mode == 'active':
                self._append_active_data(spec)
            elif mode == 'passive':
                self._append_passive_data(spec)
            elif mode in ('circular_array_new', 'circular_array_continue'):
                QtWidgets.QMessageBox.warning(
                    self, "Circular Array",
                    "Circular Array mode starts a new workflow.\n"
                    "Please use File → Open Data from the launcher to start a new session."
                )
            elif mode == 'state':
                QtWidgets.QMessageBox.warning(
                    self, "State File",
                    "State files replace the current session.\n"
                    "Please use File → Open Data from the launcher to load a state file."
                )
            else:
                QtWidgets.QMessageBox.warning(self, "Error", f"Unknown mode: {mode}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to open data:\n{e}")
    
    def _append_active_data(self, spec: dict):
        """Append active data to the current session."""
        import numpy as np
        from dc_cut.io.universal import parse_any_file, parse_combined_csv
        import os
        
        files = spec.get('files', [])
        vcut = spec.get('vmax', spec.get('velocity_cutoff', 5000))
        
        if not files:
            QtWidgets.QMessageBox.warning(self, "Error", "No files specified")
            return
        
        total_layers = 0
        for file_info in files:
            path = file_info.get('path')
            label = file_info.get('label', os.path.basename(path))
            mapping_info = file_info.get('mapping', {})
            
            if not path or not os.path.exists(path):
                continue
            
            # Extract mapping components (matching app.py _load_active logic)
            column_mapping = mapping_info.get('column_mapping', {}) if mapping_info else {}
            data_start_line = mapping_info.get('data_start_line', 0) if mapping_info else 0
            offset_grouping = mapping_info.get('offset_grouping', 'None (single offset)') if mapping_info else 'None (single offset)'
            
            # Determine cols_per_offset
            cols_per_offset = 0
            if '2 cols' in offset_grouping:
                cols_per_offset = 2
            elif '3 cols' in offset_grouping:
                cols_per_offset = 3
            elif 'Auto' in offset_grouping:
                cols_per_offset = 3
            
            ext = os.path.splitext(path)[1].lower()
            
            try:
                if column_mapping:
                    v, f, w, labels = parse_any_file(
                        path, column_mapping,
                        data_start_line=data_start_line,
                        cols_per_offset=cols_per_offset
                    )
                elif ext == '.mat':
                    v, f, w, labels = parse_any_file(path)
                elif ext == '.csv':
                    v, f, w, labels = parse_combined_csv(path)
                else:
                    continue
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Parse Error", f"Failed to parse {path}:\n{e}")
                continue
            
            # Apply velocity clamp
            for i in range(len(v)):
                mask = (v[i] >= 0) & (v[i] <= vcut)
                v[i] = v[i][mask]
                f[i] = f[i][mask]
                w[i] = w[i][mask]
            
            # Prefix labels with source name
            prefixed_labels = [f"{label}/{lbl}" for lbl in labels]
            
            # Append to controller
            ctrl = self.controller
            start_idx = len(ctrl.velocity_arrays)
            
            ctrl.velocity_arrays.extend(v)
            ctrl.frequency_arrays.extend(f)
            ctrl.wavelength_arrays.extend(w)
            
            # Insert new labels BEFORE the average labels (which are at the end)
            # The base controller appends "Average (Freq)" and "Average (Wave)" to offset_labels
            avg_labels = [ctrl.average_label, ctrl.average_label_wave]
            # Remove average labels if present at the end
            while ctrl.offset_labels and ctrl.offset_labels[-1] in avg_labels:
                ctrl.offset_labels.pop()
            # Add new layer labels
            ctrl.offset_labels.extend(prefixed_labels)
            # Re-add average labels at the end
            ctrl.offset_labels.append(ctrl.average_label)
            ctrl.offset_labels.append(ctrl.average_label_wave)
            
            end_idx = len(ctrl.velocity_arrays)
            
            # Update file boundaries
            if not hasattr(ctrl, '_file_boundaries') or ctrl._file_boundaries is None:
                ctrl._file_boundaries = []
            ctrl._file_boundaries.append((label, start_idx, end_idx))
            
            # Create lines for new data
            self._create_lines_for_new_data(start_idx, end_idx, v, f, w)
            total_layers += len(v)
        
        # Update layers model and refresh UI
        self._update_layers_model()
        if hasattr(self.controller, 'on_layers_changed') and self.controller.on_layers_changed:
            self.controller.on_layers_changed()
        
        if total_layers > 0:
            QtWidgets.QMessageBox.information(self, "Success", f"Appended {total_layers} layers.")
    
    def _append_passive_data(self, spec: dict):
        """Append passive data to the current session."""
        import numpy as np
        from dc_cut.io.max import parse_max_file
        import os
        
        max_path = spec.get('max_path')
        vcut = spec.get('velocity_cutoff', 2000)
        wave_type = spec.get('wave_type', 'all')
        
        if not max_path or not os.path.exists(max_path):
            QtWidgets.QMessageBox.warning(self, "Error", "Invalid .max file path")
            return
        
        try:
            df = parse_max_file(max_path, wave_type=wave_type)
            
            # Convert to velocity/frequency/wavelength
            if 'slow' in df.columns:
                slow = df['slow'].values
                velocity = 1000.0 / np.maximum(slow, 1e-10)
            elif 'velocity' in df.columns:
                velocity = df['velocity'].values
            else:
                raise ValueError("No velocity or slowness column found")
            
            frequency = df['freq'].values
            wavelength = velocity / np.maximum(frequency, 1e-10)
            
            # Apply velocity filter
            mask = (velocity >= 0) & (velocity <= vcut)
            velocity = velocity[mask]
            frequency = frequency[mask]
            wavelength = wavelength[mask]
            
            label = os.path.splitext(os.path.basename(max_path))[0]
            
            # Add as single layer
            ctrl = self.controller
            start_idx = len(ctrl.velocity_arrays)
            
            ctrl.velocity_arrays.append(velocity)
            ctrl.frequency_arrays.append(frequency)
            ctrl.wavelength_arrays.append(wavelength)
            ctrl.offset_labels.append(label)
            
            end_idx = len(ctrl.velocity_arrays)
            
            # Update file boundaries
            if not hasattr(ctrl, '_file_boundaries') or ctrl._file_boundaries is None:
                ctrl._file_boundaries = []
            ctrl._file_boundaries.append((label, start_idx, end_idx))
            
            # Create lines for new data
            self._create_lines_for_new_data(start_idx, end_idx, [velocity], [frequency], [wavelength])
            
            # Update layers model
            self._update_layers_model()
            
            # Recalculate averages to include new data
            if hasattr(ctrl, '_update_average_line'):
                ctrl._update_average_line()
            
            if hasattr(ctrl, 'on_layers_changed') and ctrl.on_layers_changed:
                ctrl.on_layers_changed()
            
            QtWidgets.QMessageBox.information(self, "Success", f"Appended {len(velocity)} points from {label}")
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to parse passive data:\n{e}")
    
    def _append_data(self):
        """Append additional data to the current session (legacy method)."""
        self._open_data_append()
    
    def _do_append_data(self, spec: dict) -> bool:
        """Actually append the data to the controller."""
        import numpy as np
        from dc_cut.io.universal import parse_any_file, parse_combined_csv
        import os
        
        path = spec.get('path')
        label = spec.get('label', os.path.basename(path))
        mapping = spec.get('mapping')
        vmin = spec.get('vmin', 0)
        vmax = spec.get('vmax', 10000)
        
        if not path or not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Error", "Invalid file path")
            return False
        
        ext = os.path.splitext(path)[1].lower()
        
        try:
            if mapping:
                v, f, w, labels = parse_any_file(path, mapping)
            elif ext == '.mat':
                v, f, w, labels = parse_any_file(path)
            elif ext == '.csv':
                v, f, w, labels = parse_combined_csv(path)
            else:
                QtWidgets.QMessageBox.warning(self, "Error", f"Unsupported file type: {ext}")
                return False
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Parse Error", f"Failed to parse file:\n{e}")
            return False
        
        # Apply velocity clamp
        for i in range(len(v)):
            mask = (v[i] >= vmin) & (v[i] <= vmax)
            v[i] = v[i][mask]
            f[i] = f[i][mask]
            w[i] = w[i][mask]
        
        # Prefix labels with source name
        prefixed_labels = [f"{label}/{lbl}" for lbl in labels]
        
        # Append to controller
        ctrl = self.controller
        start_idx = len(ctrl.velocity_arrays)
        
        # Extend arrays
        ctrl.velocity_arrays.extend(v)
        ctrl.frequency_arrays.extend(f)
        ctrl.wavelength_arrays.extend(w)
        ctrl.offset_labels.extend(prefixed_labels)
        
        end_idx = len(ctrl.velocity_arrays)
        
        # Update file boundaries
        if not hasattr(ctrl, '_file_boundaries') or ctrl._file_boundaries is None:
            ctrl._file_boundaries = []
        ctrl._file_boundaries.append((label, start_idx, end_idx))
        
        # Create new matplotlib lines for the new data
        self._create_lines_for_new_data(start_idx, end_idx, v, f, w)
        
        # Update layers model
        self._update_layers_model()
        
        # Recalculate averages to include new data
        if hasattr(ctrl, '_update_average_line'):
            ctrl._update_average_line()
        
        # Store layer count in spec for message
        spec['layer_count'] = len(v)
        
        return True
    
    def _create_lines_for_new_data(self, start_idx, end_idx, v_arrays, f_arrays, w_arrays):
        """Create matplotlib lines for newly appended data matching original style."""
        ctrl = self.controller
        
        # Use same markers and colors as base_controller.py for consistency
        markers = ['o', 's', '^', 'v', '<', '>', 'D', 'd', 'p', 'h', 'H', '8', 'P', 'X', '*', '+', 'x', '1', '2', '4']
        palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        for i, (v, f, w) in enumerate(zip(v_arrays, f_arrays, w_arrays)):
            idx = start_idx + i
            marker = markers[idx % len(markers)]
            color = palette[idx % len(palette)]
            label = ctrl.offset_labels[idx] if idx < len(ctrl.offset_labels) else f"Offset {idx + 1}"
            
            # Create frequency plot line - match original style (hollow markers)
            line_freq, = ctrl.ax_freq.semilogx(
                f, v,
                marker=marker, linestyle='', markerfacecolor='none',
                markeredgecolor=color, markeredgewidth=1.5, markersize=6,
                picker=5
            )
            ctrl.lines_freq.append(line_freq)
            
            # Create wavelength plot line - match original style (hollow markers)
            line_wave, = ctrl.ax_wave.semilogx(
                w, v,
                marker=marker, linestyle='', markerfacecolor='none',
                markeredgecolor=color, markeredgewidth=1.5, markersize=6,
                label=label, picker=5
            )
            ctrl.lines_wave.append(line_wave)
        
        # Update legend and redraw
        ctrl._update_legend()
        ctrl._apply_axis_limits()
        ctrl.fig.canvas.draw_idle()
    
    def _update_layers_model(self):
        """Rebuild layers model from controller arrays."""
        ctrl = self.controller
        from dc_cut.core.model import LayersModel
        
        # Always rebuild the model from current arrays
        ctrl._layers_model = LayersModel.from_arrays(
            ctrl.velocity_arrays,
            ctrl.frequency_arrays,
            ctrl.wavelength_arrays,
            ctrl.offset_labels
        )

    def _switch_tool(self, tool_name: str) -> None:
        """Switch to the specified selection tool."""
        try:
            # Update tool actions checked state
            for name, action in self._tool_actions.items():
                action.setChecked(name == tool_name)
            
            # Call controller method
            if tool_name == 'box':
                self.controller._activate_box_tool()
            elif tool_name == 'line':
                self.controller._activate_line_tool()
            elif tool_name == 'inclined_rect':
                self.controller._activate_inclined_rect_tool()
        except Exception:
            pass

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


