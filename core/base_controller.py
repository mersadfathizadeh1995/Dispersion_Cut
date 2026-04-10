"""Backward-compatibility shim -- real module is dc_cut.gui.controller.base."""
from dc_cut.gui.controller.base import BaseInteractiveRemoval  # noqa: F401

__all__ = ["BaseInteractiveRemoval"]
