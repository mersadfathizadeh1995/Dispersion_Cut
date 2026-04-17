"""K-Limits panel widget.

Displays per-limit checkboxes (with All On / All Off buttons)
and manages visibility of k-limit guide overlays on the canvas.
"""
from __future__ import annotations

from typing import Optional

from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore


class KLimitsPanel(QtWidgets.QWidget):
    """Manages k-limit guide visibility in the Data tab's K-Limits sub-tab."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.c = controller

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Master show/hide ──
        self._chk_show = QtWidgets.QCheckBox("Show k-limit guides on canvas")
        self._chk_show.setChecked(bool(getattr(self.c, 'show_k_guides', False)))
        self._chk_show.toggled.connect(self._on_master_toggle)
        layout.addWidget(self._chk_show)

        # ── All On / All Off buttons ──
        btn_row = QtWidgets.QHBoxLayout()
        btn_all_on = QtWidgets.QPushButton("All On")
        btn_all_off = QtWidgets.QPushButton("All Off")
        btn_all_on.clicked.connect(lambda: self._set_all(True))
        btn_all_off.clicked.connect(lambda: self._set_all(False))
        btn_row.addWidget(btn_all_on)
        btn_row.addWidget(btn_all_off)
        layout.addLayout(btn_row)

        # ── Per-limit list ──
        self._list_widget = QtWidgets.QWidget()
        self._list_layout = QtWidgets.QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(2)
        layout.addWidget(self._list_widget)

        self._checkboxes: dict[str, QtWidgets.QCheckBox] = {}

        layout.addStretch()

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self.rebuild()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.rebuild()

    def rebuild(self) -> None:
        """Rebuild the checkbox list from controller k-limits data."""
        # Clear existing
        for cb in list(self._checkboxes.values()):
            cb.setParent(None)
            cb.deleteLater()
        self._checkboxes.clear()

        multi_klimits = getattr(self.c, '_multi_klimits', [])
        visibility = getattr(self.c, '_klimits_visibility', {})

        if not multi_klimits:
            self._status.setText("No k-limits loaded.")
            return

        self._status.setText(f"{len(multi_klimits)} k-limit set(s) available.")

        for label, kmin, kmax in multi_klimits:
            cb = QtWidgets.QCheckBox(f"{label} ({kmin:.3f} – {kmax:.3f})")
            cb.setChecked(visibility.get(label, True))
            cb.toggled.connect(
                lambda checked, lbl=label: self._on_limit_toggled(lbl, checked)
            )
            self._list_layout.addWidget(cb)
            self._checkboxes[label] = cb

    def _on_master_toggle(self, on: bool) -> None:
        self.c.show_k_guides = bool(on)
        try:
            self.c._draw_k_guides()
        except Exception:
            pass
        try:
            from dc_cut.services.prefs import set_pref
            set_pref('show_k_guides_default', bool(on))
        except Exception:
            pass

    def _on_limit_toggled(self, label: str, checked: bool) -> None:
        if not hasattr(self.c, '_klimits_visibility'):
            self.c._klimits_visibility = {}
        self.c._klimits_visibility[label] = checked
        try:
            self.c._draw_k_guides()
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass

    def _set_all(self, visible: bool) -> None:
        for label, cb in self._checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(visible)
            cb.blockSignals(False)
            if not hasattr(self.c, '_klimits_visibility'):
                self.c._klimits_visibility = {}
            self.c._klimits_visibility[label] = visible
        try:
            self.c._draw_k_guides()
            self.c.fig.canvas.draw_idle()
        except Exception:
            pass
