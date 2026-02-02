"""Loaded Sources Dock - displays loaded data sources with visibility controls."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui

if TYPE_CHECKING:
    from dc_cut.core.controller import InteractiveRemovalWithLayers


class LoadedSourcesDock(QtWidgets.QDockWidget):
    """Dock widget showing loaded data sources with visibility toggles.
    
    Displays:
    - Data sources organized by type (Active, Passive, Circular Array)
    - Each source shows file label and layer count
    - Checkboxes to toggle visibility of entire source
    - Double-click to rename source label
    """
    
    def __init__(self, controller: "InteractiveRemovalWithLayers", parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Loaded Sources", parent)
        self.controller = controller
        
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
        self._populate_tree()
    
    def _build_ui(self):
        """Build the dock widget UI."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Tree widget for sources
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Source", "Layers", "Visible"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 50)
        self.tree.setColumnWidth(2, 50)
        
        # Enable editing for renaming
        try:
            self.tree.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked)
        except AttributeError:
            self.tree.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        
        layout.addWidget(self.tree)
        
        # Context menu
        try:
            self.tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        except AttributeError:
            self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        # Info label when empty
        self.empty_label = QtWidgets.QLabel(
            "<i>No data loaded.<br>Use File → Open Data to load files.</i>"
        )
        self.empty_label.setAlignment(QtCore.Qt.AlignCenter if hasattr(QtCore.Qt, 'AlignCenter') 
                                       else QtCore.Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        
        self.setWidget(container)
    
    def _populate_tree(self):
        """Populate tree from controller's data sources."""
        self.tree.blockSignals(True)
        self.tree.clear()
        
        # Get file boundaries from controller
        file_boundaries = getattr(self.controller, '_file_boundaries', None)
        data_sources = getattr(self.controller, '_data_sources', None)
        
        has_data = False
        
        if file_boundaries:
            has_data = True
            # Create "Active Data" parent if we have file boundaries
            active_parent = QtWidgets.QTreeWidgetItem(["Active Data", "", ""])
            active_parent.setData(0, self._user_role(), ('type', 'active'))
            font = active_parent.font(0)
            font.setBold(True)
            active_parent.setFont(0, font)
            
            total_layers = 0
            all_visible = True
            
            for file_label, start_idx, end_idx in file_boundaries:
                layer_count = end_idx - start_idx
                total_layers += layer_count
                
                # Check visibility of layers in this source
                source_visible = self._check_source_visibility(start_idx, end_idx)
                if not source_visible:
                    all_visible = False
                
                item = QtWidgets.QTreeWidgetItem([file_label, str(layer_count), ""])
                item.setData(0, self._user_role(), ('source', file_label, start_idx, end_idx))
                item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable if hasattr(QtCore.Qt, 'ItemIsEditable')
                             else item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
                
                # Checkbox for visibility
                item.setCheckState(2, self._check_state(source_visible))
                
                active_parent.addChild(item)
            
            active_parent.setText(1, str(total_layers))
            active_parent.setCheckState(2, self._check_state(all_visible))
            
            self.tree.addTopLevelItem(active_parent)
            active_parent.setExpanded(True)
        
        # Handle other data source types if present
        if data_sources:
            has_data = True
            for source_info in data_sources:
                source_type = source_info.get('type', 'unknown')
                label = source_info.get('label', 'Unknown')
                layers = source_info.get('layers', [])
                
                if source_type == 'active':
                    continue  # Already handled above
                
                type_label = {
                    'passive': 'Passive Data',
                    'circular': 'Circular Array',
                    'state': 'Loaded State'
                }.get(source_type, source_type.title())
                
                item = QtWidgets.QTreeWidgetItem([f"{type_label}: {label}", str(len(layers)), ""])
                item.setData(0, self._user_role(), ('source', label, layers[0] if layers else 0, layers[-1]+1 if layers else 0))
                
                visible = self._check_source_visibility(layers[0] if layers else 0, layers[-1]+1 if layers else 0)
                item.setCheckState(2, self._check_state(visible))
                
                self.tree.addTopLevelItem(item)
        
        # Show/hide empty label
        self.empty_label.setVisible(not has_data)
        self.tree.setVisible(has_data)
        
        self.tree.blockSignals(False)
    
    def _user_role(self):
        """Get UserRole constant."""
        try:
            return QtCore.Qt.ItemDataRole.UserRole
        except AttributeError:
            return QtCore.Qt.UserRole
    
    def _check_state(self, checked: bool):
        """Get check state constant."""
        try:
            return QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked
        except AttributeError:
            return QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
    
    def _check_source_visibility(self, start_idx: int, end_idx: int) -> bool:
        """Check if all layers in source are visible."""
        model = getattr(self.controller, 'model', None)
        if not model:
            return True
        
        for i in range(start_idx, end_idx):
            if i < len(model.layers):
                if not getattr(model.layers[i], 'visible', True):
                    return False
        return True
    
    def _on_item_changed(self, item, column):
        """Handle item change (checkbox or rename)."""
        if column == 2:
            # Visibility toggle
            data = item.data(0, self._user_role())
            if data and data[0] == 'source':
                _, label, start_idx, end_idx = data
                try:
                    checked = item.checkState(2) == (QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') 
                                                      else QtCore.Qt.Checked)
                except:
                    checked = True
                self._set_source_visibility(start_idx, end_idx, checked)
            elif data and data[0] == 'type':
                # Toggle all children
                try:
                    checked = item.checkState(2) == (QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') 
                                                      else QtCore.Qt.Checked)
                except:
                    checked = True
                for i in range(item.childCount()):
                    child = item.child(i)
                    child_data = child.data(0, self._user_role())
                    if child_data and child_data[0] == 'source':
                        _, _, start_idx, end_idx = child_data
                        self._set_source_visibility(start_idx, end_idx, checked)
                self._populate_tree()
        elif column == 0:
            # Rename - update controller's file_boundaries
            data = item.data(0, self._user_role())
            if data and data[0] == 'source':
                old_label = data[1]
                new_label = item.text(0)
                if old_label != new_label:
                    self._rename_source(old_label, new_label)
    
    def _on_double_click(self, item, column):
        """Handle double-click for renaming."""
        if column == 0:
            data = item.data(0, self._user_role())
            if data and data[0] == 'source':
                self.tree.editItem(item, 0)
    
    def _set_source_visibility(self, start_idx: int, end_idx: int, visible: bool):
        """Set visibility for all layers in a source."""
        model = getattr(self.controller, 'model', None)
        if not model:
            return
        
        for i in range(start_idx, end_idx):
            if i < len(model.layers):
                model.layers[i].visible = visible
        
        # Trigger redraw
        if hasattr(self.controller, '_draw'):
            self.controller._draw()
        
        # Update layer tree dock if present
        if hasattr(self.controller, 'on_layers_changed') and self.controller.on_layers_changed:
            self.controller.on_layers_changed()
    
    def _rename_source(self, old_label: str, new_label: str):
        """Rename a source in file_boundaries and layer labels."""
        file_boundaries = getattr(self.controller, '_file_boundaries', None)
        if not file_boundaries:
            return
        
        # Update file_boundaries
        new_boundaries = []
        for label, start_idx, end_idx in file_boundaries:
            if label == old_label:
                new_boundaries.append((new_label, start_idx, end_idx))
            else:
                new_boundaries.append((label, start_idx, end_idx))
        self.controller._file_boundaries = new_boundaries
        
        # Update layer labels
        model = getattr(self.controller, 'model', None)
        if model:
            for layer in model.layers:
                if hasattr(layer, 'label') and layer.label.startswith(f"{old_label}/"):
                    layer.label = layer.label.replace(f"{old_label}/", f"{new_label}/", 1)
        
        # Update offset_labels on controller
        if hasattr(self.controller, 'offset_labels'):
            new_labels = []
            for lbl in self.controller.offset_labels:
                if lbl.startswith(f"{old_label}/"):
                    new_labels.append(lbl.replace(f"{old_label}/", f"{new_label}/", 1))
                else:
                    new_labels.append(lbl)
            self.controller.offset_labels = new_labels
        
        # Refresh UI
        if hasattr(self.controller, 'on_layers_changed') and self.controller.on_layers_changed:
            self.controller.on_layers_changed()
    
    def _show_context_menu(self, pos):
        """Show context menu for tree items."""
        item = self.tree.itemAt(pos)
        if not item:
            return
        
        data = item.data(0, self._user_role())
        menu = QtWidgets.QMenu(self)
        
        if data and data[0] == 'source':
            action_rename = menu.addAction("Rename")
            action_show = menu.addAction("Show All Layers")
            action_hide = menu.addAction("Hide All Layers")
            
            action = menu.exec_(self.tree.mapToGlobal(pos))
            
            if action == action_rename:
                self.tree.editItem(item, 0)
            elif action == action_show:
                _, _, start_idx, end_idx = data
                self._set_source_visibility(start_idx, end_idx, True)
                self._populate_tree()
            elif action == action_hide:
                _, _, start_idx, end_idx = data
                self._set_source_visibility(start_idx, end_idx, False)
                self._populate_tree()
        
        elif data and data[0] == 'type':
            action_show_all = menu.addAction("Show All")
            action_hide_all = menu.addAction("Hide All")
            
            action = menu.exec_(self.tree.mapToGlobal(pos))
            
            if action == action_show_all:
                self._set_all_visibility(True)
            elif action == action_hide_all:
                self._set_all_visibility(False)
    
    def _set_all_visibility(self, visible: bool):
        """Set visibility for all sources."""
        model = getattr(self.controller, 'model', None)
        if not model:
            return
        
        for layer in model.layers:
            layer.visible = visible
        
        self._populate_tree()
        
        if hasattr(self.controller, '_draw'):
            self.controller._draw()
        
        if hasattr(self.controller, 'on_layers_changed') and self.controller.on_layers_changed:
            self.controller.on_layers_changed()
