"""Per-subplot legend layer for Report Studio.

This module owns *everything* related to legend rendering in the
Report Studio. It is intentionally self-contained so that future
figure types (NACD-only, spectrum, custom plots, …) can plug in
their own legend item collectors via :mod:`registry` without
touching the renderer.

The public entry points are:

* :class:`SubplotLegendConfig` — placement / appearance config that
  lives on :class:`SubplotState.legend`.
* :func:`build_legend` — render the legend for a single subplot.
* :func:`build_combined_outside_legend` — gather labels from every
  subplot whose placement is ``outside_*`` and emit one
  :func:`fig.legend`.
* :func:`register_collector` / :func:`collect_items` — extension
  hooks: a subplot type can register a function that returns
  additional :class:`LegendItem` entries (used e.g. by NACD lines
  drawn outside the normal scatter handles).
"""

from .config import LegendItem
from .registry import register_collector, collect_items, clear_collectors
from .builder import (
    build_legend,
    build_combined_outside_legend,
    LOC_ANCHORS,
)

# Re-export the dataclass that lives on SubplotState so callers can
# write ``from packages.report_studio.legend import SubplotLegendConfig``.
from ..core.models import SubplotLegendConfig  # noqa: E402

__all__ = [
    "SubplotLegendConfig",
    "LegendItem",
    "build_legend",
    "build_combined_outside_legend",
    "register_collector",
    "collect_items",
    "clear_collectors",
    "LOC_ANCHORS",
]
