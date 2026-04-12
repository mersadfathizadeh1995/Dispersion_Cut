"""
Entry point for the Report Studio v2.

Usage:
    from dc_cut.packages.report_studio import launch_studio
    launch_studio(controller=None)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # controller type hint


def launch_studio(controller=None, parent=None):
    """
    Open the Report Studio window.

    Parameters
    ----------
    controller : optional
        DC Cut InteractiveRemovalWithLayers controller.
        If None, the user selects data via project dialog.
    parent : QWidget, optional
        Parent widget for modality.
    """
    from .gui.main_window import ReportStudioWindow

    win = ReportStudioWindow(controller=controller, parent=parent)
    win.show()
    return win
