"""
Collapsible Section Widget
==========================

Reusable collapsible/expandable section for grouping options.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon


class CollapsibleSection(QWidget):
    """A collapsible section with header and content area."""
    
    toggled = Signal(bool)  # Emits expanded state
    
    def __init__(self, title: str, parent=None, expanded: bool = True, max_height: int = 0):
        super().__init__(parent)
        self._expanded = expanded
        self._title = title
        self._max_height = max_height
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header button
        self.header_btn = QPushButton(self._get_header_text())
        self.header_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 12px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f5f5f5;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
        self.header_btn.clicked.connect(self._toggle)
        layout.addWidget(self.header_btn)
        
        # Content frame with optional scroll
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-top: none;
                border-radius: 0 0 4px 4px;
                background-color: #fafafa;
            }
        """)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        
        if self._max_height > 0:
            self.content_frame.setMaximumHeight(self._max_height)
        
        layout.addWidget(self.content_frame)
        
        # Set initial state
        self.content_frame.setVisible(self._expanded)
    
    def _get_header_text(self) -> str:
        arrow = "v" if self._expanded else ">"
        return f"[{arrow}] {self._title}"
    
    def _toggle(self):
        self._expanded = not self._expanded
        self.content_frame.setVisible(self._expanded)
        self.header_btn.setText(self._get_header_text())
        self.toggled.emit(self._expanded)
    
    def set_expanded(self, expanded: bool):
        """Set expanded state programmatically."""
        if self._expanded != expanded:
            self._toggle()
    
    def is_expanded(self) -> bool:
        return self._expanded
    
    def set_content(self, widget: QWidget):
        """Set the content widget."""
        # Clear existing content
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.content_layout.addWidget(widget)
    
    def add_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)
    
    def add_layout(self, layout):
        """Add a layout to the content area."""
        self.content_layout.addLayout(layout)
