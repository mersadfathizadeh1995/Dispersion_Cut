"""
Spectrum settings panel — per-spectrum appearance controls.

Shown in the Context tab when a spectrum is selected (via the data tree).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from ...qt_compat import (
    QtWidgets, QtCore, Signal,
)
from .collapsible import CollapsibleSection

if TYPE_CHECKING:
    from ...core.models import CombinedSpectrumBarConfig, OffsetCurve


_COLORMAPS = [
    # Perceptually uniform / popular defaults
    "jet", "viridis", "plasma", "inferno", "magma", "cividis", "turbo",
    # Monochrome / neutral
    "gray", "bone", "cubehelix",
    # Sequential hues
    "Blues", "Greens", "Reds", "Purples", "YlGnBu", "YlOrRd",
    # Diverging / mirrored
    "RdBu_r", "PiYG", "BrBG", "seismic", "coolwarm", "Spectral", "RdYlBu",
    # Qualitative
    "hot", "tab20",
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
    # (attr, value) for the sheet-level ``CombinedSpectrumBarConfig``.
    combined_bar_setting_changed = Signal(str, object)

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

        # Scale the whole colorbar (size + pad + font) with one knob.
        self._spin_bar_scale = QtWidgets.QDoubleSpinBox()
        self._spin_bar_scale.setRange(0.5, 3.0)
        self._spin_bar_scale.setSingleStep(0.1)
        self._spin_bar_scale.setValue(1.0)
        self._spin_bar_scale.setDecimals(2)
        self._spin_bar_scale.valueChanged.connect(
            lambda v: self._emit("spectrum_colorbar_scale", float(v)))
        bl.addRow("Bar scale:", self._spin_bar_scale)

        layout.addWidget(bar_sec)

        # ── Advanced: combined bar (only active when multiple spectra
        #    are selected). Emits on ``combined_bar_setting_changed``
        #    and writes into ``SheetState.combined_spectrum_bar``.
        self._advanced_sec = CollapsibleSection(
            "Advanced: Combined bar (multi-select)", expanded=False,
        )
        al = self._advanced_sec.form
        al.setSpacing(4)

        self._cb_hint = QtWidgets.QLabel(
            "Select 2+ spectra in the data tree to enable."
        )
        self._cb_hint.setStyleSheet("color:#888;font-style:italic;")
        self._cb_hint.setWordWrap(True)
        al.addRow(self._cb_hint)

        self._cb_enable = QtWidgets.QCheckBox(
            "Combine into one figure-level bar"
        )
        self._cb_enable.toggled.connect(
            lambda on: self._emit_combined("enabled", bool(on)))
        al.addRow(self._cb_enable)

        self._cb_placement = QtWidgets.QComboBox()
        self._cb_placement.addItems([
            "outside_right", "outside_left", "outside_top", "outside_bottom",
        ])
        self._cb_placement.currentTextChanged.connect(
            lambda v: self._emit_combined("placement", v))
        al.addRow("Placement:", self._cb_placement)

        self._cb_orientation = QtWidgets.QComboBox()
        self._cb_orientation.addItems(["auto", "vertical", "horizontal"])
        self._cb_orientation.currentTextChanged.connect(
            lambda v: self._emit_combined("orientation", v))
        al.addRow("Orientation:", self._cb_orientation)

        self._cb_scale = QtWidgets.QDoubleSpinBox()
        self._cb_scale.setRange(0.3, 4.0)
        self._cb_scale.setSingleStep(0.1)
        self._cb_scale.setValue(1.0)
        self._cb_scale.setDecimals(2)
        self._cb_scale.valueChanged.connect(
            lambda v: self._emit_combined("scale", float(v)))
        al.addRow("Scale:", self._cb_scale)

        self._cb_pad = QtWidgets.QDoubleSpinBox()
        self._cb_pad.setRange(0.0, 0.5)
        self._cb_pad.setSingleStep(0.01)
        self._cb_pad.setValue(0.05)
        self._cb_pad.setDecimals(3)
        self._cb_pad.valueChanged.connect(
            lambda v: self._emit_combined("pad", float(v)))
        al.addRow("Pad:", self._cb_pad)

        self._cb_label = QtWidgets.QLineEdit()
        self._cb_label.setPlaceholderText("Power")
        self._cb_label.editingFinished.connect(
            lambda: self._emit_combined("label", self._cb_label.text()))
        al.addRow("Label:", self._cb_label)

        layout.addWidget(self._advanced_sec)
        # Advanced section starts disabled (single-mode default).
        self._set_advanced_enabled(False)

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
        self._spin_bar_scale.setValue(
            float(getattr(curve, "spectrum_colorbar_scale", 1.0) or 1.0)
        )

        # Single-mode: combined-bar section is disabled and collapsed.
        self._set_advanced_enabled(False)

        self._updating = False

    def show_spectra_batch(
        self,
        uids: List[str],
        curves: List["OffsetCurve"],
        combined_bar: "Optional[CombinedSpectrumBarConfig]" = None,
    ):
        """Batch editing for multiple spectra.

        ``combined_bar`` is the sheet-level :class:`CombinedSpectrumBarConfig`
        so the advanced section can seed its widgets with the current
        values. When omitted, default values are used.
        """
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
            self._spin_bar_scale.setValue(
                float(getattr(c, "spectrum_colorbar_scale", 1.0) or 1.0)
            )

        # Seed advanced combined-bar widgets from the sheet-level config.
        if combined_bar is not None:
            self._cb_enable.setChecked(bool(getattr(combined_bar, "enabled", False)))
            place = str(getattr(combined_bar, "placement", "outside_right"))
            idx = self._cb_placement.findText(place)
            if idx >= 0:
                self._cb_placement.setCurrentIndex(idx)
            orient = str(getattr(combined_bar, "orientation", "auto"))
            idx = self._cb_orientation.findText(orient)
            if idx >= 0:
                self._cb_orientation.setCurrentIndex(idx)
            self._cb_scale.setValue(
                float(getattr(combined_bar, "scale", 1.0) or 1.0)
            )
            self._cb_pad.setValue(
                float(getattr(combined_bar, "pad", 0.05) or 0.05)
            )
            self._cb_label.setText(str(getattr(combined_bar, "label", "") or ""))

        self._set_advanced_enabled(len(self._batch_uids) >= 2)

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

    def _emit_combined(self, attr: str, value):
        if self._updating:
            return
        self.combined_bar_setting_changed.emit(attr, value)

    def _set_advanced_enabled(self, on: bool) -> None:
        """Enable or disable the whole Combined bar section at once."""
        self._cb_hint.setVisible(not on)
        for w in (
            self._cb_enable, self._cb_placement, self._cb_orientation,
            self._cb_scale, self._cb_pad, self._cb_label,
        ):
            w.setEnabled(on)
