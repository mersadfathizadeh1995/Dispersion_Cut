"""Circular Array HRFK Workflow for dc_cut.

This subpackage provides multi-stage workflow management for processing
dispersion curves from circular array HRFK (High Resolution Frequency-Wavenumber)
analysis.

Workflow Stages:
    1. INITIAL - Per-array cleanup with array-specific k-limits
    2. INTERMEDIATE - Cross-array refinement with all arrays overlaid
    3. REFINED - Mode extraction and final export for dinver inversion
"""
from __future__ import annotations

from dc_cut.packages.circular_array.config import (
    Stage,
    ArrayConfig,
    WorkflowConfig,
)

from dc_cut.packages.circular_array.io import (
    load_multi_array_klimits,
    export_stage_to_mat,
    export_dinver_txt,
)

from dc_cut.packages.circular_array.orchestrator import CircularArrayOrchestrator
from dc_cut.packages.circular_array.workflow_dock import CircularArrayWorkflowDock

__all__ = [
    "Stage",
    "ArrayConfig",
    "WorkflowConfig",
    "load_multi_array_klimits",
    "export_stage_to_mat",
    "export_dinver_txt",
    "CircularArrayOrchestrator",
    "CircularArrayWorkflowDock",
]
