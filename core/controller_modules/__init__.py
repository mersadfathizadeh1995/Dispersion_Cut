"""Controller modules using composition architecture.

Each handler is a delegate object that encapsulates specific controller functionality.
Handlers receive a reference to the parent controller and access its state via self._ctrl.
"""

from dc_cut.core.controller_modules.spectrum_handler import SpectrumHandler
from dc_cut.core.controller_modules.tools_handler import ToolsHandler
from dc_cut.core.controller_modules.dialogs_handler import DialogsHandler
from dc_cut.core.controller_modules.file_io_handler import FileIOHandler
from dc_cut.core.controller_modules.state_handler import StateHandler
from dc_cut.core.controller_modules.edit_handler import EditHandler
from dc_cut.core.controller_modules.add_handler import AddHandler
from dc_cut.core.controller_modules.visualization_handler import VisualizationHandler

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
