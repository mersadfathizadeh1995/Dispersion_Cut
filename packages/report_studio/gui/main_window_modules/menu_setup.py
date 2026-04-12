"""Menu and toolbar setup mixin."""

from __future__ import annotations


class MenuSetupMixin:
    """Creates the menu bar and toolbar."""

    def _setup_menubar(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")
        self._act_open = file_menu.addAction("&Open Data...")
        self._act_open.setShortcut("Ctrl+O")
        file_menu.addSeparator()
        self._act_save_project = file_menu.addAction("&Save Project...")
        self._act_save_project.setShortcut("Ctrl+S")
        self._act_load_project = file_menu.addAction("&Load Project...")
        self._act_load_project.setShortcut("Ctrl+Shift+O")
        file_menu.addSeparator()
        self._act_export_img = file_menu.addAction("Export &Image...")
        self._act_export_img.setShortcut("Ctrl+E")
        file_menu.addSeparator()
        self._act_close = file_menu.addAction("&Close")
        self._act_close.setShortcut("Ctrl+W")

        # View menu
        view_menu = menubar.addMenu("&View")
        self._act_auto_range = view_menu.addAction("Auto &Range")
        self._act_auto_range.setShortcut("Ctrl+R")

    def _setup_toolbar(self):
        pass  # NavigationToolbar is embedded in PlotCanvas

    def _connect_menu_signals(self):
        self._act_close.triggered.connect(self.close)
        self._act_save_project.triggered.connect(self._on_save_project)
        self._act_load_project.triggered.connect(self._on_load_project)
