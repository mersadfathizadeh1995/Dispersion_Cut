"""
Properties Panel
================

Right panel container that shows properties for the selected curve.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QStackedWidget, QLabel, QScrollArea
)
from PySide6.QtCore import Signal, Qt
from typing import Optional

from .curve_tree import CurveData, CurveType
from .curve_properties import DispersionPropertiesWidget
from .hv_properties import HVCurvePropertiesWidget, HVPeakPropertiesWidget


class PropertiesPanel(QWidget):
    """Container for curve property widgets."""
    
    data_changed = Signal(str, CurveData)  # uid, updated data
    remove_requested = Signal(str)  # uid
    preview_requested = Signal(str)  # uid
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_uid: Optional[str] = None
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Container widget
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked widget to show different property panels
        self.stack = QStackedWidget()
        container_layout.addWidget(self.stack)
        
        # Empty state
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_label = QLabel("Select a curve from the list\nto view its properties")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: gray; font-style: italic;")
        empty_layout.addWidget(empty_label)
        self.stack.addWidget(self.empty_widget)
        
        # Dispersion properties (for Rayleigh and Love)
        self.dispersion_props = DispersionPropertiesWidget()
        self.dispersion_props.data_changed.connect(self._on_data_changed)
        self.dispersion_props.remove_requested.connect(self._on_remove)
        self.dispersion_props.preview_requested.connect(self._on_preview)
        self.stack.addWidget(self.dispersion_props)
        
        # HV Curve properties
        self.hv_curve_props = HVCurvePropertiesWidget()
        self.hv_curve_props.data_changed.connect(self._on_data_changed)
        self.hv_curve_props.remove_requested.connect(self._on_remove)
        self.hv_curve_props.preview_requested.connect(self._on_preview)
        self.stack.addWidget(self.hv_curve_props)
        
        # HV Peak properties
        self.hv_peak_props = HVPeakPropertiesWidget()
        self.hv_peak_props.data_changed.connect(self._on_data_changed)
        self.hv_peak_props.remove_requested.connect(self._on_remove)
        self.stack.addWidget(self.hv_peak_props)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # Start with empty state
        self.stack.setCurrentWidget(self.empty_widget)
    
    def show_curve(self, uid: str, data: CurveData):
        """Show properties for the given curve."""
        self._current_uid = uid
        
        if data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
            self.dispersion_props.set_curve(uid, data)
            self.stack.setCurrentWidget(self.dispersion_props)
        elif data.curve_type == CurveType.HV_CURVE:
            self.hv_curve_props.set_curve(uid, data)
            self.stack.setCurrentWidget(self.hv_curve_props)
        elif data.curve_type == CurveType.HV_PEAK:
            self.hv_peak_props.set_curve(uid, data)
            self.stack.setCurrentWidget(self.hv_peak_props)
        else:
            self.stack.setCurrentWidget(self.empty_widget)
    
    def clear(self):
        """Clear the properties panel."""
        self._current_uid = None
        self.stack.setCurrentWidget(self.empty_widget)
    
    def _on_data_changed(self, uid: str, data: CurveData):
        """Forward data change signal."""
        self.data_changed.emit(uid, data)
    
    def _on_remove(self, uid: str):
        """Forward remove request."""
        self.remove_requested.emit(uid)
    
    def _on_preview(self, uid: str):
        """Forward preview request."""
        self.preview_requested.emit(uid)
