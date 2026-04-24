"""
Subplot settings panel — rich per-subplot configuration.

Shown in the Context tab when a subplot is selected (via tree or canvas click).
Sections: Title & Labels, X Axis, Y Axis, Legend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...qt_compat import (
    QtWidgets, QtCore, QtGui, Signal,
    Horizontal, PolicyExpanding,
)
from .collapsible import CollapsibleSection
from .fonts import CURATED_FONTS, populate_font_combo

if TYPE_CHECKING:
    from ...core.models import SubplotState, TypographyConfig


class SubplotSettingsPanel(QtWidgets.QWidget):
    """
    Rich subplot settings with collapsible sections.

    Signals
    -------
    setting_changed(str, str, object)
        (subplot_key, attribute_name, new_value)
    """

    setting_changed = Signal(str, str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._subplot_key = ""
        self._batch_keys: list = []
        self._current_sp = None
        self._batch_subplots: list = []
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Selection info label
        self._lbl_selection = QtWidgets.QLabel("")
        self._lbl_selection.setStyleSheet(
            "font-weight: bold; color: #3399FF; padding: 2px 4px;")
        self._lbl_selection.setVisible(False)
        layout.addWidget(self._lbl_selection)

        # ── Title & Labels ────────────────────────────────────────────
        title_sec = CollapsibleSection("Title && Labels", expanded=True)
        tl = title_sec.form
        tl.setSpacing(4)

        self._edit_name = QtWidgets.QLineEdit()
        self._edit_name.setPlaceholderText("Subplot name")
        self._edit_name.editingFinished.connect(
            lambda: self._emit("name", self._edit_name.text()))
        tl.addRow("Name:", self._edit_name)

        self._combo_font = QtWidgets.QComboBox()
        self._combo_font.addItems(CURATED_FONTS)
        self._combo_font.currentTextChanged.connect(
            lambda f: self._emit("font_family", f))
        tl.addRow("Font:", self._combo_font)

        self._spin_title_size = QtWidgets.QSpinBox()
        self._spin_title_size.setRange(4, 36)
        self._spin_title_size.setValue(12)
        self._spin_title_size.valueChanged.connect(
            lambda v: self._emit("title_font_size", v))
        tl.addRow("Title size:", self._spin_title_size)

        self._spin_label_size = QtWidgets.QSpinBox()
        self._spin_label_size.setRange(4, 30)
        self._spin_label_size.setValue(10)
        self._spin_label_size.valueChanged.connect(
            lambda v: self._emit("axis_label_font_size", v))
        tl.addRow("Label size:", self._spin_label_size)

        self._spin_tick_size = QtWidgets.QSpinBox()
        self._spin_tick_size.setRange(4, 24)
        self._spin_tick_size.setValue(9)
        self._spin_tick_size.valueChanged.connect(
            lambda v: self._emit("tick_label_font_size", v))
        tl.addRow("Tick size:", self._spin_tick_size)

        layout.addWidget(title_sec)

        # ── X Axis ────────────────────────────────────────────────────
        x_sec = CollapsibleSection("X Axis", expanded=True)
        xl = x_sec.form
        xl.setSpacing(4)

        self._combo_domain = QtWidgets.QComboBox()
        self._combo_domain.addItems(["frequency", "wavelength"])
        self._combo_domain.currentTextChanged.connect(
            lambda v: self._emit("x_domain", v))
        xl.addRow("Domain:", self._combo_domain)

        self._combo_xscale = QtWidgets.QComboBox()
        self._combo_xscale.addItems(["linear", "log"])
        self._combo_xscale.currentTextChanged.connect(
            lambda v: self._emit("x_scale", v))
        xl.addRow("Scale:", self._combo_xscale)

        self._combo_xtick = QtWidgets.QComboBox()
        self._combo_xtick.addItems(["plain", "sci", "eng"])
        self._combo_xtick.currentTextChanged.connect(
            lambda v: self._emit("x_tick_format", v))
        xl.addRow("Tick format:", self._combo_xtick)

        # Frequency tick style (decades / one-two-five / custom / ruler)
        # — mirrors the DC Cut properties panel.
        self._combo_freq_tick_style = QtWidgets.QComboBox()
        self._combo_freq_tick_style.addItems(
            ["decades", "one-two-five", "custom", "ruler"]
        )
        self._combo_freq_tick_style.currentTextChanged.connect(
            self._on_freq_tick_style_changed
        )
        xl.addRow("Freq ticks:", self._combo_freq_tick_style)

        self._edit_freq_custom = QtWidgets.QLineEdit()
        self._edit_freq_custom.setPlaceholderText(
            "e.g. 1,2,3,5,7,10,15,20"
        )
        self._edit_freq_custom.editingFinished.connect(
            self._on_freq_custom_ticks_changed
        )
        xl.addRow("Custom (Hz):", self._edit_freq_custom)

        # Auto + manual range
        self._chk_auto_x = QtWidgets.QCheckBox("Auto")
        self._chk_auto_x.setChecked(True)
        self._chk_auto_x.toggled.connect(self._on_auto_x)
        x_range = QtWidgets.QHBoxLayout()
        self._spin_xmin = QtWidgets.QDoubleSpinBox()
        self._spin_xmin.setRange(0, 99999)
        self._spin_xmin.setDecimals(2)
        self._spin_xmin.setEnabled(False)
        self._spin_xmax = QtWidgets.QDoubleSpinBox()
        self._spin_xmax.setRange(0, 99999)
        self._spin_xmax.setDecimals(2)
        self._spin_xmax.setEnabled(False)
        x_range.addWidget(self._spin_xmin)
        x_range.addWidget(QtWidgets.QLabel("–"))
        x_range.addWidget(self._spin_xmax)
        x_range.addWidget(self._chk_auto_x)
        xl.addRow("Range:", x_range)

        self._btn_apply_x = QtWidgets.QPushButton("Apply")
        self._btn_apply_x.setEnabled(False)
        self._btn_apply_x.clicked.connect(self._apply_x)
        xl.addRow("", self._btn_apply_x)

        self._edit_xlabel = QtWidgets.QLineEdit()
        self._edit_xlabel.setPlaceholderText("Default label")
        self._edit_xlabel.editingFinished.connect(
            lambda: self._emit("x_label", self._edit_xlabel.text()))
        xl.addRow("Label:", self._edit_xlabel)

        layout.addWidget(x_sec)

        # ── Y Axis ────────────────────────────────────────────────────
        y_sec = CollapsibleSection("Y Axis", expanded=True)
        yl = y_sec.form
        yl.setSpacing(4)

        self._combo_yscale = QtWidgets.QComboBox()
        self._combo_yscale.addItems(["linear", "log"])
        self._combo_yscale.currentTextChanged.connect(
            lambda v: self._emit("y_scale", v))
        yl.addRow("Scale:", self._combo_yscale)

        self._combo_ytick = QtWidgets.QComboBox()
        self._combo_ytick.addItems(["plain", "sci", "eng"])
        self._combo_ytick.currentTextChanged.connect(
            lambda v: self._emit("y_tick_format", v))
        yl.addRow("Tick format:", self._combo_ytick)

        self._chk_auto_y = QtWidgets.QCheckBox("Auto")
        self._chk_auto_y.setChecked(True)
        self._chk_auto_y.toggled.connect(self._on_auto_y)
        y_range = QtWidgets.QHBoxLayout()
        self._spin_ymin = QtWidgets.QDoubleSpinBox()
        self._spin_ymin.setRange(0, 99999)
        self._spin_ymin.setDecimals(2)
        self._spin_ymin.setEnabled(False)
        self._spin_ymax = QtWidgets.QDoubleSpinBox()
        self._spin_ymax.setRange(0, 99999)
        self._spin_ymax.setDecimals(2)
        self._spin_ymax.setEnabled(False)
        y_range.addWidget(self._spin_ymin)
        y_range.addWidget(QtWidgets.QLabel("–"))
        y_range.addWidget(self._spin_ymax)
        y_range.addWidget(self._chk_auto_y)
        yl.addRow("Range:", y_range)

        self._btn_apply_y = QtWidgets.QPushButton("Apply")
        self._btn_apply_y.setEnabled(False)
        self._btn_apply_y.clicked.connect(self._apply_y)
        yl.addRow("", self._btn_apply_y)

        self._edit_ylabel = QtWidgets.QLineEdit()
        self._edit_ylabel.setPlaceholderText("Default label")
        self._edit_ylabel.editingFinished.connect(
            lambda: self._emit("y_label", self._edit_ylabel.text()))
        yl.addRow("Label:", self._edit_ylabel)

        layout.addWidget(y_sec)

        # ── Legend (per-subplot override) ─────────────────────────────
        legend_sec = CollapsibleSection("Legend", expanded=False)
        ll = legend_sec.form
        ll.setSpacing(4)

        self._chk_legend_visible = QtWidgets.QCheckBox("Show legend")
        self._chk_legend_visible.setChecked(True)
        self._chk_legend_visible.toggled.connect(
            lambda v: self._emit("legend_visible", v))
        ll.addRow(self._chk_legend_visible)

        self._combo_legend_pos = QtWidgets.QComboBox()
        self._combo_legend_pos.addItems([
            "best", "upper right", "upper left", "lower left",
            "lower right", "center left", "center right",
            "lower center", "upper center", "center",
        ])
        self._combo_legend_pos.currentTextChanged.connect(
            lambda v: self._emit("legend_position", v))
        ll.addRow("Position:", self._combo_legend_pos)

        self._spin_legend_size = QtWidgets.QSpinBox()
        self._spin_legend_size.setRange(4, 24)
        self._spin_legend_size.setValue(8)
        self._spin_legend_size.valueChanged.connect(
            lambda v: self._emit("legend_font_size", v))
        ll.addRow("Font size:", self._spin_legend_size)

        self._chk_legend_frame = QtWidgets.QCheckBox("Frame")
        self._chk_legend_frame.setChecked(True)
        self._chk_legend_frame.toggled.connect(
            lambda v: self._emit("legend_frame_on", v))
        ll.addRow(self._chk_legend_frame)

        layout.addWidget(legend_sec)

        layout.addStretch(1)

    # ── Public API ────────────────────────────────────────────────────

    def show_subplot(self, sp: "SubplotState",
                     typography: "TypographyConfig" = None):
        """Populate from a SubplotState.

        ``typography`` (optional) is the sheet's global TypographyConfig used
        to display effective font/size when the subplot has no per-subplot
        override (font_family == "" or sizes == 0).
        """
        self._updating = True
        self._subplot_key = sp.key
        self._current_sp = sp
        self._batch_keys = []
        self._batch_subplots = []
        self._lbl_selection.setVisible(False)

        # Block signals across all controls during populate to avoid
        # accidentally clobbering the model with the combo's first item.
        widgets = [
            self._edit_name, self._combo_font, self._spin_title_size,
            self._spin_label_size, self._spin_tick_size,
            self._combo_domain, self._combo_xscale, self._combo_xtick,
            self._combo_freq_tick_style, self._edit_freq_custom,
            self._chk_auto_x, self._spin_xmin, self._spin_xmax,
            self._edit_xlabel, self._combo_yscale, self._combo_ytick,
            self._chk_auto_y, self._spin_ymin, self._spin_ymax,
            self._edit_ylabel, self._chk_legend_visible,
            self._combo_legend_pos, self._spin_legend_size,
            self._chk_legend_frame,
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            self._edit_name.setText(sp.name)

            # Font — curated combo. Show effective value (sp override or
            # global typography fallback) without writing to the model.
            tfont = ""
            if typography is not None:
                tfont = getattr(typography, "font_family", "") or ""
            effective_font = sp.font_family or tfont or CURATED_FONTS[0]
            populate_font_combo(self._combo_font, effective_font)

            # Sizes — show the per-subplot value when set, otherwise the
            # effective global size derived from typography.
            if typography is not None:
                title_default = typography.title_size
                label_default = typography.axis_label_size
                tick_default = typography.tick_label_size
                legend_default = typography.legend_font_size
            else:
                title_default = 12
                label_default = 10
                tick_default = 9
                legend_default = 8
            self._spin_title_size.setValue(
                sp.title_font_size if sp.title_font_size > 0 else title_default)
            self._spin_label_size.setValue(
                sp.axis_label_font_size if sp.axis_label_font_size > 0 else label_default)
            self._spin_tick_size.setValue(
                sp.tick_label_font_size if sp.tick_label_font_size > 0 else tick_default)

            # X axis
            idx = self._combo_domain.findText(sp.x_domain)
            if idx >= 0:
                self._combo_domain.setCurrentIndex(idx)
            idx = self._combo_xscale.findText(sp.x_scale)
            if idx >= 0:
                self._combo_xscale.setCurrentIndex(idx)
            idx = self._combo_xtick.findText(sp.x_tick_format)
            if idx >= 0:
                self._combo_xtick.setCurrentIndex(idx)
            freq_style = str(getattr(sp, "freq_tick_style", "one-two-five"))
            if freq_style == "one_two_five":
                freq_style = "one-two-five"
            idx = self._combo_freq_tick_style.findText(freq_style)
            if idx >= 0:
                self._combo_freq_tick_style.setCurrentIndex(idx)
            custom = getattr(sp, "freq_custom_ticks", None) or []
            self._edit_freq_custom.setText(
                ",".join(f"{float(v):g}" for v in custom)
            )
            self._edit_freq_custom.setEnabled(freq_style == "custom")
            self._chk_auto_x.setChecked(sp.auto_x)
            # Seed manual X range: prefer the user's manual range, fall
            # back to the last rendered auto limits so unchecking "Auto"
            # starts from what the user is currently seeing (not 0.0).
            seed_xlim = sp.x_range
            if not seed_xlim:
                seed_xlim = getattr(sp, "last_auto_xlim", None)
            if seed_xlim and len(seed_xlim) == 2:
                try:
                    self._spin_xmin.setValue(float(seed_xlim[0]))
                    self._spin_xmax.setValue(float(seed_xlim[1]))
                except (TypeError, ValueError):
                    pass
            self._edit_xlabel.setText(sp.x_label)

            # Y axis
            idx = self._combo_yscale.findText(sp.y_scale)
            if idx >= 0:
                self._combo_yscale.setCurrentIndex(idx)
            idx = self._combo_ytick.findText(sp.y_tick_format)
            if idx >= 0:
                self._combo_ytick.setCurrentIndex(idx)
            self._chk_auto_y.setChecked(sp.auto_y)
            seed_ylim = sp.y_range
            if not seed_ylim:
                seed_ylim = getattr(sp, "last_auto_ylim", None)
            if seed_ylim and len(seed_ylim) == 2:
                try:
                    self._spin_ymin.setValue(float(seed_ylim[0]))
                    self._spin_ymax.setValue(float(seed_ylim[1]))
                except (TypeError, ValueError):
                    pass
            self._edit_ylabel.setText(sp.y_label)

            # Legend
            legend_vis = getattr(sp, "legend_visible", None)
            self._chk_legend_visible.setChecked(
                legend_vis if legend_vis is not None else True)
            legend_pos = getattr(sp, "legend_position", "") or "best"
            idx = self._combo_legend_pos.findText(legend_pos)
            if idx >= 0:
                self._combo_legend_pos.setCurrentIndex(idx)
            leg_size = getattr(sp, "legend_font_size", 0)
            self._spin_legend_size.setValue(
                leg_size if leg_size > 0 else legend_default)
            legend_frame = getattr(sp, "legend_frame_on", None)
            self._chk_legend_frame.setChecked(
                legend_frame if legend_frame is not None else True)
        finally:
            for w in widgets:
                w.blockSignals(False)
            self._updating = False

    def show_subplots_batch(self, keys: list, subplots: list,
                            typography: "TypographyConfig" = None):
        """Batch editing for multiple subplots — common settings apply to all."""
        self._updating = True
        self._batch_keys = list(keys)
        self._batch_subplots = list(subplots or [])
        self._current_sp = None
        self._subplot_key = keys[0] if keys else ""

        self._lbl_selection.setText(f"{len(keys)} subplots selected")
        self._lbl_selection.setVisible(True)

        widgets = [
            self._edit_name, self._combo_font, self._spin_title_size,
            self._spin_label_size, self._spin_tick_size,
            self._combo_domain, self._combo_xscale, self._combo_yscale,
            self._chk_auto_x, self._spin_xmin, self._spin_xmax,
            self._chk_auto_y, self._spin_ymin, self._spin_ymax,
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            if subplots:
                sp = subplots[0]
                self._edit_name.setText("")
                self._edit_name.setPlaceholderText("(multiple)")
                tfont = ""
                if typography is not None:
                    tfont = getattr(typography, "font_family", "") or ""
                effective_font = sp.font_family or tfont or CURATED_FONTS[0]
                populate_font_combo(self._combo_font, effective_font)
                self._spin_title_size.setValue(sp.title_font_size)
                self._spin_label_size.setValue(sp.axis_label_font_size)
                self._spin_tick_size.setValue(sp.tick_label_font_size)

                # Seed axis controls from the first subplot so the
                # "Apply X/Y range" buttons have meaningful starting
                # values. The Apply buttons already broadcast to every
                # key in ``self._batch_keys`` via :meth:`_emit`.
                self._chk_auto_x.setChecked(bool(sp.auto_x))
                seed_x = sp.x_range or getattr(sp, "last_auto_xlim", None)
                if seed_x and len(seed_x) == 2:
                    try:
                        self._spin_xmin.setValue(float(seed_x[0]))
                        self._spin_xmax.setValue(float(seed_x[1]))
                    except (TypeError, ValueError):
                        pass
                self._chk_auto_y.setChecked(bool(sp.auto_y))
                seed_y = sp.y_range or getattr(sp, "last_auto_ylim", None)
                if seed_y and len(seed_y) == 2:
                    try:
                        self._spin_ymin.setValue(float(seed_y[0]))
                        self._spin_ymax.setValue(float(seed_y[1]))
                    except (TypeError, ValueError):
                        pass
                self._spin_xmin.setEnabled(not bool(sp.auto_x))
                self._spin_xmax.setEnabled(not bool(sp.auto_x))
                self._btn_apply_x.setEnabled(not bool(sp.auto_x))
                self._spin_ymin.setEnabled(not bool(sp.auto_y))
                self._spin_ymax.setEnabled(not bool(sp.auto_y))
                self._btn_apply_y.setEnabled(not bool(sp.auto_y))

                idx = self._combo_domain.findText(sp.x_domain)
                if idx >= 0:
                    self._combo_domain.setCurrentIndex(idx)
                idx = self._combo_xscale.findText(sp.x_scale)
                if idx >= 0:
                    self._combo_xscale.setCurrentIndex(idx)
                idx = self._combo_yscale.findText(sp.y_scale)
                if idx >= 0:
                    self._combo_yscale.setCurrentIndex(idx)
        finally:
            for w in widgets:
                w.blockSignals(False)
            self._updating = False

    def clear(self):
        """Reset to empty state."""
        self._subplot_key = ""

    # ── Internal ──────────────────────────────────────────────────────

    def _emit(self, attr: str, value):
        if self._updating:
            return
        if self._batch_keys and len(self._batch_keys) > 1:
            for key in self._batch_keys:
                self.setting_changed.emit(key, attr, value)
        elif self._subplot_key:
            self.setting_changed.emit(self._subplot_key, attr, value)

    def _on_auto_x(self, checked):
        self._spin_xmin.setEnabled(not checked)
        self._spin_xmax.setEnabled(not checked)
        self._btn_apply_x.setEnabled(not checked)
        # When the user disables Auto, pre-fill the spinboxes with the
        # last rendered auto limits so the starting point is what the
        # plot is showing instead of 0.0 / 0.0. For batch mode, use the
        # first selected subplot's cache as the seed (the user will
        # tweak and Apply anyway).
        if not checked and not self._updating:
            seed = None
            sp = self._current_sp
            if sp is None and self._batch_subplots:
                sp = self._batch_subplots[0]
            if sp is not None:
                seed = getattr(sp, "x_range", None) or getattr(
                    sp, "last_auto_xlim", None
                )
            if seed and len(seed) == 2:
                self._spin_xmin.blockSignals(True)
                self._spin_xmax.blockSignals(True)
                try:
                    self._spin_xmin.setValue(float(seed[0]))
                    self._spin_xmax.setValue(float(seed[1]))
                finally:
                    self._spin_xmin.blockSignals(False)
                    self._spin_xmax.blockSignals(False)
        if not self._updating:
            self._emit("auto_x", checked)

    def _on_auto_y(self, checked):
        self._spin_ymin.setEnabled(not checked)
        self._spin_ymax.setEnabled(not checked)
        self._btn_apply_y.setEnabled(not checked)
        if not checked and not self._updating:
            seed = None
            sp = self._current_sp
            if sp is None and self._batch_subplots:
                sp = self._batch_subplots[0]
            if sp is not None:
                seed = getattr(sp, "y_range", None) or getattr(
                    sp, "last_auto_ylim", None
                )
            if seed and len(seed) == 2:
                self._spin_ymin.blockSignals(True)
                self._spin_ymax.blockSignals(True)
                try:
                    self._spin_ymin.setValue(float(seed[0]))
                    self._spin_ymax.setValue(float(seed[1]))
                finally:
                    self._spin_ymin.blockSignals(False)
                    self._spin_ymax.blockSignals(False)
        if not self._updating:
            self._emit("auto_y", checked)

    def _apply_x(self):
        xmin, xmax = self._spin_xmin.value(), self._spin_xmax.value()
        if xmax > xmin:
            self._emit("x_range", (xmin, xmax))

    def _apply_y(self):
        ymin, ymax = self._spin_ymin.value(), self._spin_ymax.value()
        if ymax > ymin:
            self._emit("y_range", (ymin, ymax))

    def _on_freq_tick_style_changed(self, style: str):
        """Broadcast the freq tick style and toggle the Custom field."""
        self._edit_freq_custom.setEnabled(style == "custom")
        self._emit("freq_tick_style", style)

    def _on_freq_custom_ticks_changed(self):
        """Parse the comma-separated custom tick list and emit."""
        raw = self._edit_freq_custom.text().strip()
        vals: list = []
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                vals.append(float(part))
            except ValueError:
                continue
        self._emit("freq_custom_ticks", vals)
