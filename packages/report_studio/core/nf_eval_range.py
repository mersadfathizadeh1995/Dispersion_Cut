"""Apply :class:`EvaluationRange` to :class:`NFAnalysis` (limit lines + optional mask)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

import numpy as np

if TYPE_CHECKING:
    from .models import NFAnalysis, NFLine


def _display_for_derived(kind: str, role: str, value: float) -> str:
    if kind == "lambda":
        return f"λ / {role} = {value:g} m"
    return f"f / {role} = {value:g} Hz"


def apply_eval_range_to_nf(nf: "NFAnalysis", eval_range_dict: Dict[str, Any]) -> None:
    """Store *eval_range_dict*, re-derive limit lines, optionally refresh contamination mask.

    Keeps lines with ``lambda_max_curve=True``. Replaces all other guide/limit lines
    with a fresh ``derive_limits`` pass for each ``per_offset`` row.
    """
    try:
        from dc_cut.core.processing.nearfield.ranges import (
            EvaluationRange,
            compute_range_mask,
        )
        from dc_cut.core.processing.nearfield.range_derivation import derive_limits
    except ImportError:
        return

    from .models import NFLine

    er = EvaluationRange.from_dict(eval_range_dict)
    nf.settings["eval_range"] = er.to_dict()

    preserved: List[NFLine] = [ln for ln in nf.lines if ln.lambda_max_curve]
    new_lines: List[NFLine] = []

    for r in nf.per_offset:
        dls = derive_limits(er, r.f, r.v)
        for dl in dls.lines:
            new_lines.append(
                NFLine(
                    band_index=int(dl.band_index),
                    kind=str(dl.kind),
                    role=str(dl.role),
                    value=float(dl.value),
                    source=str(dl.source),
                    valid=bool(dl.valid),
                    derived_from=dl.derived_from,
                    source_offset=r.source_offset,
                    offset_label=r.label,
                    display_label=_display_for_derived(
                        str(dl.kind), str(dl.role), float(dl.value)
                    ),
                )
            )
        if nf.use_range_as_mask and r.f.size and r.v.size:
            inside = compute_range_mask(r.f, r.v, er)
            mask = ~inside
            r.mask_contaminated = np.asarray(mask, dtype=bool)
            r.n_contaminated = int(np.sum(r.mask_contaminated))
            r.n_clean = int(len(r.f) - r.n_contaminated)
            r.n_total = int(len(r.f))

    nf.lines = preserved + new_lines
