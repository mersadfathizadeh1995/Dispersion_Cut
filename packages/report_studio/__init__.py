"""
DC Cut Report Studio v2 — Clean, signal-driven report generation.

Usage:
    from dc_cut.packages.report_studio.app import launch_studio
    launch_studio(controller=None)
"""

__all__ = ["launch_studio"]


def launch_studio(controller=None, parent=None):
    """Convenience re-export — lazy import to avoid circular deps."""
    from .app import launch_studio as _launch
    return _launch(controller=controller, parent=parent)
