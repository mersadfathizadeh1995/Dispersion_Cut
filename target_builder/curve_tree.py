"""
Curve Tree Widget
=================

Left panel tree widget for managing curves in the target builder.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QMenu, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class CurveType(Enum):
    RAYLEIGH = "rayleigh"
    LOVE = "love"
    HV_CURVE = "hv_curve"
    HV_PEAK = "hv_peak"
    AVERAGED = "averaged"


@dataclass
class CurveData:
    """Data container for a curve."""
    curve_type: CurveType
    filepath: Optional[str] = None  # Original file path
    name: str = ""
    mode: int = 0
    stddev_type: str = "logstd"
    # For HV Peak
    peak_freq: Optional[float] = None
    peak_stddev: float = 0.5
    # Metadata (read from file)
    n_points: int = 0
    freq_min: float = 0.0
    freq_max: float = 0.0
    # State
    included: bool = True
    # Unique ID
    uid: str = ""
    # Working file path (modified copy for processing)
    working_filepath: Optional[str] = None
    # Processing settings
    stddev_mode: str = "file"  # "file", "fixed_logstd", "fixed_cov"
    fixed_logstd: float = 1.1
    fixed_cov: float = 0.1
    use_min_cov: bool = False
    min_cov: float = 0.05
    # Multiple stddev frequency ranges (list of dicts with freq_min, freq_max, value)
    stddev_freq_ranges: Optional[List] = None
    # Resampling settings
    resample_enabled: bool = False
    resample_method: str = "log"
    resample_npoints: int = 50
    resample_fmin: Optional[float] = None
    resample_fmax: Optional[float] = None
    # Cut settings
    cut_enabled: bool = False
    cut_freq_min: Optional[float] = None
    cut_freq_max: Optional[float] = None
    # Dummy points settings
    dummy_enabled: bool = False
    dummy_mode: str = "extend"  # "extend", "custom"
    dummy_extend_low: Optional[float] = None
    dummy_extend_high: Optional[float] = None
    dummy_custom_freqs: str = ""
    dummy_custom_vels: str = ""


class CurveTreeWidget(QWidget):
    """Tree widget for managing curves."""
    
    curve_selected = Signal(str)  # Emits curve UID
    curve_added = Signal(str)  # Emits curve UID
    curve_removed = Signal(str)  # Emits curve UID
    curve_inclusion_changed = Signal(str, bool)  # Emits UID, included state
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: Dict[str, CurveData] = {}
        self._uid_counter = 0
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Curves to Include")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)
        
        # Create category items
        self._rayleigh_item = QTreeWidgetItem(self.tree, ["Rayleigh (0)"])
        self._rayleigh_item.setExpanded(True)
        self._rayleigh_item.setFlags(self._rayleigh_item.flags() & ~Qt.ItemIsSelectable)
        
        self._love_item = QTreeWidgetItem(self.tree, ["Love (0)"])
        self._love_item.setExpanded(True)
        self._love_item.setFlags(self._love_item.flags() & ~Qt.ItemIsSelectable)
        
        self._hvsr_item = QTreeWidgetItem(self.tree, ["HVSR"])
        self._hvsr_item.setExpanded(True)
        self._hvsr_item.setFlags(self._hvsr_item.flags() & ~Qt.ItemIsSelectable)
        
        self._averaged_item = QTreeWidgetItem(self.tree, ["Averaged (0)"])
        self._averaged_item.setExpanded(True)
        self._averaged_item.setFlags(self._averaged_item.flags() & ~Qt.ItemIsSelectable)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("+ Add Curve")
        self.add_btn.setMenu(self._create_add_menu())
        btn_layout.addWidget(self.add_btn)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_all_curves)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
        
    def _create_add_menu(self) -> QMenu:
        """Create the Add Curve dropdown menu."""
        menu = QMenu(self)
        
        menu.addAction("Rayleigh Curve...", lambda: self._request_add_curve(CurveType.RAYLEIGH))
        menu.addAction("Love Curve...", lambda: self._request_add_curve(CurveType.LOVE))
        menu.addSeparator()
        menu.addAction("HV Curve...", lambda: self._request_add_curve(CurveType.HV_CURVE))
        menu.addAction("HV Peak...", lambda: self._request_add_curve(CurveType.HV_PEAK))
        menu.addSeparator()
        menu.addAction("Load Target File...", self._load_target_file)
        
        return menu
    
    def _generate_uid(self) -> str:
        """Generate a unique ID for a curve."""
        self._uid_counter += 1
        return f"curve_{self._uid_counter}"
    
    def _request_add_curve(self, curve_type: CurveType):
        """Request to add a curve (emits signal for dialog)."""
        # This will be connected to show the AddCurveDialog
        from .dialogs import AddCurveDialog
        dialog = AddCurveDialog(curve_type, self)
        if dialog.exec():
            data = dialog.get_curve_data()
            self.add_curve(data)
    
    def add_curve(self, data: CurveData) -> str:
        """Add a curve to the tree."""
        uid = self._generate_uid()
        data.uid = uid
        self._curves[uid] = data
        
        # Determine parent and display text
        if data.curve_type == CurveType.RAYLEIGH:
            parent = self._rayleigh_item
            text = f"{data.name} (M{data.mode})"
        elif data.curve_type == CurveType.LOVE:
            parent = self._love_item
            text = f"{data.name} (M{data.mode})"
        elif data.curve_type == CurveType.HV_CURVE:
            parent = self._hvsr_item
            text = "HV Curve"
        elif data.curve_type == CurveType.HV_PEAK:
            parent = self._hvsr_item
            text = f"HV Peak ({data.peak_freq:.1f} Hz)" if data.peak_freq else "HV Peak"
        elif data.curve_type == CurveType.AVERAGED:
            parent = self._averaged_item
            text = f"{data.name} (M{data.mode})"
        else:
            return ""
        
        # Create tree item
        item = QTreeWidgetItem(parent, [text])
        item.setData(0, Qt.UserRole, uid)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked if data.included else Qt.Unchecked)
        
        # Update category counts
        self._update_category_counts()
        
        self.curve_added.emit(uid)
        return uid
    
    def remove_curve(self, uid: str):
        """Remove a curve from the tree."""
        if uid not in self._curves:
            return
        
        data = self._curves[uid]
        
        # Find and remove tree item
        if data.curve_type == CurveType.RAYLEIGH:
            parent = self._rayleigh_item
        elif data.curve_type == CurveType.LOVE:
            parent = self._love_item
        elif data.curve_type in (CurveType.HV_CURVE, CurveType.HV_PEAK):
            parent = self._hvsr_item
        elif data.curve_type == CurveType.AVERAGED:
            parent = self._averaged_item
        else:
            return
        
        for i in range(parent.childCount()):
            item = parent.child(i)
            if item.data(0, Qt.UserRole) == uid:
                parent.removeChild(item)
                break
        
        del self._curves[uid]
        self._update_category_counts()
        self.curve_removed.emit(uid)
    
    def get_curve(self, uid: str) -> Optional[CurveData]:
        """Get curve data by UID."""
        return self._curves.get(uid)
    
    def update_curve(self, uid: str, data: CurveData):
        """Update curve data."""
        if uid not in self._curves:
            return
        
        data.uid = uid
        self._curves[uid] = data
        
        # Update tree item text
        self._update_item_text(uid, data)
    
    def _update_item_text(self, uid: str, data: CurveData):
        """Update the tree item text for a curve."""
        item = self._find_item_by_uid(uid)
        if not item:
            return
        
        if data.curve_type in (CurveType.RAYLEIGH, CurveType.LOVE, CurveType.AVERAGED):
            text = f"{data.name} (M{data.mode})"
        elif data.curve_type == CurveType.HV_CURVE:
            text = "HV Curve"
        elif data.curve_type == CurveType.HV_PEAK:
            text = f"HV Peak ({data.peak_freq:.1f} Hz)" if data.peak_freq else "HV Peak"
        else:
            return
        
        item.setText(0, text)
    
    def _find_item_by_uid(self, uid: str) -> Optional[QTreeWidgetItem]:
        """Find a tree item by UID."""
        for parent in [self._rayleigh_item, self._love_item, self._hvsr_item, self._averaged_item]:
            for i in range(parent.childCount()):
                item = parent.child(i)
                if item.data(0, Qt.UserRole) == uid:
                    return item
        return None
    
    def _update_category_counts(self):
        """Update the count display in category headers."""
        rayleigh_count = sum(1 for c in self._curves.values() if c.curve_type == CurveType.RAYLEIGH)
        love_count = sum(1 for c in self._curves.values() if c.curve_type == CurveType.LOVE)
        averaged_count = sum(1 for c in self._curves.values() if c.curve_type == CurveType.AVERAGED)
        
        self._rayleigh_item.setText(0, f"Rayleigh ({rayleigh_count})")
        self._love_item.setText(0, f"Love ({love_count})")
        self._averaged_item.setText(0, f"Averaged ({averaged_count})")
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click."""
        uid = item.data(0, Qt.UserRole)
        if uid:
            self.curve_selected.emit(uid)
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle item change (checkbox)."""
        uid = item.data(0, Qt.UserRole)
        if uid and uid in self._curves:
            included = item.checkState(0) == Qt.Checked
            self._curves[uid].included = included
            self.curve_inclusion_changed.emit(uid, included)
    
    def _show_context_menu(self, position):
        """Show context menu for curve items."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        uid = item.data(0, Qt.UserRole)
        if not uid:
            return
        
        menu = QMenu(self)
        
        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(lambda: self.remove_curve(uid))
        
        menu.exec(self.tree.viewport().mapToGlobal(position))
    
    def get_included_curves(self) -> List[CurveData]:
        """Get all curves that are checked for inclusion."""
        return [c for c in self._curves.values() if c.included]
    
    def get_all_curves(self) -> List[CurveData]:
        """Get all curves."""
        return list(self._curves.values())
    
    def clear_all(self):
        """Remove all curves."""
        for uid in list(self._curves.keys()):
            self.remove_curve(uid)
    
    def _clear_all_curves(self):
        """Clear all curves with confirmation."""
        if not self._curves:
            return
        
        reply = QMessageBox.question(
            self, "Clear All Curves",
            "Are you sure you want to remove all curves?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.clear_all()
    
    def _load_target_file(self):
        """Load curves from an existing .target file."""
        from PySide6.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Target File", "",
            "Target files (*.target);;All files (*.*)"
        )
        
        if not filepath:
            return
        
        try:
            from .target_loader import load_target_file
            
            curves, summary = load_target_file(filepath)
            
            if not curves:
                QMessageBox.warning(
                    self, "No Curves Found",
                    "No curves were found in the target file."
                )
                return
            
            # Add all curves to the tree
            for curve_data in curves:
                self.add_curve(curve_data)
            
            # Show summary
            msg_parts = [f"Loaded from: {filepath}", ""]
            if summary['rayleigh_count'] > 0:
                msg_parts.append(f"• {summary['rayleigh_count']} Rayleigh curve(s)")
            if summary['love_count'] > 0:
                msg_parts.append(f"• {summary['love_count']} Love curve(s)")
            if summary['hv_curve']:
                msg_parts.append("• 1 HV Curve")
            if summary['hv_peak']:
                msg_parts.append("• 1 HV Peak")
            
            QMessageBox.information(
                self, "Target Loaded",
                "\n".join(msg_parts)
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error Loading Target",
                f"Failed to load target file:\n\n{e}"
            )
