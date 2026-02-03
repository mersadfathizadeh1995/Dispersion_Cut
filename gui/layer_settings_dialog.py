"""
Layer Settings Dialog
=====================

Dialog for customizing layer appearance (color, marker, line style).
"""

from typing import Optional, Dict, Any
from matplotlib import colors as mcolors
from matplotlib.backends.qt_compat import QtWidgets, QtCore, QtGui

# Aliases for cleaner code
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QFormLayout = QtWidgets.QFormLayout
QGroupBox = QtWidgets.QGroupBox
QComboBox = QtWidgets.QComboBox
QSpinBox = QtWidgets.QSpinBox
QDoubleSpinBox = QtWidgets.QDoubleSpinBox
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QColorDialog = QtWidgets.QColorDialog
QFrame = QtWidgets.QFrame
Qt = QtCore.Qt
QColor = QtGui.QColor
QPalette = QtGui.QPalette


# Marker shape options
MARKER_OPTIONS = [
    ("o", "Circle"),
    ("s", "Square"),
    ("^", "Triangle Up"),
    ("v", "Triangle Down"),
    ("D", "Diamond"),
    ("*", "Star"),
    ("+", "Plus"),
    ("x", "Cross"),
    (".", "Point"),
    ("", "None"),
]

# Line style options
LINE_STYLE_OPTIONS = [
    ("-", "Solid"),
    ("--", "Dashed"),
    ("-.", "Dash-Dot"),
    (":", "Dotted"),
    ("", "None"),
]


class ColorButton(QPushButton):
    """Button that displays and allows selection of a color."""
    
    def __init__(self, color: str = "#0000FF", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 24)
        self.clicked.connect(self._pick_color)
        self._update_style()
    
    def _update_style(self):
        """Update button style to show current color."""
        self.setStyleSheet(
            f"background-color: {self._color}; "
            f"border: 1px solid #888; border-radius: 3px;"
        )
    
    def _pick_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()
    
    def get_color(self) -> str:
        """Get current color as hex string."""
        return self._color
    
    def set_color(self, color: str):
        """Set color from hex string or matplotlib color name."""
        try:
            # Convert matplotlib color to hex
            rgba = mcolors.to_rgba(color)
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255)
            )
            self._color = hex_color
            self._update_style()
        except Exception:
            pass


class LayerSettingsDialog(QDialog):
    """
    Dialog for customizing layer visual appearance.
    
    Settings:
    - Line color
    - Marker color
    - Marker shape
    - Marker size
    - Line style
    - Line width
    - Alpha (opacity)
    """
    
    def __init__(self, layer_name: str, current_settings: Optional[Dict[str, Any]] = None, 
                 parent=None):
        super().__init__(parent)
        self._layer_name = layer_name
        self._settings = current_settings or {}
        
        self.setWindowTitle(f"Layer Settings - {layer_name}")
        self.setMinimumWidth(350)
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Layer name header
        header = QLabel(f"<b>{self._layer_name}</b>")
        align_center = Qt.AlignmentFlag.AlignCenter if hasattr(Qt, 'AlignmentFlag') else Qt.AlignCenter
        header.setAlignment(align_center)
        layout.addWidget(header)
        
        # Line settings
        line_group = QGroupBox("Line")
        line_layout = QFormLayout(line_group)
        
        self.line_color_btn = ColorButton("#0000FF")
        line_layout.addRow("Color:", self.line_color_btn)
        
        self.line_style_combo = QComboBox()
        for style, name in LINE_STYLE_OPTIONS:
            self.line_style_combo.addItem(name, style)
        line_layout.addRow("Style:", self.line_style_combo)
        
        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 10.0)
        self.line_width_spin.setValue(1.0)
        self.line_width_spin.setSingleStep(0.5)
        self.line_width_spin.setDecimals(1)
        line_layout.addRow("Width:", self.line_width_spin)
        
        layout.addWidget(line_group)
        
        # Marker settings
        marker_group = QGroupBox("Marker")
        marker_layout = QFormLayout(marker_group)
        
        self.marker_color_btn = ColorButton("#0000FF")
        marker_layout.addRow("Color:", self.marker_color_btn)
        
        self.marker_shape_combo = QComboBox()
        for marker, name in MARKER_OPTIONS:
            self.marker_shape_combo.addItem(name, marker)
        marker_layout.addRow("Shape:", self.marker_shape_combo)
        
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 30)
        self.marker_size_spin.setValue(6)
        marker_layout.addRow("Size:", self.marker_size_spin)
        
        layout.addWidget(marker_group)
        
        # Opacity
        opacity_layout = QFormLayout()
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setValue(1.0)
        self.alpha_spin.setSingleStep(0.1)
        self.alpha_spin.setDecimals(2)
        opacity_layout.addRow("Opacity:", self.alpha_spin)
        layout.addLayout(opacity_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        reset_btn = QPushButton("Reset to Default")
        reset_btn.clicked.connect(self._reset_to_default)
        btn_layout.addWidget(reset_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Apply")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_settings(self):
        """Load current settings into UI."""
        if not self._settings:
            return
        
        if 'line_color' in self._settings:
            self.line_color_btn.set_color(self._settings['line_color'])
        if 'marker_color' in self._settings:
            self.marker_color_btn.set_color(self._settings['marker_color'])
        
        if 'line_style' in self._settings:
            for i in range(self.line_style_combo.count()):
                if self.line_style_combo.itemData(i) == self._settings['line_style']:
                    self.line_style_combo.setCurrentIndex(i)
                    break
        
        if 'marker' in self._settings:
            for i in range(self.marker_shape_combo.count()):
                if self.marker_shape_combo.itemData(i) == self._settings['marker']:
                    self.marker_shape_combo.setCurrentIndex(i)
                    break
        
        if 'line_width' in self._settings:
            self.line_width_spin.setValue(self._settings['line_width'])
        if 'marker_size' in self._settings:
            self.marker_size_spin.setValue(self._settings['marker_size'])
        if 'alpha' in self._settings:
            self.alpha_spin.setValue(self._settings['alpha'])
    
    def _reset_to_default(self):
        """Reset all settings to defaults."""
        self.line_color_btn.set_color("#0000FF")
        self.marker_color_btn.set_color("#0000FF")
        self.line_style_combo.setCurrentIndex(0)  # Solid
        self.marker_shape_combo.setCurrentIndex(0)  # Circle
        self.line_width_spin.setValue(1.0)
        self.marker_size_spin.setValue(6)
        self.alpha_spin.setValue(1.0)
    
    def get_settings(self) -> Dict[str, Any]:
        """Get the configured settings."""
        return {
            'line_color': self.line_color_btn.get_color(),
            'marker_color': self.marker_color_btn.get_color(),
            'line_style': self.line_style_combo.currentData(),
            'marker': self.marker_shape_combo.currentData(),
            'line_width': self.line_width_spin.value(),
            'marker_size': self.marker_size_spin.value(),
            'alpha': self.alpha_spin.value(),
        }
