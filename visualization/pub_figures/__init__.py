"""Backward-compatibility shim -- canonical location is packages.report_generation."""
from dc_cut.packages.report_generation import (
    ReportGenerator as PublicationFigureGenerator,
    ReportConfig as PlotConfig,
    COLORBLIND_PALETTE,
)

__all__ = [
    'PlotConfig',
    'PublicationFigureGenerator',
    'COLORBLIND_PALETTE',
]
