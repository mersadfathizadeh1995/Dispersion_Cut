"""Backward-compatibility shim -- canonical location is packages.report_generation.plots."""
from dc_cut.packages.report_generation.plots import (
    BasicFrequencyPlotsMixin,
    BasicWavelengthPlotsMixin,
    CanvasExportMixin,
    OffsetAnalysisMixin,
    NearFieldAnalysisMixin,
)

__all__ = [
    'BasicFrequencyPlotsMixin',
    'BasicWavelengthPlotsMixin',
    'CanvasExportMixin',
    'OffsetAnalysisMixin',
    'NearFieldAnalysisMixin',
]
