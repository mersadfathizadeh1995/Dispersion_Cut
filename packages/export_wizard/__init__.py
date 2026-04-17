"""
Export Wizard Package
=====================

A standalone, modular export wizard for dispersion curve data.
Can be used within DC Cut or as an independent application.

Features:
- Interactive canvas for curve visualization
- Editable table with dynamic columns
- Resampling and uncertainty adjustment
- Multiple export formats (TXT, CSV, JSON)
"""

from .wizard_main import ExportWizardWindow
from .data_model import CurveDataModel

__all__ = ['ExportWizardWindow', 'CurveDataModel']
