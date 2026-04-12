"""
Source-offset figure type plugin — the first (and currently only) plugin.

Handles loading dispersion curves from PKL files and spectrum data from
NPZ files.  This is the plugin that powers the existing Report Studio
workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..figure_types import FigureTypePlugin, registry
from .. import subplot_types as ST


class SourceOffsetPlugin:
    """Figure type: source-offset dispersion curves ± spectrum overlay."""

    @property
    def type_id(self) -> str:
        return "source_offset"

    @property
    def display_name(self) -> str:
        return "Source Offset Curves"

    @property
    def accepted_subplot_types(self) -> Sequence[str]:
        return (ST.COMBINED, ST.DISPERSION, ST.SPECTRUM)

    def load_data(
        self,
        pkl_path: str = "",
        npz_path: str = "",
        selected_offsets: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Load curves from *pkl_path*, optionally filtered by offset labels.

        Parameters
        ----------
        pkl_path : str
            Path to the ``.pkl`` state file (required).
        npz_path : str
            Path to the ``.npz`` spectrum file (optional).
        selected_offsets : list[str] | None
            If provided, only offsets whose labels appear here are returned.
            ``None`` = return all offsets.

        Returns
        -------
        dict
            ``{'curves': [...], 'spectra': [...]}``
        """
        from ...io.pkl_reader import read_pkl
        from ...io.spectrum_reader import read_spectrum_npz

        curves = read_pkl(pkl_path) if pkl_path else []

        # Filter by selected offsets
        if selected_offsets is not None:
            curves = [c for c in curves if c.name in selected_offsets]

        spectra = []
        if npz_path and Path(npz_path).exists():
            try:
                spectra = read_spectrum_npz(npz_path)
            except Exception:
                pass

        return {"curves": curves, "spectra": spectra}

    def settings_fields(self) -> List[Dict[str, Any]]:
        return [
            {"key": "x_domain", "label": "X Axis", "type": "combo",
             "default": "frequency", "options": ["frequency", "wavelength"]},
        ]


# Auto-register when this module is imported
_plugin = SourceOffsetPlugin()
registry.register(_plugin)
