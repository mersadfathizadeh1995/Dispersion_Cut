"""Backward-compatibility shim -- handlers now live in dc_cut.gui.controller.handlers."""
from dc_cut.gui.controller.handlers import (  # noqa: F401
    SpectrumHandler,
    ToolsHandler,
    DialogsHandler,
    FileIOHandler,
    StateHandler,
    EditHandler,
    AddHandler,
    VisualizationHandler,
)

__all__ = [
    "SpectrumHandler",
    "ToolsHandler",
    "DialogsHandler",
    "FileIOHandler",
    "StateHandler",
    "EditHandler",
    "AddHandler",
    "VisualizationHandler",
]
