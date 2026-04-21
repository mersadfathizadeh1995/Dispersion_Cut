"""Extension registry for legend item collectors.

Different subplot types ("curves", "nacd_only", "spectrum", …) may
want to contribute extra legend entries that are *not* part of the
normal Matplotlib artist label discovery. They register a
collector here, keyed by ``stype``.

A collector has the signature::

    def collector(ax, sp, sheet) -> list[LegendItem]: ...

Where ``sp`` is the :class:`SubplotState` and ``sheet`` is the
parent :class:`SheetState`. Returning an empty list is fine.
"""
from __future__ import annotations

from typing import Callable, Dict, List

from .config import LegendItem


# Public type alias for clarity in user code.
Collector = Callable[[object, object, object], List[LegendItem]]

# Module-global registry; keyed by SubplotState.stype.
_COLLECTORS: Dict[str, List[Collector]] = {}


def register_collector(stype: str, fn: Collector) -> None:
    """Register ``fn`` as an additional collector for ``stype``.

    Multiple collectors per stype are supported (called in
    registration order).
    """
    _COLLECTORS.setdefault(stype, []).append(fn)


def collect_items(ax, sp, sheet) -> List[LegendItem]:
    """Run every collector registered for ``sp.stype`` and aggregate."""
    out: List[LegendItem] = []
    for fn in _COLLECTORS.get(getattr(sp, "stype", ""), ()):
        try:
            items = fn(ax, sp, sheet) or []
        except Exception:
            # Collectors must never break rendering; swallow & continue.
            items = []
        out.extend(items)
    return out


def clear_collectors() -> None:
    """Remove all registered collectors (for tests)."""
    _COLLECTORS.clear()
