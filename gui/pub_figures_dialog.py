"""GUI dialog for configuring publication-quality figure generation."""

from __future__ import annotations

from typing import Optional
from pathlib import Path
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

from dc_cut.core.pub_figures import PublicationFigureGenerator, PlotConfig


class PublicationFigureDialog(QtWidgets.QDialog):
    """Dialog for configuring and generating publication-quality figures."""

    def __init__(self, controller, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Export Publication Figure")
        self.resize(600, 700)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)

        # Tab widget for organized sections
        self.tabs = QtWidgets.QTabWidget(self)
        layout.addWidget(self.tabs)

        # Create tabs
        self._build_plot_type_tab()
        self._build_styling_tab()
        self._build_axes_tab()
        self._build_output_tab()

        # Buttons
        button_box = QtWidgets.QDialogButtonBox(self)
        try:
            generate_btn = QtWidgets.QDialogButtonBox.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            generate_btn = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel_btn = QtWidgets.QDialogButtonBox.StandardButton.Cancel

        button_box.setStandardButtons(generate_btn | cancel_btn)
        # Rename OK button to "Generate"
        try:
            ok_button = button_box.button(generate_btn)
            if ok_button:
                ok_button.setText("Generate")
        except Exception:
            pass

        button_box.accepted.connect(self._on_generate)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def _build_plot_type_tab(self):
        """Build the Plot Type selection tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Plot type selection
        type_group = QtWidgets.QGroupBox("Plot Type")
        type_layout = QtWidgets.QVBoxLayout(type_group)

        # FREQUENCY DOMAIN PLOTS
        freq_label = QtWidgets.QLabel("<b>Frequency Domain:</b>")
        type_layout.addWidget(freq_label)

        self.plot_type_aggregated = QtWidgets.QCheckBox("Aggregated Dispersion Curve")
        self.plot_type_per_offset = QtWidgets.QCheckBox("Per-Offset Curves")
        self.plot_type_uncertainty = QtWidgets.QCheckBox("Uncertainty Visualization")

        self.plot_type_aggregated.setChecked(True)

        # Add descriptions
        desc_aggregated = QtWidgets.QLabel(
            "Shows binned average velocity with ±1σ uncertainty envelope.\n"
            "Suitable for final dispersion curves in publications."
        )
        desc_aggregated.setWordWrap(True)
        desc_aggregated.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        desc_per_offset = QtWidgets.QLabel(
            "Shows individual curves for each active offset/layer.\n"
            "Useful for comparing multiple offsets or showing data diversity."
        )
        desc_per_offset.setWordWrap(True)
        desc_per_offset.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        desc_uncertainty = QtWidgets.QLabel(
            "Shows coefficient of variation (CV = σ/μ) as a function of frequency.\n"
            "Highlights regions with high uncertainty."
        )
        desc_uncertainty.setWordWrap(True)
        desc_uncertainty.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        type_layout.addWidget(self.plot_type_aggregated)
        type_layout.addWidget(desc_aggregated)
        type_layout.addSpacing(10)
        type_layout.addWidget(self.plot_type_per_offset)
        type_layout.addWidget(desc_per_offset)
        type_layout.addSpacing(10)
        type_layout.addWidget(self.plot_type_uncertainty)
        type_layout.addWidget(desc_uncertainty)

        # WAVELENGTH DOMAIN PLOTS (STEP 1)
        type_layout.addSpacing(15)
        wave_label = QtWidgets.QLabel("<b>Wavelength Domain:</b>")
        type_layout.addWidget(wave_label)

        self.plot_type_aggregated_wavelength = QtWidgets.QCheckBox("Aggregated (Wavelength)")
        desc_agg_wave = QtWidgets.QLabel(
            "Same as aggregated but in wavelength domain.\n"
            "Better for depth-related interpretations (λ/2 or λ/3 rules)."
        )
        desc_agg_wave.setWordWrap(True)
        desc_agg_wave.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        self.plot_type_per_offset_wavelength = QtWidgets.QCheckBox("Per-Offset (Wavelength)")
        desc_offset_wave = QtWidgets.QLabel(
            "Per-offset curves in wavelength domain.\n"
            "Shows aperture-wavelength relationships clearly."
        )
        desc_offset_wave.setWordWrap(True)
        desc_offset_wave.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        self.plot_type_dual_domain = QtWidgets.QCheckBox("Dual-Domain Comparison")
        desc_dual = QtWidgets.QLabel(
            "Side-by-side frequency and wavelength plots.\n"
            "Very common in MASW publications for comprehensive presentation."
        )
        desc_dual.setWordWrap(True)
        desc_dual.setStyleSheet("color: gray; font-style: italic; margin-left: 20px;")

        type_layout.addWidget(self.plot_type_aggregated_wavelength)
        type_layout.addWidget(desc_agg_wave)
        type_layout.addSpacing(10)
        type_layout.addWidget(self.plot_type_per_offset_wavelength)
        type_layout.addWidget(desc_offset_wave)
        type_layout.addSpacing(10)
        type_layout.addWidget(self.plot_type_dual_domain)
        type_layout.addWidget(desc_dual)

        layout.addWidget(type_group)

        # Option to generate all plot types
        self.generate_all_check = QtWidgets.QCheckBox("Generate all plot types at once")
        self.generate_all_check.setToolTip(
            "When checked, all six plot types will be generated with appropriate filenames:\n"
            "  Frequency domain:\n"
            "    - <filename>_aggregated.ext\n"
            "    - <filename>_per_offset.ext\n"
            "    - <filename>_uncertainty.ext\n"
            "  Wavelength domain:\n"
            "    - <filename>_aggregated_wavelength.ext\n"
            "    - <filename>_per_offset_wavelength.ext\n"
            "    - <filename>_dual_domain.ext"
        )
        layout.addWidget(self.generate_all_check)

        # Per-offset options (only enabled when per-offset is selected)
        offset_group = QtWidgets.QGroupBox("Per-Offset Options")
        offset_layout = QtWidgets.QFormLayout(offset_group)

        self.max_offsets_spin = QtWidgets.QSpinBox()
        self.max_offsets_spin.setRange(1, 50)
        self.max_offsets_spin.setValue(10)
        offset_layout.addRow("Maximum offsets to plot:", self.max_offsets_spin)

        layout.addWidget(offset_group)
        self.offset_group = offset_group

        # Enable/disable based on selection
        self.plot_type_per_offset.toggled.connect(self._update_per_offset_options)
        self.plot_type_per_offset_wavelength.toggled.connect(self._update_per_offset_options)
        self.offset_group.setEnabled(False)

        layout.addStretch()
        self.tabs.addTab(tab, "Plot Type")

    def _build_styling_tab(self):
        """Build the Styling options tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Use scroll area for styling tab
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)

        # Journal Preset (NEW)
        preset_group = QtWidgets.QGroupBox("Journal Preset")
        preset_layout = QtWidgets.QFormLayout(preset_group)

        self.journal_preset_combo = QtWidgets.QComboBox()
        self.journal_preset_combo.addItems(['Custom', 'Nature', 'AGU', 'Geophysics', 'Presentation', 'Poster'])
        self.journal_preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addRow("Preset:", self.journal_preset_combo)

        preset_note = QtWidgets.QLabel("Presets auto-configure figure size, DPI, and fonts")
        preset_note.setStyleSheet("color: gray; font-style: italic;")
        preset_layout.addRow("", preset_note)

        scroll_layout.addWidget(preset_group)

        # Title Settings (NEW)
        title_group = QtWidgets.QGroupBox("Title")
        title_layout = QtWidgets.QFormLayout(title_group)

        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.setPlaceholderText("Optional figure title")
        title_layout.addRow("Title:", self.title_edit)

        self.title_fontsize_spin = QtWidgets.QSpinBox()
        self.title_fontsize_spin.setRange(8, 24)
        self.title_fontsize_spin.setValue(14)
        title_layout.addRow("Title font size:", self.title_fontsize_spin)

        scroll_layout.addWidget(title_group)

        # Figure settings
        fig_group = QtWidgets.QGroupBox("Figure Settings")
        fig_layout = QtWidgets.QFormLayout(fig_group)

        self.figsize_width_spin = QtWidgets.QDoubleSpinBox()
        self.figsize_width_spin.setRange(2.0, 20.0)
        self.figsize_width_spin.setValue(8.0)
        self.figsize_width_spin.setSingleStep(0.5)
        fig_layout.addRow("Width (inches):", self.figsize_width_spin)

        self.figsize_height_spin = QtWidgets.QDoubleSpinBox()
        self.figsize_height_spin.setRange(2.0, 20.0)
        self.figsize_height_spin.setValue(6.0)
        self.figsize_height_spin.setSingleStep(0.5)
        fig_layout.addRow("Height (inches):", self.figsize_height_spin)

        self.dpi_spin = QtWidgets.QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSingleStep(50)
        fig_layout.addRow("DPI:", self.dpi_spin)

        scroll_layout.addWidget(fig_group)

        # Font settings
        font_group = QtWidgets.QGroupBox("Font Settings")
        font_layout = QtWidgets.QFormLayout(font_group)

        self.font_family_combo = QtWidgets.QComboBox()
        self.font_family_combo.addItems(['serif', 'sans-serif', 'monospace'])
        font_layout.addRow("Font family:", self.font_family_combo)

        self.font_size_spin = QtWidgets.QSpinBox()
        self.font_size_spin.setRange(6, 24)
        self.font_size_spin.setValue(11)
        font_layout.addRow("Font size:", self.font_size_spin)

        scroll_layout.addWidget(font_group)

        # Line/marker settings
        line_group = QtWidgets.QGroupBox("Line & Marker Settings")
        line_layout = QtWidgets.QFormLayout(line_group)

        self.line_width_spin = QtWidgets.QDoubleSpinBox()
        self.line_width_spin.setRange(0.5, 5.0)
        self.line_width_spin.setValue(1.5)
        self.line_width_spin.setSingleStep(0.1)
        line_layout.addRow("Line width:", self.line_width_spin)

        self.marker_size_spin = QtWidgets.QDoubleSpinBox()
        self.marker_size_spin.setRange(1.0, 10.0)
        self.marker_size_spin.setValue(4.0)
        self.marker_size_spin.setSingleStep(0.5)
        line_layout.addRow("Marker size:", self.marker_size_spin)

        # Marker style (NEW)
        self.marker_style_combo = QtWidgets.QComboBox()
        self.marker_style_combo.addItems(['o (circle)', 's (square)', '^ (triangle)', 'D (diamond)', 'x (cross)', '+ (plus)', '. (point)'])
        line_layout.addRow("Marker style:", self.marker_style_combo)

        scroll_layout.addWidget(line_group)

        # Legend settings (NEW)
        legend_group = QtWidgets.QGroupBox("Legend")
        legend_layout = QtWidgets.QFormLayout(legend_group)

        self.legend_position_combo = QtWidgets.QComboBox()
        self.legend_position_combo.addItems(['best', 'upper left', 'upper right', 'lower left', 'lower right', 'center left', 'center right', 'upper center', 'lower center'])
        legend_layout.addRow("Position:", self.legend_position_combo)

        self.legend_columns_spin = QtWidgets.QSpinBox()
        self.legend_columns_spin.setRange(1, 5)
        self.legend_columns_spin.setValue(1)
        legend_layout.addRow("Columns:", self.legend_columns_spin)

        self.legend_frameon_check = QtWidgets.QCheckBox("Show legend frame")
        self.legend_frameon_check.setChecked(False)
        legend_layout.addRow("", self.legend_frameon_check)

        scroll_layout.addWidget(legend_group)

        # Color settings
        color_group = QtWidgets.QGroupBox("Color Settings")
        color_layout = QtWidgets.QFormLayout(color_group)

        self.color_palette_combo = QtWidgets.QComboBox()
        self.color_palette_combo.addItems(['vibrant', 'muted', 'bright', 'high_contrast'])
        color_layout.addRow("Color palette:", self.color_palette_combo)

        palette_note = QtWidgets.QLabel("All palettes are colorblind-friendly")
        palette_note.setStyleSheet("color: gray; font-style: italic;")
        color_layout.addRow("", palette_note)

        self.uncertainty_alpha_spin = QtWidgets.QDoubleSpinBox()
        self.uncertainty_alpha_spin.setRange(0.0, 1.0)
        self.uncertainty_alpha_spin.setValue(0.3)
        self.uncertainty_alpha_spin.setSingleStep(0.05)
        color_layout.addRow("Uncertainty alpha:", self.uncertainty_alpha_spin)

        scroll_layout.addWidget(color_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        self.tabs.addTab(tab, "Styling")

    def _on_preset_changed(self, preset_name: str):
        """Apply journal preset settings."""
        presets = {
            'Nature': {'width': 3.5, 'height': 3.5, 'dpi': 300, 'font': 'sans-serif', 'font_size': 8},
            'AGU': {'width': 3.74, 'height': 4.53, 'dpi': 300, 'font': 'sans-serif', 'font_size': 9},
            'Geophysics': {'width': 3.5, 'height': 4.0, 'dpi': 600, 'font': 'sans-serif', 'font_size': 9},
            'Presentation': {'width': 10, 'height': 7.5, 'dpi': 150, 'font': 'sans-serif', 'font_size': 14},
            'Poster': {'width': 12, 'height': 9, 'dpi': 150, 'font': 'sans-serif', 'font_size': 16},
        }
        if preset_name in presets:
            p = presets[preset_name]
            self.figsize_width_spin.setValue(p['width'])
            self.figsize_height_spin.setValue(p['height'])
            self.dpi_spin.setValue(p['dpi'])
            idx = self.font_family_combo.findText(p['font'])
            if idx >= 0:
                self.font_family_combo.setCurrentIndex(idx)
            self.font_size_spin.setValue(p['font_size'])

    def _build_axes_tab(self):
        """Build the Axes configuration tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Grid settings
        grid_group = QtWidgets.QGroupBox("Grid")
        grid_layout = QtWidgets.QVBoxLayout(grid_group)

        self.show_grid_check = QtWidgets.QCheckBox("Show grid")
        self.show_grid_check.setChecked(True)
        grid_layout.addWidget(self.show_grid_check)

        grid_alpha_layout = QtWidgets.QHBoxLayout()
        grid_alpha_layout.addWidget(QtWidgets.QLabel("Grid alpha:"))
        self.grid_alpha_spin = QtWidgets.QDoubleSpinBox()
        self.grid_alpha_spin.setRange(0.0, 1.0)
        self.grid_alpha_spin.setValue(0.3)
        self.grid_alpha_spin.setSingleStep(0.05)
        grid_alpha_layout.addWidget(self.grid_alpha_spin)
        grid_alpha_layout.addStretch()
        grid_layout.addLayout(grid_alpha_layout)

        layout.addWidget(grid_group)

        # Labels
        labels_group = QtWidgets.QGroupBox("Axis Labels")
        labels_layout = QtWidgets.QFormLayout(labels_group)

        self.xlabel_edit = QtWidgets.QLineEdit("Frequency (Hz)")
        labels_layout.addRow("X-axis label:", self.xlabel_edit)

        self.ylabel_edit = QtWidgets.QLineEdit("Phase Velocity (m/s)")
        labels_layout.addRow("Y-axis label:", self.ylabel_edit)

        layout.addWidget(labels_group)

        # Limits
        limits_group = QtWidgets.QGroupBox("Axis Limits")
        limits_layout = QtWidgets.QFormLayout(limits_group)

        self.xlim_auto_check = QtWidgets.QCheckBox("Auto")
        self.xlim_auto_check.setChecked(True)
        limits_layout.addRow("X-axis:", self.xlim_auto_check)

        xlim_layout = QtWidgets.QHBoxLayout()
        self.xlim_min_spin = QtWidgets.QDoubleSpinBox()
        self.xlim_min_spin.setRange(0.1, 1000.0)
        self.xlim_min_spin.setValue(1.0)
        self.xlim_min_spin.setEnabled(False)
        xlim_layout.addWidget(QtWidgets.QLabel("Min:"))
        xlim_layout.addWidget(self.xlim_min_spin)
        self.xlim_max_spin = QtWidgets.QDoubleSpinBox()
        self.xlim_max_spin.setRange(0.1, 1000.0)
        self.xlim_max_spin.setValue(100.0)
        self.xlim_max_spin.setEnabled(False)
        xlim_layout.addWidget(QtWidgets.QLabel("Max:"))
        xlim_layout.addWidget(self.xlim_max_spin)
        xlim_layout.addStretch()
        limits_layout.addRow("", xlim_layout)

        self.ylim_auto_check = QtWidgets.QCheckBox("Auto")
        self.ylim_auto_check.setChecked(True)
        limits_layout.addRow("Y-axis:", self.ylim_auto_check)

        ylim_layout = QtWidgets.QHBoxLayout()
        self.ylim_min_spin = QtWidgets.QDoubleSpinBox()
        self.ylim_min_spin.setRange(0.0, 10000.0)
        self.ylim_min_spin.setValue(0.0)
        self.ylim_min_spin.setEnabled(False)
        ylim_layout.addWidget(QtWidgets.QLabel("Min:"))
        ylim_layout.addWidget(self.ylim_min_spin)
        self.ylim_max_spin = QtWidgets.QDoubleSpinBox()
        self.ylim_max_spin.setRange(0.0, 10000.0)
        self.ylim_max_spin.setValue(1000.0)
        self.ylim_max_spin.setEnabled(False)
        ylim_layout.addWidget(QtWidgets.QLabel("Max:"))
        ylim_layout.addWidget(self.ylim_max_spin)
        ylim_layout.addStretch()
        limits_layout.addRow("", ylim_layout)

        layout.addWidget(limits_group)

        # Connect auto checkboxes
        self.xlim_auto_check.toggled.connect(lambda checked: self.xlim_min_spin.setDisabled(checked))
        self.xlim_auto_check.toggled.connect(lambda checked: self.xlim_max_spin.setDisabled(checked))
        self.ylim_auto_check.toggled.connect(lambda checked: self.ylim_min_spin.setDisabled(checked))
        self.ylim_auto_check.toggled.connect(lambda checked: self.ylim_max_spin.setDisabled(checked))

        # Near-field marking
        nf_group = QtWidgets.QGroupBox("Near-Field Marking")
        nf_layout = QtWidgets.QVBoxLayout(nf_group)

        self.mark_near_field_check = QtWidgets.QCheckBox("Mark near-field data")
        self.mark_near_field_check.setChecked(True)
        nf_layout.addWidget(self.mark_near_field_check)

        nf_style_layout = QtWidgets.QHBoxLayout()
        nf_style_layout.addWidget(QtWidgets.QLabel("Style:"))
        self.nf_style_combo = QtWidgets.QComboBox()
        self.nf_style_combo.addItems(['faded', 'crossed', 'none'])
        nf_style_layout.addWidget(self.nf_style_combo)
        nf_style_layout.addStretch()
        nf_layout.addLayout(nf_style_layout)

        nf_thresh_layout = QtWidgets.QHBoxLayout()
        nf_thresh_layout.addWidget(QtWidgets.QLabel("NACD threshold:"))
        self.nacd_thresh_spin = QtWidgets.QDoubleSpinBox()
        self.nacd_thresh_spin.setRange(0.1, 10.0)
        self.nacd_thresh_spin.setValue(1.0)
        self.nacd_thresh_spin.setSingleStep(0.1)
        nf_thresh_layout.addWidget(self.nacd_thresh_spin)
        nf_thresh_layout.addStretch()
        nf_layout.addLayout(nf_thresh_layout)

        nf_alpha_layout = QtWidgets.QHBoxLayout()
        nf_alpha_layout.addWidget(QtWidgets.QLabel("Near-field alpha:"))
        self.nf_alpha_spin = QtWidgets.QDoubleSpinBox()
        self.nf_alpha_spin.setRange(0.0, 1.0)
        self.nf_alpha_spin.setValue(0.4)
        self.nf_alpha_spin.setSingleStep(0.05)
        nf_alpha_layout.addWidget(self.nf_alpha_spin)
        nf_alpha_layout.addStretch()
        nf_layout.addLayout(nf_alpha_layout)

        layout.addWidget(nf_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Axes & Limits")

    def _build_output_tab(self):
        """Build the Output settings tab."""
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)

        # Output directory
        dir_group = QtWidgets.QGroupBox("Output Directory")
        dir_layout = QtWidgets.QVBoxLayout(dir_group)

        dir_select_layout = QtWidgets.QHBoxLayout()
        self.output_dir_edit = QtWidgets.QLineEdit()
        self.output_dir_edit.setPlaceholderText("Select output directory...")
        dir_select_layout.addWidget(self.output_dir_edit)

        self.browse_button = QtWidgets.QPushButton("Browse...")
        self.browse_button.clicked.connect(self._on_browse)
        dir_select_layout.addWidget(self.browse_button)

        dir_layout.addLayout(dir_select_layout)

        # Filename options
        filename_layout = QtWidgets.QHBoxLayout()
        filename_layout.addWidget(QtWidgets.QLabel("Filename:"))
        self.filename_edit = QtWidgets.QLineEdit("dispersion_curve")
        self.filename_edit.setPlaceholderText("Enter filename (without extension)")
        filename_layout.addWidget(self.filename_edit)
        dir_layout.addLayout(filename_layout)

        note_label = QtWidgets.QLabel("Note: File extension will be added automatically based on format")
        note_label.setStyleSheet("color: gray; font-style: italic; font-size: 9pt;")
        note_label.setWordWrap(True)
        dir_layout.addWidget(note_label)

        layout.addWidget(dir_group)

        # Format
        format_group = QtWidgets.QGroupBox("Output Format")
        format_layout = QtWidgets.QVBoxLayout(format_group)

        self.format_pdf = QtWidgets.QRadioButton("PDF (vector, recommended)")
        self.format_png = QtWidgets.QRadioButton("PNG (raster)")
        self.format_svg = QtWidgets.QRadioButton("SVG (vector)")
        self.format_eps = QtWidgets.QRadioButton("EPS (vector)")

        self.format_pdf.setChecked(True)

        format_layout.addWidget(self.format_pdf)
        format_layout.addWidget(self.format_png)
        format_layout.addWidget(self.format_svg)
        format_layout.addWidget(self.format_eps)

        layout.addWidget(format_group)

        # Layout options
        layout_group = QtWidgets.QGroupBox("Layout")
        layout_layout = QtWidgets.QVBoxLayout(layout_group)

        self.tight_layout_check = QtWidgets.QCheckBox("Use tight layout")
        self.tight_layout_check.setChecked(True)
        layout_layout.addWidget(self.tight_layout_check)

        layout.addWidget(layout_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Output")

    def _on_browse(self):
        """Open dialog to select output directory."""
        # Get current directory if set
        current_dir = self.output_dir_edit.text().strip()
        if not current_dir:
            current_dir = str(Path.home())

        # Handle Qt version compatibility for ShowDirsOnly option
        try:
            # Try newer Qt6 enum style first
            options = QtWidgets.QFileDialog.Option.ShowDirsOnly
        except AttributeError:
            try:
                # Fall back to Qt5 style
                options = QtWidgets.QFileDialog.ShowDirsOnly
            except AttributeError:
                # If neither works, use no options
                options = None

        try:
            if options is not None:
                dir_path = QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Select Output Directory",
                    current_dir,
                    options
                )
            else:
                dir_path = QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Select Output Directory",
                    current_dir
                )
        except Exception as e:
            # Fallback without options if there's any error
            dir_path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory",
                current_dir
            )

        if dir_path:
            self.output_dir_edit.setText(dir_path)

    def _update_per_offset_options(self):
        """Enable/disable per-offset options based on plot type selection."""
        enabled = self.plot_type_per_offset.isChecked() or self.plot_type_per_offset_wavelength.isChecked()
        self.offset_group.setEnabled(enabled)

    def _gather_config(self) -> PlotConfig:
        """Gather configuration from UI widgets."""
        # Determine format
        if self.format_pdf.isChecked():
            output_format = 'pdf'
        elif self.format_png.isChecked():
            output_format = 'png'
        elif self.format_svg.isChecked():
            output_format = 'svg'
        else:
            output_format = 'eps'

        # Determine limits
        xlim = None
        if not self.xlim_auto_check.isChecked():
            xlim = (self.xlim_min_spin.value(), self.xlim_max_spin.value())

        ylim = None
        if not self.ylim_auto_check.isChecked():
            ylim = (self.ylim_min_spin.value(), self.ylim_max_spin.value())

        # Get marker style (extract first character)
        marker_text = self.marker_style_combo.currentText()
        marker_style = marker_text.split(' ')[0] if marker_text else 'o'

        # Get title (empty string = None)
        title = self.title_edit.text().strip() or None

        config = PlotConfig(
            figsize=(self.figsize_width_spin.value(), self.figsize_height_spin.value()),
            dpi=self.dpi_spin.value(),
            font_family=self.font_family_combo.currentText(),
            font_size=self.font_size_spin.value(),
            line_width=self.line_width_spin.value(),
            marker_size=self.marker_size_spin.value(),
            marker_style=marker_style,
            title=title,
            title_fontsize=self.title_fontsize_spin.value(),
            legend_position=self.legend_position_combo.currentText(),
            legend_columns=self.legend_columns_spin.value(),
            legend_frameon=self.legend_frameon_check.isChecked(),
            color_palette=self.color_palette_combo.currentText(),
            uncertainty_alpha=self.uncertainty_alpha_spin.value(),
            near_field_alpha=self.nf_alpha_spin.value(),
            mark_near_field=self.mark_near_field_check.isChecked(),
            near_field_style=self.nf_style_combo.currentText(),
            nacd_threshold=self.nacd_thresh_spin.value(),
            show_grid=self.show_grid_check.isChecked(),
            grid_alpha=self.grid_alpha_spin.value(),
            xlabel=self.xlabel_edit.text(),
            ylabel=self.ylabel_edit.text(),
            xlim=xlim,
            ylim=ylim,
            output_format=output_format,
            tight_layout=self.tight_layout_check.isChecked(),
        )

        return config

    def _on_generate(self):
        """Generate the publication figure(s)."""
        # Validate output directory
        output_dir = self.output_dir_edit.text().strip()
        if not output_dir:
            QtWidgets.QMessageBox.warning(
                self,
                "No Output Directory",
                "Please select an output directory."
            )
            return

        # Validate directory exists
        dir_path = Path(output_dir)
        if not dir_path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Directory Not Found",
                f"The directory does not exist:\n{output_dir}"
            )
            return

        if not dir_path.is_dir():
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Directory",
                f"The path is not a directory:\n{output_dir}"
            )
            return

        # Get filename
        filename = self.filename_edit.text().strip()
        if not filename:
            QtWidgets.QMessageBox.warning(
                self,
                "No Filename",
                "Please enter a filename."
            )
            return

        # Determine file extension based on format
        if self.format_pdf.isChecked():
            extension = ".pdf"
        elif self.format_png.isChecked():
            extension = ".png"
        elif self.format_svg.isChecked():
            extension = ".svg"
        else:
            extension = ".eps"

        # Remove extension from filename if user added one
        filename_base = Path(filename).stem

        # Gather configuration
        config = self._gather_config()

        # Create generator from controller
        try:
            generator = PublicationFigureGenerator.from_controller(self.controller)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create figure generator:\n{str(e)}"
            )
            return

        # Determine which plot types to generate
        generate_all = self.generate_all_check.isChecked()

        if generate_all:
            # Generate all six plot types (3 frequency + 3 wavelength domain)
            outputs_to_generate = [
                ('aggregated', 'aggregated'),
                ('per_offset', 'per_offset'),
                ('uncertainty', 'uncertainty'),
                ('aggregated_wavelength', 'aggregated_wavelength'),
                ('per_offset_wavelength', 'per_offset_wavelength'),
                ('dual_domain', 'dual_domain')
            ]

            # Check if any files exist
            files_to_create = []
            for plot_type, suffix in outputs_to_generate:
                output_path = str(dir_path / f"{filename_base}_{suffix}{extension}")
                files_to_create.append((plot_type, output_path))

            existing_files = [p for _, p in files_to_create if Path(p).exists()]
            if existing_files:
                file_list = '\n'.join(existing_files)
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Files Exist",
                    f"The following files already exist:\n{file_list}\n\nOverwrite?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.No:
                    return

            # Generate all plots
            try:
                generated_files = []
                for plot_type, output_path in files_to_create:
                    if plot_type == 'aggregated':
                        generator.generate_aggregated_plot(output_path=output_path, config=config)
                    elif plot_type == 'per_offset':
                        max_offsets = self.max_offsets_spin.value()
                        generator.generate_per_offset_plot(
                            output_path=output_path,
                            config=config,
                            max_offsets=max_offsets
                        )
                    elif plot_type == 'uncertainty':
                        generator.generate_uncertainty_plot(output_path=output_path, config=config)
                    elif plot_type == 'aggregated_wavelength':
                        generator.generate_aggregated_wavelength_plot(output_path=output_path, config=config)
                    elif plot_type == 'per_offset_wavelength':
                        max_offsets = self.max_offsets_spin.value()
                        generator.generate_per_offset_wavelength_plot(
                            output_path=output_path,
                            config=config,
                            max_offsets=max_offsets
                        )
                    elif plot_type == 'dual_domain':
                        generator.generate_dual_domain_plot(output_path=output_path, config=config)
                    generated_files.append(output_path)

                # Success message
                file_list = '\n'.join(generated_files)
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"All publication figures saved:\n{file_list}"
                )
                self.accept()

            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to generate figures:\n{str(e)}"
                )
        else:
            # Generate selected plot types
            # Collect which checkboxes are selected
            selected_types = []
            if self.plot_type_aggregated.isChecked():
                selected_types.append(('aggregated', 'aggregated'))
            if self.plot_type_per_offset.isChecked():
                selected_types.append(('per_offset', 'per_offset'))
            if self.plot_type_uncertainty.isChecked():
                selected_types.append(('uncertainty', 'uncertainty'))
            if self.plot_type_aggregated_wavelength.isChecked():
                selected_types.append(('aggregated_wavelength', 'aggregated_wavelength'))
            if self.plot_type_per_offset_wavelength.isChecked():
                selected_types.append(('per_offset_wavelength', 'per_offset_wavelength'))
            if self.plot_type_dual_domain.isChecked():
                selected_types.append(('dual_domain', 'dual_domain'))

            # Validate at least one type is selected
            if not selected_types:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Plot Type Selected",
                    "Please select at least one plot type to generate."
                )
                return

            # Build file list
            files_to_create = []
            for plot_type, suffix in selected_types:
                # If only one type selected, don't add suffix
                if len(selected_types) == 1:
                    output_path = str(dir_path / f"{filename_base}{extension}")
                else:
                    output_path = str(dir_path / f"{filename_base}_{suffix}{extension}")
                files_to_create.append((plot_type, output_path))

            # Check for existing files
            existing_files = [p for _, p in files_to_create if Path(p).exists()]
            if existing_files:
                file_list = '\n'.join(existing_files)
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "Files Exist",
                    f"The following files already exist:\n{file_list}\n\nOverwrite?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.No:
                    return

            # Generate all selected plots
            try:
                generated_files = []
                for plot_type, output_path in files_to_create:
                    if plot_type == 'aggregated':
                        generator.generate_aggregated_plot(output_path=output_path, config=config)
                    elif plot_type == 'per_offset':
                        max_offsets = self.max_offsets_spin.value()
                        generator.generate_per_offset_plot(
                            output_path=output_path,
                            config=config,
                            max_offsets=max_offsets
                        )
                    elif plot_type == 'uncertainty':
                        generator.generate_uncertainty_plot(output_path=output_path, config=config)
                    elif plot_type == 'aggregated_wavelength':
                        generator.generate_aggregated_wavelength_plot(output_path=output_path, config=config)
                    elif plot_type == 'per_offset_wavelength':
                        max_offsets = self.max_offsets_spin.value()
                        generator.generate_per_offset_wavelength_plot(
                            output_path=output_path,
                            config=config,
                            max_offsets=max_offsets
                        )
                    elif plot_type == 'dual_domain':
                        generator.generate_dual_domain_plot(output_path=output_path, config=config)
                    generated_files.append(output_path)

                # Success message
                file_list = '\n'.join(generated_files)
                if len(generated_files) == 1:
                    msg = f"Publication figure saved to:\n{file_list}"
                else:
                    msg = f"Publication figures saved:\n{file_list}"
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    msg
                )

                self.accept()

            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to generate figure:\n{str(e)}"
                )
