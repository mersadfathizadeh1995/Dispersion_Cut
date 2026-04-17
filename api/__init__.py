"""API orchestration layer for DC Cut.

Provides config dataclasses and operation functions that sit between
the pure core logic and the consumer interfaces (GUI, CLI, MCP).

Usage:
    from dc_cut.api.config import SessionConfig, DataLoadConfig
    from dc_cut.api.data_ops import load_data
    from dc_cut.api.edit_ops import apply_filters, remove_in_box
    from dc_cut.api.analysis_ops import compute_averages, compute_nacd
    from dc_cut.api.export_ops import export_data
    from dc_cut.api.session_io import save_session, load_session
    from dc_cut.api.pub_figures_ops import generate_publication_figure
"""
from __future__ import annotations

from dc_cut.api.config import (
    SessionConfig,
    DataLoadConfig,
    FilterConfig,
    AverageConfig,
    NearFieldConfig,
    ExportConfig,
    ViewConfig,
)

__all__ = [
    "SessionConfig",
    "DataLoadConfig",
    "FilterConfig",
    "AverageConfig",
    "NearFieldConfig",
    "ExportConfig",
    "ViewConfig",
]
