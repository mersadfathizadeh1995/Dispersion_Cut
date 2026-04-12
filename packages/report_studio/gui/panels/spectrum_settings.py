"""
Spectrum settings panel — per-spectrum appearance controls.

Shown in the Context tab when a spectrum is selected (via the data tree).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import OffsetCurve


_COLORMAPS = [
    "jet", "viridis", "plasma", "inferno", "magma", "cividis",
    "hot", "coolwarm", "Spectral", "RdYlBu", "turbo",
]


class SpectrumSettingsPanel(QtWidgets.QWidget):
    """
    Spectrum appearance settings (colormap, opacity, colorbar).

    Signals
    -------
    spectrum_style_changed(str, str, object)
        (curve_uid, attr, value) — attr is spectrum_cmap, spectrum_alpha, etc.
    """

    spectrum_style_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._current_uid: str = ""
        self._batch_uids: List[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Selection info label (for batch mode)
        self._lbl_selection = QtWidgets.QLabel("")
        self._lbl_selection.setStyleSheet(
            "font-weight: bold; color: #3399FF; padding: 2px 4px;")
        self._lbl_selection.setVisible(False)
        layout.addWidget(self._lbl_selection)

        # ── Appearance ─────────────────────────────────────────────────
        sec = CollapsibleSection("Spectrum Appearance", expanded=True)
        fl = sec.form
        fl.setSpacing(4)

        # Name label
        self._lbl_name = QtWidgets.QLabel("—")
        self._lbl_name.setWordWrap(True)
        fl.addRow("Source:", self._lbl_name)

        # Colormap
        self._combo_cmap = QtWidgets.QComboBox()
        self._combo_cmap.addItems(_COLORMAPS)
        self._combo_cmap.currentTextChanged.connect(
            lambda v: self._emit("spectrum_cmap", v))
        fl.addRow("Theme:", self._combo_cmap)

        # Opacity
        self._spin_alpha = QtWidgets.QDoubleSpinBox()
        self._spin_alpha.setRange(0.0, 1.0)
        self._spin_alpha.setSingleStep(0.05)
        self._spin_alpha.setValue(0.85)
        self._spin_alpha.valueChanged.connect(
            lambda v: self._emit("spectrum_alpha", v))
        fl.addRow("Opacity:", self._spin_alpha)

        layout.addWidget(sec)

        # ── Colorbar / Legend ──────────────────────────────────────────
        bar_sec = CollapsibleSection("Colorbar", expanded=True)
        bl = bar_sec.form
        bl.setSpacing(4)

        self._chk_colorbar = QtWidgets.QCheckBox("Show colorbar")
        self._chk_colorbar.setChecked(False)
        self._chk_colorbar.toggled.connect(
            lambda v: self._emit("spectrum_colorbar", v))
        bl.addRow(self._chk_colorbar)

        self._combo_colorbar_orient = QtWidgets.QComboBox()
        self._combo_colorbar_orient.addItems(["vertical", "horizontal"])
        self._combo_colorbar_orient.currentTextChanged.connect(
            lambda v: self._emit("spectrum_colorbar_orient", v))
        bl.addRow("Orientation:", self._combo_colorbar_orient)

        self._combo_colorbar_pos = QtWidgets.QComboBox()
        self._combo_colorbar_pos.addItems(["right", "left", "top", "bottom"])
        self._combo_colorbar_pos.currentTextChanged.connect(
            lambda v: self._emit("spectrum_colorbar_position", v))
        bl.addRow("Position:", self._combo_colorbar_pos)

        self._edit_colorbar_label = QtWidgets.QLineEdit()
        self._edit_colorbar_label.setPlaceholderText("Power")
        self._edit_colorbar_label.editingFinished.connect(
            lambda: self._emit("spectrum_colorbar_label",
                               self._edit_colorbar_label.text()))
        bl.addRow("Label:", self._edit_colorbar_label)

        layout.addWidget(bar_sec)

        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def show_spectrum(self, curve: "OffsetCurve"):
        """Populate from a curve's spectrum settings."""
        self._updating = True
        self._current_uid = curve.uid
        self._batch_uids = []
        self._lbl_selection.setVisible(False)

        self._lbl_name.setText(curve.display_name)
        idx = self._combo_cmap.findText(curve.spectrum_cmap)
        if idx >= 0:
            self._combo_cmap.setCurrentIndex(idx)
        self._spin_alpha.setValue(curve.spectrum_alpha)
        self._chk_colorbar.setChecked(curve.spectrum_colorbar)

        # Colorbar details
        orient = getattr(curve, "spectrum_colorbar_orient", "vertical")
        idx = self._combo_colorbar_orient.findText(orient)
        if idx >= 0:
            self._combo_colorbar_orient.setCurrentIndex(idx)
        pos = getattr(curve, "spectrum_colorbar_position", "right")
        idx = self._combo_colorbar_pos.findText(pos)
        if idx >= 0:
            self._combo_colorbar_pos.setCurrentIndex(idx)
        self._edit_colorbar_label.setText(
            getattr(curve, "spectrum_colorbar_label", ""))

        self._updating = False

    def show_spectra_batch(self, uids: List[str], curves: List["OffsetCurve"]):
        """Batch editing for multiple spectra."""
        self._updating = True
        self._batch_uids = list(uids)
        self._current_uid = uids[0] if uids else ""

        self._lbl_selection.setText(f"{len(uids)} spectra selected")
        self._lbl_selection.setVisible(True)
        self._lbl_name.setText(f"{len(uids)} spectra")

        if curves:
            c = curves[0]
            idx = self._combo_cmap.findText(c.spectrum_cmap)
            if idx >= 0:
                self._combo_cmap.setCurrentIndex(idx)
            self._spin_alpha.setValue(c.spectrum_alpha)

        self._updating = False

    def clear(self):
        self._current_uid = ""
        self._batch_uids = []

    # ── Internal ──────────────────────────────────────────────────────

    def _emit(self, attr: str, value):
        if self._updating:
            return
        if self._batch_uids and len(self._batch_uids) > 1:
            for uid in self._batch_uids:
                self.spectrum_style_changed.emit(uid, attr, value)
        elif self._current_uid:
            self.spectrum_style_changed.emit(self._current_uid, attr, value)
