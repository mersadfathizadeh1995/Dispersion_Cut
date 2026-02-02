"""Layer Tree Explorer dock widget.

Displays layers organized by source file as a tree structure.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore
QtGui = qt_compat.QtGui


class LayerTreeDock(QtWidgets.QDockWidget):
    """Dock widget showing layers organized by source file."""
    
    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("Layer Tree", parent)
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
        
        # Connect to controller's layer change callback if available
        if hasattr(controller, 'on_layers_changed'):
            original_callback = controller.on_layers_changed
            def wrapped_callback(*args, **kwargs):
                if original_callback:
                    original_callback(*args, **kwargs)
                self._populate_tree()
            controller.on_layers_changed = wrapped_callback
    
    def _build_ui(self):
        """Build the tree widget UI."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Tree widget
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Layer", "Points", "Visible"])
        self.tree.setColumnCount(3)
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 50)
        self.tree.setColumnWidth(2, 50)
        
        # Enable checkboxes
        self.tree.itemChanged.connect(self._on_item_changed)
        
        layout.addWidget(self.tree)
        
        # Context menu
        self.tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu if hasattr(QtCore.Qt, 'ContextMenuPolicy') else QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        
        self.setWidget(container)
    
    def _populate_tree(self):
        """Populate tree from controller's layer data."""
        self.tree.blockSignals(True)
        self.tree.clear()
        
        if not hasattr(self.controller, 'model') or not self.controller.model:
            self.tree.blockSignals(False)
            return
        
        model = self.controller.model
        
        # Check if we have file boundaries (from multi-file load)
        file_boundaries = getattr(self.controller, '_file_boundaries', None)
        
        if file_boundaries:
            # Organize by file
            for file_label, start_idx, end_idx in file_boundaries:
                file_item = QtWidgets.QTreeWidgetItem([file_label, "", ""])
                user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
                file_item.setData(0, user_role, ('file', file_label, start_idx, end_idx))
                
                # Make file item bold
                font = file_item.font(0)
                font.setBold(True)
                file_item.setFont(0, font)
                
                # Check if all layers in this file are visible
                all_visible = all(
                    model.layers[i].visible if hasattr(model.layers[i], 'visible') else True
                    for i in range(start_idx, min(end_idx, len(model.layers)))
                )
                check_state = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
                uncheck_state = QtCore.Qt.CheckState.Unchecked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Unchecked
                file_item.setCheckState(2, check_state if all_visible else uncheck_state)
                
                # Count total points for file
                total_points = sum(
                    len(model.layers[i].velocity) if hasattr(model.layers[i], 'velocity') else 0
                    for i in range(start_idx, min(end_idx, len(model.layers)))
                )
                file_item.setText(1, str(total_points))
                
                # Add child layers
                for layer_idx in range(start_idx, end_idx):
                    if layer_idx < len(model.layers):
                        layer = model.layers[layer_idx]
                        self._add_layer_item(file_item, layer_idx, layer)
                
                self.tree.addTopLevelItem(file_item)
                file_item.setExpanded(True)
        else:
            # Flat list - group by label prefix if "/" present
            groups = {}
            for layer_idx, layer in enumerate(model.layers):
                label = layer.label if hasattr(layer, 'label') else f"Layer {layer_idx + 1}"
                
                if '/' in label:
                    group_name, layer_name = label.split('/', 1)
                else:
                    group_name = None
                    layer_name = label
                
                if group_name:
                    if group_name not in groups:
                        groups[group_name] = []
                    groups[group_name].append((layer_idx, layer, layer_name))
                else:
                    # Add directly as top-level
                    item = QtWidgets.QTreeWidgetItem()
                    self._configure_layer_item(item, layer_idx, layer, layer_name)
                    self.tree.addTopLevelItem(item)
            
            # Add grouped items
            for group_name, layers_list in groups.items():
                group_item = QtWidgets.QTreeWidgetItem([group_name, "", ""])
                user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
                layer_indices = [l[0] for l in layers_list]
                group_item.setData(0, user_role, ('group', group_name, layer_indices))
                font = group_item.font(0)
                font.setBold(True)
                group_item.setFont(0, font)
                
                # Check if all layers in group are visible
                all_visible = all(
                    model.layers[idx].visible if hasattr(model.layers[idx], 'visible') else True
                    for idx, _, _ in layers_list if idx < len(model.layers)
                )
                check_state = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
                uncheck_state = QtCore.Qt.CheckState.Unchecked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Unchecked
                group_item.setCheckState(2, check_state if all_visible else uncheck_state)
                
                # Count total points
                total_points = sum(
                    len(model.layers[idx].velocity) if hasattr(model.layers[idx], 'velocity') else 0
                    for idx, _, _ in layers_list if idx < len(model.layers)
                )
                group_item.setText(1, str(total_points))
                
                for layer_idx, layer, layer_name in layers_list:
                    self._add_layer_item(group_item, layer_idx, layer, layer_name)
                
                self.tree.addTopLevelItem(group_item)
                group_item.setExpanded(True)
        
        self.tree.blockSignals(False)
    
    def _add_layer_item(self, parent_item, layer_idx, layer, label=None):
        """Add a layer as child of parent item."""
        item = QtWidgets.QTreeWidgetItem()
        layer_label = label or (layer.label if hasattr(layer, 'label') else f"Layer {layer_idx + 1}")
        self._configure_layer_item(item, layer_idx, layer, layer_label)
        parent_item.addChild(item)
    
    def _configure_layer_item(self, item, layer_idx, layer, label):
        """Configure a tree item for a layer."""
        # Get point count
        n_points = len(layer.velocity) if hasattr(layer, 'velocity') else 0
        
        # Get visibility
        visible = layer.visible if hasattr(layer, 'visible') else True
        
        item.setText(0, label)
        item.setText(1, str(n_points))
        
        # Checkbox for visibility
        check_state = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
        uncheck_state = QtCore.Qt.CheckState.Unchecked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Unchecked
        item.setCheckState(2, check_state if visible else uncheck_state)
        
        # Store layer index
        user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
        item.setData(0, user_role, ('layer', layer_idx))
    
    def _on_item_changed(self, item, column):
        """Handle item checkbox change."""
        if column != 2:
            return
        
        user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
        data = item.data(0, user_role)
        if not data:
            return
        
        check_state = QtCore.Qt.CheckState.Checked if hasattr(QtCore.Qt, 'CheckState') else QtCore.Qt.Checked
        visible = item.checkState(2) == check_state
        
        if data[0] == 'layer':
            layer_idx = data[1]
            self._set_layer_visibility(layer_idx, visible)
        elif data[0] == 'file':
            # Toggle all layers in file
            _, _, start_idx, end_idx = data
            self._set_range_visibility(start_idx, end_idx, visible)
        elif data[0] == 'group':
            # Toggle all layers in group
            _, _, layer_indices = data
            for idx in layer_indices:
                self._set_layer_visibility_no_refresh(idx, visible)
            self._refresh_after_visibility_change()
    
    def _show_context_menu(self, pos):
        """Show context menu for tree items."""
        item = self.tree.itemAt(pos)
        if not item:
            return
        
        user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
        data = item.data(0, user_role)
        
        menu = QtWidgets.QMenu(self)
        
        if data and data[0] == 'layer':
            layer_idx = data[1]
            
            action_show = menu.addAction("Show Only This")
            action_hide = menu.addAction("Hide This")
            menu.addSeparator()
            action_show_all = menu.addAction("Show All")
            action_hide_all = menu.addAction("Hide All")
            
            action = menu.exec_(self.tree.mapToGlobal(pos))
            
            if action == action_show:
                self._set_layer_visibility(layer_idx, True, exclusive=True)
            elif action == action_hide:
                self._set_layer_visibility(layer_idx, False)
            elif action == action_show_all:
                self._set_all_visibility(True)
            elif action == action_hide_all:
                self._set_all_visibility(False)
        
        elif data and data[0] in ('file', 'group'):
            action_show_group = menu.addAction("Show All in Group")
            action_hide_group = menu.addAction("Hide All in Group")
            
            action = menu.exec_(self.tree.mapToGlobal(pos))
            
            if action == action_show_group:
                self._set_group_visibility(item, True)
            elif action == action_hide_group:
                self._set_group_visibility(item, False)
    
    def _set_layer_visibility(self, layer_idx, visible, exclusive=False):
        """Set visibility for a single layer and refresh UI."""
        if not hasattr(self.controller, 'model') or not self.controller.model:
            return
        
        model = self.controller.model
        
        if exclusive:
            for i, layer in enumerate(model.layers):
                layer.visible = (i == layer_idx)
        else:
            if layer_idx < len(model.layers):
                model.layers[layer_idx].visible = visible
        
        self._refresh_after_visibility_change()
    
    def _set_layer_visibility_no_refresh(self, layer_idx, visible):
        """Set visibility for a single layer without refreshing (batch use)."""
        if not hasattr(self.controller, 'model') or not self.controller.model:
            return
        
        model = self.controller.model
        if layer_idx < len(model.layers):
            model.layers[layer_idx].visible = visible
    
    def _set_range_visibility(self, start_idx, end_idx, visible):
        """Set visibility for a range of layers."""
        if not hasattr(self.controller, 'model') or not self.controller.model:
            return
        
        model = self.controller.model
        for i in range(start_idx, min(end_idx, len(model.layers))):
            model.layers[i].visible = visible
        
        self._refresh_after_visibility_change()
    
    def _set_all_visibility(self, visible):
        """Set visibility for all layers."""
        if not hasattr(self.controller, 'model') or not self.controller.model:
            return
        
        for layer in self.controller.model.layers:
            layer.visible = visible
        
        self._refresh_after_visibility_change()
    
    def _set_group_visibility(self, group_item, visible):
        """Set visibility for all layers in a group."""
        if not hasattr(self.controller, 'model') or not self.controller.model:
            return
        
        user_role = QtCore.Qt.ItemDataRole.UserRole if hasattr(QtCore.Qt, 'ItemDataRole') else QtCore.Qt.UserRole
        
        for i in range(group_item.childCount()):
            child = group_item.child(i)
            data = child.data(0, user_role)
            if data and data[0] == 'layer':
                layer_idx = data[1]
                if layer_idx < len(self.controller.model.layers):
                    self.controller.model.layers[layer_idx].visible = visible
        
        self._refresh_after_visibility_change()
    
    def _refresh_after_visibility_change(self):
        """Refresh UI after visibility changes - syncs with Layers dock."""
        # Update matplotlib lines visibility
        if hasattr(self.controller, 'model') and self.controller.model:
            model = self.controller.model
            for i, layer in enumerate(model.layers):
                visible = layer.visible if hasattr(layer, 'visible') else True
                if i < len(getattr(self.controller, 'lines_freq', [])):
                    self.controller.lines_freq[i].set_visible(visible)
                if i < len(getattr(self.controller, 'lines_wave', [])):
                    self.controller.lines_wave[i].set_visible(visible)
        
        # Redraw plot
        if hasattr(self.controller, '_draw'):
            self.controller._draw()
        
        # Call on_layers_changed to sync Layers dock on right
        if hasattr(self.controller, 'on_layers_changed') and self.controller.on_layers_changed:
            self.controller.on_layers_changed()
