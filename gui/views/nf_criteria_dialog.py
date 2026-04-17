"""Near-field criteria settings dialog.

Lets the user configure severity thresholds, unknown-handling policy,
and the V_R onset detection threshold.
"""
from __future__ import annotations

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore

try:
    _QDialogAccepted = QtWidgets.QDialog.Accepted
except AttributeError:
    _QDialogAccepted = QtWidgets.QDialog.DialogCode.Accepted

try:
    _BtnOk = QtWidgets.QDialogButtonBox.Ok
    _BtnCancel = QtWidgets.QDialogButtonBox.Cancel
except AttributeError:
    _std = QtWidgets.QDialogButtonBox.StandardButton
    _BtnOk = _std.Ok
    _BtnCancel = _std.Cancel


class NFCriteriaDialog(QtWidgets.QDialog):
    """Pop-up dialog for configuring NF severity criteria."""

    def __init__(
        self,
        parent=None,
        clean_thr: float = 0.95,
        marginal_thr: float = 0.85,
        unknown_action: str = "unknown",
        vr_onset: float = 0.90,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Near-Field Criteria Settings")
        self.setMinimumWidth(340)

        layout = QtWidgets.QVBoxLayout(self)

        # ── Severity thresholds ──
        sev_grp = QtWidgets.QGroupBox("Severity Thresholds (V_R)")
        sf = QtWidgets.QFormLayout(sev_grp)

        self._clean_spin = QtWidgets.QDoubleSpinBox()
        self._clean_spin.setRange(0.50, 1.00)
        self._clean_spin.setDecimals(3)
        self._clean_spin.setSingleStep(0.01)
        self._clean_spin.setValue(clean_thr)
        self._clean_spin.setToolTip("V_R >= this value → Clean")
        sf.addRow("Clean (V_R ≥):", self._clean_spin)

        self._marginal_spin = QtWidgets.QDoubleSpinBox()
        self._marginal_spin.setRange(0.30, 1.00)
        self._marginal_spin.setDecimals(3)
        self._marginal_spin.setSingleStep(0.01)
        self._marginal_spin.setValue(marginal_thr)
        self._marginal_spin.setToolTip("V_R >= this but < Clean → Marginal; below → Contaminated")
        sf.addRow("Marginal (V_R ≥):", self._marginal_spin)

        layout.addWidget(sev_grp)

        # ── Unknown handling ──
        unk_grp = QtWidgets.QGroupBox("Unknown Points (λ beyond λ_max reference)")
        ul = QtWidgets.QVBoxLayout(unk_grp)
        self._unk_unknown = QtWidgets.QRadioButton("Mark as Unknown")
        self._unk_contam = QtWidgets.QRadioButton("Mark as Contaminated")
        self._unk_exclude = QtWidgets.QRadioButton("Exclude from analysis")
        ul.addWidget(self._unk_unknown)
        ul.addWidget(self._unk_contam)
        ul.addWidget(self._unk_exclude)
        if unknown_action == "contaminated":
            self._unk_contam.setChecked(True)
        elif unknown_action == "exclude":
            self._unk_exclude.setChecked(True)
        else:
            self._unk_unknown.setChecked(True)
        layout.addWidget(unk_grp)

        # ── V_R onset threshold ──
        onset_grp = QtWidgets.QGroupBox("Near-Field Onset Detection")
        of = QtWidgets.QFormLayout(onset_grp)
        self._onset_spin = QtWidgets.QDoubleSpinBox()
        self._onset_spin.setRange(0.50, 1.00)
        self._onset_spin.setDecimals(3)
        self._onset_spin.setSingleStep(0.01)
        self._onset_spin.setValue(vr_onset)
        self._onset_spin.setToolTip("V_R drops below this → NF onset detected")
        of.addRow("V_R onset threshold:", self._onset_spin)
        layout.addWidget(onset_grp)

        # ── Buttons ──
        btn_box = QtWidgets.QDialogButtonBox(_BtnOk | _BtnCancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_values(self) -> dict:
        if self._unk_contam.isChecked():
            ua = "contaminated"
        elif self._unk_exclude.isChecked():
            ua = "exclude"
        else:
            ua = "unknown"
        return {
            "clean_threshold": self._clean_spin.value(),
            "marginal_threshold": self._marginal_spin.value(),
            "unknown_action": ua,
            "vr_onset_threshold": self._onset_spin.value(),
        }
