"""
Target Builder GUI Module
=========================

A panel-based GUI for creating Dinver .target files.
"""

from .target_builder import TargetBuilderWidget
from .curve_tree import CurveTreeWidget, CurveData, CurveType
from .properties_panel import PropertiesPanel
from .dialogs import AddCurveDialog
from .averaging_dialog import AveragingDialog
from .summary_dialog import SummaryDialog
from .canvas_preview import CanvasPreviewWindow
from .curve_history import CurveHistoryManager, get_history_manager
from .cut_widget import CutWidget, CutSettings
from .dummy_points_widget import DummyPointsWidget, DummyPointsSettings
from .save_widget import SaveWidget, SaveSettings

__all__ = [
    'TargetBuilderWidget',
    'CurveTreeWidget',
    'CurveData',
    'CurveType',
    'PropertiesPanel',
    'AddCurveDialog',
    'AveragingDialog',
    'SummaryDialog',
    'CanvasPreviewWindow',
    'CurveHistoryManager',
    'get_history_manager',
    'CutWidget',
    'CutSettings',
    'DummyPointsWidget',
    'DummyPointsSettings',
    'SaveWidget',
    'SaveSettings'
]
