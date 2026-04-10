"""Backward-compatibility shim -- real module is dc_cut.core.io.state."""
from dc_cut.core.io.state import *  # noqa: F401,F403
from dc_cut.core.io.state import save_session, load_session
