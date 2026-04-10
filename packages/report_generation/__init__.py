"""Report Generation package -- publication-quality figure generation.

Public API:
    ReportGenerator  -- orchestrator that dispatches to plot types
    ReportConfig     -- configuration dataclass (alias for PlotConfig)
    PlotConfig       -- flat configuration dataclass used by all code
    ReportDialog     -- Qt dialog (imported lazily to avoid PySide6 dep at import time)
"""
from dc_cut.packages.report_generation.config import ReportConfig, PlotConfig, COLORBLIND_PALETTE
from dc_cut.packages.report_generation.generator import ReportGenerator

# Backward-compat alias
PublicationFigureGenerator = ReportGenerator

__all__ = [
    'ReportGenerator',
    'ReportConfig',
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTE',
]
