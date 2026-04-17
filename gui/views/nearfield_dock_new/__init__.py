"""Near-Field Evaluation dock subpackage (parallel build).

Modules are extracted incrementally; the public re-exports are added
once :mod:`dock` is in place (see :class:`NearFieldEvalDock`).
"""
from __future__ import annotations

__all__: list[str] = []

try:
    from .dock import NearFieldEvalDock, NearFieldAnalysisDock  # noqa: F401
    __all__.extend(["NearFieldEvalDock", "NearFieldAnalysisDock"])
except Exception:  # dock.py not yet built
    pass
