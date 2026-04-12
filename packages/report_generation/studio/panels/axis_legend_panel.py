"""Axis & Legend panel – merges AxisPanel + LegendPanel into one tab."""

from ..qt_compat import QtWidgets, Signal

QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QGroupBox = QtWidgets.QGroupBox


class AxisLegendPanel(QWidget):
    """Combines AxisPanel and LegendPanel under collapsible groups."""

    changed = Signal()

    def __init__(self, axis_panel, legend_panel, parent=None):
        super().__init__(parent)
        self._axis = axis_panel
        self._legend = legend_panel

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Axis section
        axis_group = QGroupBox("Axis")
        axis_lay = QVBoxLayout(axis_group)
        axis_lay.setContentsMargins(4, 4, 4, 4)
        axis_lay.addWidget(self._axis)
        layout.addWidget(axis_group)

        # Legend section
        legend_group = QGroupBox("Legend")
        legend_lay = QVBoxLayout(legend_group)
        legend_lay.setContentsMargins(4, 4, 4, 4)
        legend_lay.addWidget(self._legend)
        layout.addWidget(legend_group)

        layout.addStretch()

        # Forward signals
        self._axis.changed.connect(self.changed)
        self._legend.changed.connect(self.changed)
