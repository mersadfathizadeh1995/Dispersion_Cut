"""Style panel – merges Typography + Spectrum into one tab."""

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QGroupBox = QtWidgets.QGroupBox


class StylePanel(QWidget):
    """Combines TypographyPanel and SpectrumThemePanel under collapsible groups."""

    changed = Signal()
    preset_requested = Signal(str)

    def __init__(self, typography_panel, spectrum_panel, parent=None):
        super().__init__(parent)
        self._typo = typography_panel
        self._spec = spectrum_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Typography section
        typo_group = QGroupBox("Typography")
        typo_lay = QVBoxLayout(typo_group)
        typo_lay.setContentsMargins(4, 4, 4, 4)
        typo_lay.addWidget(self._typo)
        layout.addWidget(typo_group)

        # Spectrum section
        spec_group = QGroupBox("Spectrum Theme")
        spec_lay = QVBoxLayout(spec_group)
        spec_lay.setContentsMargins(4, 4, 4, 4)
        spec_lay.addWidget(self._spec)
        layout.addWidget(spec_group)

        layout.addStretch()

        # Forward signals
        self._typo.changed.connect(self.changed)
        self._spec.changed.connect(self.changed)
        self._typo.preset_requested.connect(self.preset_requested)
