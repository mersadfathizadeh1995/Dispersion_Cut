"""
Add Point Dialog
================

Dialog for adding points to a specific layer with multiple input modes.
"""

from typing import Optional, List, Tuple, Callable
import numpy as np

from matplotlib.backends.qt_compat import QtWidgets, QtCore

# Aliases for cleaner code
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QRadioButton = QtWidgets.QRadioButton
QButtonGroup = QtWidgets.QButtonGroup
QStackedWidget = QtWidgets.QStackedWidget
QWidget = QtWidgets.QWidget
QMessageBox = QtWidgets.QMessageBox
QLineEdit = QtWidgets.QLineEdit
Qt = QtCore.Qt
Signal = QtCore.Signal


class AddPointDialog(QDialog):
    """
    Dialog for adding a point to a specific layer.
    
    Input modes:
    - Manual: Enter frequency and velocity directly
    - Click on Canvas: User clicks on the plot to select position
    - Interpolate: Insert point between two existing points
    - Clipboard: Paste frequency, velocity from clipboard
    """
    
    # Signal emitted when user wants to pick point from canvas
    request_canvas_pick = Signal()
    
    def __init__(self, layer_names: List[str], parent=None):
        super().__init__(parent)
        self._layer_names = layer_names
        self._picked_point: Optional[Tuple[float, float]] = None
        self._layer_data: Optional[Tuple[np.ndarray, np.ndarray]] = None
        
        self.setWindowTitle("Add Point to Layer")
        self.setMinimumWidth(400)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Layer selection
        layer_group = QGroupBox("Target Layer")
        layer_layout = QFormLayout(layer_group)
        
        self.layer_combo = QComboBox()
        self.layer_combo.addItems(self._layer_names)
        layer_layout.addRow("Layer:", self.layer_combo)
        
        layout.addWidget(layer_group)
        
        # Input mode selection
        mode_group = QGroupBox("Input Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_group = QButtonGroup(self)
        
        self.manual_radio = QRadioButton("Manual Entry")
        self.manual_radio.setChecked(True)
        self.mode_group.addButton(self.manual_radio, 0)
        mode_layout.addWidget(self.manual_radio)
        
        self.canvas_radio = QRadioButton("Click on Canvas")
        self.mode_group.addButton(self.canvas_radio, 1)
        mode_layout.addWidget(self.canvas_radio)
        
        self.interpolate_radio = QRadioButton("Interpolate Between Points")
        self.mode_group.addButton(self.interpolate_radio, 2)
        mode_layout.addWidget(self.interpolate_radio)
        
        self.clipboard_radio = QRadioButton("From Clipboard")
        self.mode_group.addButton(self.clipboard_radio, 3)
        mode_layout.addWidget(self.clipboard_radio)
        
        layout.addWidget(mode_group)
        
        # Stacked widget for mode-specific inputs
        self.mode_stack = QStackedWidget()
        
        # Mode 0: Manual entry
        manual_widget = QWidget()
        manual_layout = QFormLayout(manual_widget)
        
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(0.01, 500.0)
        self.freq_spin.setValue(10.0)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSuffix(" Hz")
        manual_layout.addRow("Frequency:", self.freq_spin)
        
        self.vel_spin = QDoubleSpinBox()
        self.vel_spin.setRange(1.0, 5000.0)
        self.vel_spin.setValue(200.0)
        self.vel_spin.setDecimals(2)
        self.vel_spin.setSuffix(" m/s")
        manual_layout.addRow("Velocity:", self.vel_spin)
        
        self.wave_label = QLabel("Wavelength: 20.00 m")
        manual_layout.addRow("", self.wave_label)
        
        self.mode_stack.addWidget(manual_widget)
        
        # Mode 1: Canvas click
        canvas_widget = QWidget()
        canvas_layout = QVBoxLayout(canvas_widget)
        
        self.pick_btn = QPushButton("Pick Point on Canvas")
        self.pick_btn.clicked.connect(self._on_pick_clicked)
        canvas_layout.addWidget(self.pick_btn)
        
        self.picked_label = QLabel("No point selected")
        self.picked_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_layout.addWidget(self.picked_label)
        
        canvas_layout.addStretch()
        self.mode_stack.addWidget(canvas_widget)
        
        # Mode 2: Interpolate
        interp_widget = QWidget()
        interp_layout = QFormLayout(interp_widget)
        
        self.point1_combo = QComboBox()
        interp_layout.addRow("Point 1:", self.point1_combo)
        
        self.point2_combo = QComboBox()
        interp_layout.addRow("Point 2:", self.point2_combo)
        
        self.interp_spin = QDoubleSpinBox()
        self.interp_spin.setRange(0.0, 1.0)
        self.interp_spin.setValue(0.5)
        self.interp_spin.setDecimals(2)
        self.interp_spin.setSingleStep(0.1)
        interp_layout.addRow("Position (0-1):", self.interp_spin)
        
        self.interp_result = QLabel("")
        interp_layout.addRow("Result:", self.interp_result)
        
        self.mode_stack.addWidget(interp_widget)
        
        # Mode 3: Clipboard
        clipboard_widget = QWidget()
        clipboard_layout = QVBoxLayout(clipboard_widget)
        
        clipboard_layout.addWidget(QLabel("Paste format: frequency, velocity"))
        clipboard_layout.addWidget(QLabel("(separated by comma, tab, or space)"))
        
        self.clipboard_edit = QLineEdit()
        self.clipboard_edit.setPlaceholderText("e.g., 10.5, 250.0")
        clipboard_layout.addWidget(self.clipboard_edit)
        
        paste_btn = QPushButton("Paste from Clipboard")
        paste_btn.clicked.connect(self._paste_clipboard)
        clipboard_layout.addWidget(paste_btn)
        
        clipboard_layout.addStretch()
        self.mode_stack.addWidget(clipboard_widget)
        
        layout.addWidget(self.mode_stack)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        self.add_btn = QPushButton("Add Point")
        self.add_btn.setDefault(True)
        self.add_btn.clicked.connect(self._on_add_clicked)
        btn_layout.addWidget(self.add_btn)
        
        layout.addLayout(btn_layout)
    
    def _connect_signals(self):
        self.mode_group.idClicked.connect(self._on_mode_changed)
        self.freq_spin.valueChanged.connect(self._update_wavelength)
        self.vel_spin.valueChanged.connect(self._update_wavelength)
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        self.interp_spin.valueChanged.connect(self._update_interpolation)
        self.point1_combo.currentIndexChanged.connect(self._update_interpolation)
        self.point2_combo.currentIndexChanged.connect(self._update_interpolation)
    
    def _on_mode_changed(self, mode_id: int):
        self.mode_stack.setCurrentIndex(mode_id)
    
    def _update_wavelength(self):
        """Update wavelength label based on f and v."""
        f = self.freq_spin.value()
        v = self.vel_spin.value()
        w = v / max(f, 0.01)
        self.wave_label.setText(f"Wavelength: {w:.2f} m")
    
    def _on_layer_changed(self, index: int):
        """Handle layer selection change - update interpolation points."""
        # This will be populated by the caller via set_layer_data
        pass
    
    def set_layer_data(self, frequency: np.ndarray, velocity: np.ndarray):
        """Set the current layer's data for interpolation mode."""
        self._layer_data = (frequency.copy(), velocity.copy())
        
        # Populate point combos
        self.point1_combo.clear()
        self.point2_combo.clear()
        
        for i in range(len(frequency)):
            label = f"{i+1}: f={frequency[i]:.2f} Hz, v={velocity[i]:.1f} m/s"
            self.point1_combo.addItem(label, i)
            self.point2_combo.addItem(label, i)
        
        if len(frequency) > 1:
            self.point2_combo.setCurrentIndex(1)
        
        self._update_interpolation()
    
    def _update_interpolation(self):
        """Update interpolation result preview."""
        if self._layer_data is None or len(self._layer_data[0]) < 2:
            self.interp_result.setText("Need at least 2 points")
            return
        
        idx1 = self.point1_combo.currentData()
        idx2 = self.point2_combo.currentData()
        
        if idx1 is None or idx2 is None or idx1 == idx2:
            self.interp_result.setText("Select two different points")
            return
        
        t = self.interp_spin.value()
        f1, f2 = self._layer_data[0][idx1], self._layer_data[0][idx2]
        v1, v2 = self._layer_data[1][idx1], self._layer_data[1][idx2]
        
        f_new = f1 + t * (f2 - f1)
        v_new = v1 + t * (v2 - v1)
        
        self.interp_result.setText(f"f={f_new:.3f} Hz, v={v_new:.2f} m/s")
    
    def _on_pick_clicked(self):
        """Handle pick point button click."""
        self.request_canvas_pick.emit()
        self.picked_label.setText("Click on the canvas to select a point...")
    
    def set_picked_point(self, frequency: float, velocity: float):
        """Set the point picked from the canvas."""
        self._picked_point = (frequency, velocity)
        self.picked_label.setText(f"Selected: f={frequency:.3f} Hz, v={velocity:.2f} m/s")
    
    def _paste_clipboard(self):
        """Paste from system clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.clipboard_edit.setText(text.strip())
    
    def _parse_clipboard(self) -> Optional[Tuple[float, float]]:
        """Parse clipboard text to get frequency and velocity."""
        text = self.clipboard_edit.text().strip()
        if not text:
            return None
        
        # Try different delimiters
        for delimiter in [',', '\t', ' ', ';']:
            parts = text.split(delimiter)
            if len(parts) >= 2:
                try:
                    f = float(parts[0].strip())
                    v = float(parts[1].strip())
                    return (f, v)
                except ValueError:
                    continue
        
        return None
    
    def _on_add_clicked(self):
        """Handle add button click."""
        mode = self.mode_group.checkedId()
        
        if mode == 0:  # Manual
            self.accept()
        elif mode == 1:  # Canvas
            if self._picked_point is None:
                QMessageBox.warning(self, "Add Point", "Please pick a point on the canvas first.")
                return
            self.accept()
        elif mode == 2:  # Interpolate
            if self._layer_data is None or len(self._layer_data[0]) < 2:
                QMessageBox.warning(self, "Add Point", "Need at least 2 points for interpolation.")
                return
            self.accept()
        elif mode == 3:  # Clipboard
            if self._parse_clipboard() is None:
                QMessageBox.warning(self, "Add Point", "Invalid clipboard format. Use: frequency, velocity")
                return
            self.accept()
    
    def get_result(self) -> Optional[Tuple[int, float, float]]:
        """
        Get the result of the dialog.
        
        Returns:
            Tuple of (layer_index, frequency, velocity) or None if cancelled
        """
        if self.result() != QDialog.DialogCode.Accepted:
            return None
        
        layer_idx = self.layer_combo.currentIndex()
        mode = self.mode_group.checkedId()
        
        if mode == 0:  # Manual
            f = self.freq_spin.value()
            v = self.vel_spin.value()
        elif mode == 1:  # Canvas
            if self._picked_point is None:
                return None
            f, v = self._picked_point
        elif mode == 2:  # Interpolate
            if self._layer_data is None:
                return None
            idx1 = self.point1_combo.currentData()
            idx2 = self.point2_combo.currentData()
            t = self.interp_spin.value()
            f1, f2 = self._layer_data[0][idx1], self._layer_data[0][idx2]
            v1, v2 = self._layer_data[1][idx1], self._layer_data[1][idx2]
            f = f1 + t * (f2 - f1)
            v = v1 + t * (v2 - v1)
        elif mode == 3:  # Clipboard
            result = self._parse_clipboard()
            if result is None:
                return None
            f, v = result
        else:
            return None
        
        return (layer_idx, f, v)
