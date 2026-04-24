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
        self._act_save_sheet = file_menu.addAction("&Save Sheet")
        self._act_save_sheet.setShortcut("Ctrl+S")
        self._act_save_sheet_as = file_menu.addAction("Save Sheet &As...")
        self._act_save_sheet_as.setShortcut("Ctrl+Shift+S")
        self._act_load_sheet = file_menu.addAction("&Load Sheet...")
        self._act_load_sheet.setShortcut("Ctrl+Shift+O")

        file_menu.addSeparator()
        self._act_save_config = file_menu.addAction(
            "Save &Config Preset..."
        )
        self._act_load_config = file_menu.addAction(
            "Load Config &Preset..."
        )

        # Recent Projects submenu
        self._recent_menu = file_menu.addMenu("Recent Pro&jects")
        self._refresh_recent_menu()

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
        self._act_save_sheet.triggered.connect(self._on_save_sheet)
        self._act_save_sheet_as.triggered.connect(self._on_save_sheet_as)
        self._act_load_sheet.triggered.connect(self._on_load_sheet)
        self._act_save_config.triggered.connect(self._on_save_config_as)
        self._act_load_config.triggered.connect(self._on_load_config)

    def _refresh_recent_menu(self):
        """Populate the Recent Projects submenu from QSettings."""
        self._recent_menu.clear()
        try:
            from ..panels.project_start_dialog import get_qsettings, KEY_RECENT_PROJECTS
            s = get_qsettings()
            recent = s.value(KEY_RECENT_PROJECTS, [])
            if isinstance(recent, str):
                recent = [recent] if recent else []
            elif recent is None:
                recent = []

            if not recent:
                act = self._recent_menu.addAction("(no recent projects)")
                act.setEnabled(False)
                return

            import os
            for proj_path in recent[:8]:
                if isinstance(proj_path, str) and proj_path:
                    name = os.path.basename(proj_path)
                    act = self._recent_menu.addAction(f"{name}  —  {proj_path}")
                    act.setData(proj_path)
                    act.triggered.connect(
                        lambda checked, p=proj_path: self._on_open_recent(p)
                    )
        except Exception:
            act = self._recent_menu.addAction("(error loading recent)")
            act.setEnabled(False)

    def _on_open_recent(self, project_path: str):
        """Open a project from the recent list."""
        import os
        pj = os.path.join(project_path, "project.json")
        if not os.path.isfile(pj):
            from ...qt_compat import QtWidgets
            QtWidgets.QMessageBox.warning(
                self, "Project Not Found",
                f"Could not find project.json in:\n{project_path}",
            )
            return
        self._open_project_dir(project_path)
