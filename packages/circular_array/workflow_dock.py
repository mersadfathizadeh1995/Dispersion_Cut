"""Workflow control dock for circular array processing."""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Callable

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

if TYPE_CHECKING:
    from dc_cut.packages.circular_array.orchestrator import CircularArrayOrchestrator


class CircularArrayWorkflowDock(QtWidgets.QDockWidget):
    """Dock widget for controlling circular array workflow.
    
    Displays current stage, progress, array focus selector, and workflow actions.
    """

    def __init__(
        self,
        orchestrator: CircularArrayOrchestrator,
        parent: Optional[QtWidgets.QWidget] = None,
        on_save_next: Optional[Callable] = None,
        on_back: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
    ):
        super().__init__("Circular Array Workflow", parent)
        self.setObjectName("CircularArrayWorkflowDock")
        self.orchestrator = orchestrator
        self._on_save_next = on_save_next
        self._on_back = on_back
        self._on_complete = on_complete
        
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
        
        self._build_ui()
        self._update_display()

    def _build_ui(self):
        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        self._stage_label = QtWidgets.QLabel()
        self._stage_label.setStyleSheet(
            "font-size: 14pt; font-weight: bold; padding: 4px;"
        )
        try:
            self._stage_label.setAlignment(QtCore.Qt.AlignCenter)
        except AttributeError:
            self._stage_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._stage_label)
        
        self._progress = QtWidgets.QProgressBar()
        self._progress.setMinimum(1)
        self._progress.setMaximum(self.orchestrator.total_stages)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Stage %v of %m")
        layout.addWidget(self._progress)
        
        self._array_group = QtWidgets.QGroupBox("K-Limits Display")
        array_layout = QtWidgets.QVBoxLayout(self._array_group)
        self._array_checkboxes = []
        
        for diameter in self.orchestrator.config.get_array_diameters():
            cb = QtWidgets.QCheckBox(f"{diameter}m Array")
            cb.setProperty("diameter", diameter)
            array_layout.addWidget(cb)
            self._array_checkboxes.append(cb)
        
        layout.addWidget(self._array_group)
        
        info_group = QtWidgets.QGroupBox("Workflow Info")
        info_layout = QtWidgets.QFormLayout(info_group)
        
        self._site_label = QtWidgets.QLabel(self.orchestrator.config.site_name)
        info_layout.addRow("Site:", self._site_label)
        
        self._wave_label = QtWidgets.QLabel(self.orchestrator.config.wave_type)
        info_layout.addRow("Wave Type:", self._wave_label)
        
        self._output_label = QtWidgets.QLabel(str(self.orchestrator.config.output_dir))
        self._output_label.setWordWrap(True)
        self._output_label.setStyleSheet("font-size: 9pt; color: gray;")
        info_layout.addRow("Output:", self._output_label)
        
        layout.addWidget(info_group)
        
        btn_layout = QtWidgets.QHBoxLayout()
        
        self._btn_back = QtWidgets.QPushButton("◀ Back")
        self._btn_back.setToolTip("Go back to previous stage (reload saved state)")
        self._btn_back.clicked.connect(self._handle_back)
        btn_layout.addWidget(self._btn_back)
        
        self._btn_complete = QtWidgets.QPushButton("Complete Stage")
        self._btn_complete.setToolTip("Save current stage (pkl + mat) without advancing")
        self._btn_complete.clicked.connect(self._handle_complete)
        btn_layout.addWidget(self._btn_complete)
        
        self._btn_next = QtWidgets.QPushButton("Save & Next ▶")
        self._btn_next.setToolTip("Save current stage and advance to next")
        self._btn_next.clicked.connect(self._handle_save_next)
        self._btn_next.setStyleSheet("font-weight: bold;")
        btn_layout.addWidget(self._btn_next)
        
        layout.addLayout(btn_layout)
        
        self._status_label = QtWidgets.QLabel()
        self._status_label.setStyleSheet("font-size: 9pt; color: green;")
        try:
            self._status_label.setAlignment(QtCore.Qt.AlignCenter)
        except AttributeError:
            self._status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)
        
        for cb in self._array_checkboxes:
            cb.toggled.connect(self._on_array_toggled)
        if self._array_checkboxes:
            self._array_checkboxes[0].setChecked(True)
        
        layout.addStretch()
        self.setWidget(container)

    def _update_display(self):
        """Update all display elements based on current orchestrator state."""
        stage = self.orchestrator.current_stage
        
        stage_colors = {
            'INITIAL': '#4CAF50',
            'INTERMEDIATE': '#2196F3', 
            'REFINED': '#9C27B0',
        }
        color = stage_colors.get(stage.name, '#666666')
        self._stage_label.setText(f"🔷 {stage.display_name} Stage")
        self._stage_label.setStyleSheet(
            f"font-size: 14pt; font-weight: bold; padding: 4px; color: {color};"
        )
        
        self._progress.setValue(self.orchestrator.stage_number)
        
        self._btn_back.setEnabled(self.orchestrator.can_go_back())
        self._btn_next.setEnabled(self.orchestrator.can_advance())
        
        if self.orchestrator.is_last_stage:
            self._btn_next.setText("Export Final")
            self._btn_next.setToolTip("Save final stage and export dinver file")
            self._btn_next.setEnabled(True)
        else:
            self._btn_next.setText("Save & Next ▶")
            self._btn_next.setToolTip("Save current stage and advance to next")
        
        self._array_group.setVisible(True)

    def _on_array_toggled(self, checked: bool):
        """Handle array checkbox toggle - update which k-limits are displayed."""
        sender = self.sender()
        if sender is None:
            return
        
        diameter = sender.property("diameter")
        if diameter is not None:
            try:
                if checked:
                    self.orchestrator.add_klimits_display(diameter)
                    self._show_status(f"Showing {diameter}m k-limits")
                else:
                    self.orchestrator.remove_klimits_display(diameter)
                    self._show_status(f"Hidden {diameter}m k-limits")
            except Exception as e:
                self._show_status(f"Error: {e}", error=True)

    def _handle_back(self):
        """Handle Back button click."""
        if self._on_back:
            self._on_back()
        else:
            self._default_back()

    def _handle_complete(self):
        """Handle Complete Stage button click."""
        if self._on_complete:
            self._on_complete()
        else:
            self._default_complete()

    def _handle_save_next(self):
        """Handle Save & Next button click."""
        if self._on_save_next:
            self._on_save_next()
        else:
            self._default_save_next()

    def _default_back(self):
        """Default back action - show message."""
        prev_path = self.orchestrator.get_previous_stage_path()
        if prev_path and prev_path.exists():
            reply = QtWidgets.QMessageBox.question(
                self,
                "Go Back",
                f"Load previous stage from:\n{prev_path.name}?\n\n"
                "Current unsaved changes will be lost.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                self._show_status("Going back... (reload required)")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Go Back", "No previous stage state file found."
            )

    def _default_complete(self):
        """Default complete action - save pkl and mat."""
        try:
            pkl_path, mat_path = self.orchestrator.complete_stage()
            self._show_status(f"Saved: {pkl_path.name}, {mat_path.name}")
            QtWidgets.QMessageBox.information(
                self,
                "Stage Complete",
                f"Saved:\n• {pkl_path.name}\n• {mat_path.name}",
            )
        except Exception as e:
            self._show_status(f"Save failed: {e}", error=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Save failed:\n{e}")

    def _default_save_next(self):
        """Default save and next action."""
        try:
            if self.orchestrator.is_last_stage:
                pkl_path, mat_path = self.orchestrator.complete_stage()
                dinver_path = self.orchestrator.export_final_dinver()
                self._show_status(f"Exported: {dinver_path.name}")
                QtWidgets.QMessageBox.information(
                    self,
                    "Workflow Complete!",
                    f"Final exports:\n• {pkl_path.name}\n• {mat_path.name}\n• {dinver_path.name}",
                )
            else:
                pkl_path, mat_path = self.orchestrator.complete_stage()
                self.orchestrator.advance_stage()
                self._update_display()
                self._show_status(f"Advanced to {self.orchestrator.current_stage.display_name}")
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed:\n{e}")

    def _show_status(self, message: str, error: bool = False):
        """Show status message briefly."""
        color = "red" if error else "green"
        self._status_label.setStyleSheet(f"font-size: 9pt; color: {color};")
        self._status_label.setText(message)
        
        QtCore.QTimer.singleShot(5000, lambda: self._status_label.setText(""))

    def refresh(self):
        """Refresh display from orchestrator state."""
        self._update_display()
