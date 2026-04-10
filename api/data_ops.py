"""Data loading and import operations.

Wraps core I/O functions with validation and standardized return format.
"""
from __future__ import annotations

from typing import Dict, Any, Optional, Callable

from dc_cut.api.config import DataLoadConfig
from dc_cut.api.validation import validate_file_path


def load_data(
    config: DataLoadConfig,
    *,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """Load dispersion data from file.

    Returns {"success": bool, "errors": [...], "data": {...}}
    """
    validation = validate_file_path(config.file_path)
    if not validation["valid"]:
        return {"success": False, "errors": validation["errors"]}

    try:
        if progress_callback:
            progress_callback(10, "Detecting file type...")

        path = config.file_path
        file_type = config.file_type

        if file_type == "auto":
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if ext in ("mat",):
                file_type = "matlab"
            elif ext in ("csv", "txt"):
                file_type = "csv"
            elif ext in ("pkl", "dc_state"):
                file_type = "state"
            elif ext in ("max",):
                file_type = "max"
            else:
                file_type = "csv"

        if progress_callback:
            progress_callback(30, f"Loading as {file_type}...")

        if file_type == "matlab":
            from dc_cut.core.io.matlab import load_matlab_data
            result = load_matlab_data(path)
            return {"success": True, "errors": [], "data": result, "file_type": "matlab"}

        elif file_type == "csv":
            from dc_cut.core.io.universal import parse_any_file
            result = parse_any_file(path)
            return {"success": True, "errors": [], "data": result, "file_type": "csv"}

        elif file_type == "state":
            from dc_cut.core.io.state import load_session
            state = load_session(path)
            return {"success": True, "errors": [], "data": state, "file_type": "state"}

        elif file_type == "max":
            from dc_cut.core.io.max_parser import parse_max_file
            result = parse_max_file(path)
            return {"success": True, "errors": [], "data": result, "file_type": "max"}

        else:
            return {"success": False, "errors": [f"Unknown file type: {file_type}"]}

    except Exception as e:
        return {"success": False, "errors": [str(e)]}


def load_klimits(
    *,
    mat_path: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Load k-limits from MAT or CSV file.

    Returns {"success": bool, "errors": [...], "kmin": float, "kmax": float}
    """
    try:
        from dc_cut.core.io.max_parser import load_klimits as _load_klimits
        kmin, kmax = _load_klimits(mat_path=mat_path, csv_path=csv_path)
        return {"success": True, "errors": [], "kmin": kmin, "kmax": kmax}
    except Exception as e:
        return {"success": False, "errors": [str(e)]}
