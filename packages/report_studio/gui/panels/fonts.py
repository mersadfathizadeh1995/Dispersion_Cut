"""Curated font families exposed to the user.

Keeping the picker short avoids the noise of a full system font list and
ensures that the selected family is widely available across operating
systems so that saved sheets render the same on different machines.

If a sheet was saved with a font that is not in this list, the helpers
here append it once to the populated combo so the value still displays
correctly in the UI.
"""

from __future__ import annotations

from typing import Optional

CURATED_FONTS = [
    "Times New Roman",
    "Arial",
    "Calibri",
    "Helvetica",
    "Cambria",
    "Georgia",
    "Verdana",
    "Tahoma",
    "Segoe UI",
    "Courier New",
]


def populate_font_combo(combo, current: str = "") -> None:
    """Fill ``combo`` (a ``QComboBox``) with the curated font list.

    If ``current`` is provided and not part of :data:`CURATED_FONTS`, it is
    appended at the end so the combo can still display it. Selection is
    set to ``current`` when possible, otherwise to the first curated entry.
    """
    combo.clear()
    combo.addItems(CURATED_FONTS)
    fam = (current or "").strip()
    if fam and fam not in CURATED_FONTS:
        combo.addItem(fam)
    if fam:
        idx = combo.findText(fam)
        if idx >= 0:
            combo.setCurrentIndex(idx)


def coerce_to_curated(family: Optional[str]) -> str:
    """Return ``family`` if it is curated, otherwise the first curated font."""
    fam = (family or "").strip()
    if fam in CURATED_FONTS:
        return fam
    return CURATED_FONTS[0]


__all__ = ["CURATED_FONTS", "coerce_to_curated", "populate_font_combo"]
