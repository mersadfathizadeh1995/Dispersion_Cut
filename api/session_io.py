"""Session save/load orchestration.

Wraps core I/O state functions with validation and standardized returns.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, Callable

from dc_cut.api.validation import validate_file_path, validate_output_path


def save_session(
    state: Dict[str, Any],
    output_path: str,
    *,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Save session state to a pickle file.

    Returns {"success": bool, "errors": [...], "output_path": str}
    """
    path_validation = validate_output_path(output_path)
    if not path_validation["valid"]:
        return {"success": False, "errors": path_validation["errors"]}

    try:
        if progress_callback:
            progress_callback(10, "Saving session...")

        from dc_cut.core.io.state import save_session as _save_session
        _save_session(state, output_path)

        if progress_callback:
            progress_callback(100, "Session saved.")

        return {"success": True, "errors": [], "output_path": output_path}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def load_session(
    file_path: str,
    *,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Load session state from a pickle file.

    Returns {"success": bool, "errors": [...], "state": {...}}
    """
    validation = validate_file_path(file_path)
    if not validation["valid"]:
        return {"success": False, "errors": validation["errors"]}

    try:
        if progress_callback:
            progress_callback(10, "Loading session...")

        from dc_cut.core.io.state import load_session as _load_session
        state = _load_session(file_path)

        if progress_callback:
            progress_callback(100, "Session loaded.")

        return {"success": True, "errors": [], "state": state}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}
