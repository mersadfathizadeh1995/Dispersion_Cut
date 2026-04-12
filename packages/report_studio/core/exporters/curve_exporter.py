"""
Curve data exporter — export dispersion curve data to CSV/TXT/Excel.
"""

from __future__ import annotations

import csv
import os
from typing import TYPE_CHECKING, Any, Dict

from .base import AbstractExporter

if TYPE_CHECKING:
    from ..models import SheetState


class CurveExporter(AbstractExporter):
    """Export dispersion curve data."""

    @property
    def name(self) -> str:
        return "Dispersion Curves"

    def can_export(self, sheet: "SheetState") -> bool:
        for sp in sheet.subplots.values():
            if sp.curve_uids:
                return True
        return False

    def export(self, sheet: "SheetState", path: str,
               options: Dict[str, Any]) -> str:
        fmt = options.get("format", "csv")
        exported = 0
        for sp in sheet.subplots.values():
            for uid in sp.curve_uids:
                curve = sheet.curves.get(uid)
                if not curve:
                    continue
                fname = f"{curve.display_name}.{fmt}"
                fpath = os.path.join(path, _safe_name(fname))
                if fmt == "csv":
                    _write_csv(curve, fpath)
                elif fmt == "txt":
                    _write_txt(curve, fpath)
                elif fmt == "excel":
                    _write_excel(curve, fpath)
                exported += 1
        return f"Exported {exported} curves to {path}"


def _safe_name(name: str) -> str:
    """Make a filesystem-safe filename."""
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)


def _write_csv(curve, path: str):
    import numpy as np
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frequency", "phase_velocity"])
        mask = curve.point_mask if curve.point_mask is not None else \
            np.ones(curve.n_points, dtype=bool)
        for i in range(curve.n_points):
            if mask[i]:
                writer.writerow([curve.frequency[i], curve.velocity[i]])


def _write_txt(curve, path: str):
    import numpy as np
    mask = curve.point_mask if curve.point_mask is not None else \
        np.ones(curve.n_points, dtype=bool)
    with open(path, "w") as f:
        f.write("# frequency  phase_velocity\n")
        for i in range(curve.n_points):
            if mask[i]:
                f.write(f"{curve.frequency[i]:.6f}  {curve.velocity[i]:.6f}\n")


def _write_excel(curve, path: str):
    """Write using openpyxl if available, otherwise fall back to CSV."""
    try:
        import openpyxl
        import numpy as np
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dispersion"
        ws.append(["frequency", "phase_velocity"])
        mask = curve.point_mask if curve.point_mask is not None else \
            np.ones(curve.n_points, dtype=bool)
        for i in range(curve.n_points):
            if mask[i]:
                ws.append([float(curve.frequency[i]),
                           float(curve.velocity[i])])
        xlsx_path = path.rsplit(".", 1)[0] + ".xlsx"
        wb.save(xlsx_path)
    except ImportError:
        _write_csv(curve, path.rsplit(".", 1)[0] + ".csv")
