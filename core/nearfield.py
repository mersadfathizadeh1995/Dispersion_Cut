"""Backward-compatibility shim -- real code moved to:
- dc_cut.core.processing.nearfield (pure functions)
- dc_cut.gui.controller.nf_inspector (NearFieldInspector)
"""
from dc_cut.core.processing.nearfield import *  # noqa: F401,F403
from dc_cut.gui.controller.nf_inspector import NearFieldInspector  # noqa: F401
