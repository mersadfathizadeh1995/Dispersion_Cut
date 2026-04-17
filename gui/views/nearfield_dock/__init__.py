"""Near-Field Evaluation dock subpackage.

Split out of the former monolithic ``gui/views/nearfield_dock.py``.
Tabs live in sibling modules (``nacd_tab``, ``reference_tab``,
``results_tab``); cross-tab state and the QDockWidget itself are
owned by :mod:`.dock`.  The public surface is unchanged: import
:class:`NearFieldEvalDock` (or the backward-compat alias
``NearFieldAnalysisDock``) directly from this package.
"""
from __future__ import annotations

from .dock import NearFieldEvalDock, NearFieldAnalysisDock

__all__ = ["NearFieldEvalDock", "NearFieldAnalysisDock"]
