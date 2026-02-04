"""Dock widget for theoretical dispersion curves panel."""
from __future__ import annotations

from typing import Optional, List, TYPE_CHECKING
from pathlib import Path

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui
QtCore = qt_compat.QtCore

if TYPE_CHECKING:
    from dc_cut.theoretical_curves.renderer import TheoreticalCurveRenderer


class TheoreticalCurvesDock(QtWidgets.QDockWidget):
    """Dock widget for managing theoretical dispersion curves.
    
    Contains two tabs:
    - Layers: View and control loaded curves
    - Generation: Generate curves from Geopsy reports or open CSV files
    """
    
    def __init__(
        self,
        renderer: "TheoreticalCurveRenderer",
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__("Theoretical", parent)
        self.setObjectName("TheoreticalCurvesDock")
        self.renderer = renderer
        
        try:
            self.setFeatures(
                QtWidgets.QDockWidget.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFloatable
            )
        except AttributeError:
            feats = (
                QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetMovable
                | QtWidgets.QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            self.setFeatures(feats)
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        """Build the dock UI with tabs."""
        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)
        
        self.layers_tab = self._build_layers_tab()
        self.tabs.addTab(self.layers_tab, "Layers")
        
        self.generation_tab = self._build_generation_tab()
        self.tabs.addTab(self.generation_tab, "Generation")
        
        self.setWidget(container)
    
    def _build_layers_tab(self) -> QtWidgets.QWidget:
        """Build the Layers tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.chk_enable_all = QtWidgets.QCheckBox("Enable All Theoretical Curves")
        self.chk_enable_all.setChecked(True)
        self.chk_enable_all.toggled.connect(self._on_enable_all_changed)
        layout.addWidget(self.chk_enable_all)
        
        self.layers_scroll = QtWidgets.QScrollArea()
        self.layers_scroll.setWidgetResizable(True)
        try:
            self.layers_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        except AttributeError:
            self.layers_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.layers_container = QtWidgets.QWidget()
        self.layers_layout = QtWidgets.QVBoxLayout(self.layers_container)
        self.layers_layout.setContentsMargins(0, 0, 0, 0)
        self.layers_layout.setSpacing(4)
        self.layers_scroll.setWidget(self.layers_container)
        
        layout.addWidget(self.layers_scroll)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_remove = QtWidgets.QPushButton("Remove Selected")
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        btn_layout.addWidget(self.btn_remove)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _build_generation_tab(self) -> QtWidgets.QWidget:
        """Build the Generation tab."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        
        open_group = QtWidgets.QGroupBox("Open Existing CSV")
        open_layout = QtWidgets.QVBoxLayout(open_group)
        
        self.btn_open_csv = QtWidgets.QPushButton("Open CSV File(s)...")
        self.btn_open_csv.clicked.connect(self._on_open_csv)
        open_layout.addWidget(self.btn_open_csv)
        
        layout.addWidget(open_group)
        
        gen_group = QtWidgets.QGroupBox("Generate from Report")
        gen_layout = QtWidgets.QFormLayout(gen_group)
        
        self.edit_report = QtWidgets.QLineEdit()
        self.edit_report.setPlaceholderText("Select .report file...")
        btn_browse_report = QtWidgets.QPushButton("...")
        btn_browse_report.setMaximumWidth(30)
        btn_browse_report.clicked.connect(self._browse_report)
        report_layout = QtWidgets.QHBoxLayout()
        report_layout.addWidget(self.edit_report)
        report_layout.addWidget(btn_browse_report)
        gen_layout.addRow("Report File:", report_layout)
        
        self.edit_output = QtWidgets.QLineEdit()
        self.edit_output.setPlaceholderText("Select output directory...")
        btn_browse_output = QtWidgets.QPushButton("...")
        btn_browse_output.setMaximumWidth(30)
        btn_browse_output.clicked.connect(self._browse_output)
        output_layout = QtWidgets.QHBoxLayout()
        output_layout.addWidget(self.edit_output)
        output_layout.addWidget(btn_browse_output)
        gen_layout.addRow("Output Dir:", output_layout)
        
        self.edit_geopsy_bin = QtWidgets.QLineEdit(r"C:\Geopsy.org\bin")
        gen_layout.addRow("Geopsy Bin:", self.edit_geopsy_bin)
        
        self.edit_git_bash = QtWidgets.QLineEdit(
            r"C:\Users\mersadf\AppData\Local\Programs\Git\bin\bash.exe"
        )
        gen_layout.addRow("Git Bash:", self.edit_git_bash)
        
        layout.addWidget(gen_group)
        
        params_group = QtWidgets.QGroupBox("Parameters")
        params_layout = QtWidgets.QFormLayout(params_group)
        
        self.combo_curve_type = QtWidgets.QComboBox()
        self.combo_curve_type.addItems(["Rayleigh", "Love", "Both"])
        params_layout.addRow("Curve Type:", self.combo_curve_type)
        
        self.spin_num_modes = QtWidgets.QSpinBox()
        self.spin_num_modes.setRange(1, 5)
        self.spin_num_modes.setValue(1)
        params_layout.addRow("Num Modes:", self.spin_num_modes)
        
        # Selection mode: Misfit or N Best
        selection_widget = QtWidgets.QWidget()
        selection_layout = QtWidgets.QHBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        
        self.radio_misfit = QtWidgets.QRadioButton("Misfit ≤")
        self.radio_best = QtWidgets.QRadioButton("N Best")
        self.radio_misfit.setChecked(True)
        
        self.spin_misfit = QtWidgets.QDoubleSpinBox()
        self.spin_misfit.setRange(0.01, 10.0)
        self.spin_misfit.setValue(1.0)
        self.spin_misfit.setDecimals(2)
        self.spin_misfit.setSingleStep(0.1)
        
        selection_layout.addWidget(self.radio_misfit)
        selection_layout.addWidget(self.spin_misfit)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.radio_best)
        selection_layout.addStretch()
        
        params_layout.addRow("Selection:", selection_widget)
        
        # N Profiles - shared by both modes
        self.spin_n_profiles = QtWidgets.QSpinBox()
        self.spin_n_profiles.setRange(10, 100000)
        self.spin_n_profiles.setValue(1000)
        params_layout.addRow("N Profiles:", self.spin_n_profiles)
        
        # Frequency range
        freq_widget = QtWidgets.QWidget()
        freq_layout = QtWidgets.QHBoxLayout(freq_widget)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        
        self.spin_freq_min = QtWidgets.QDoubleSpinBox()
        self.spin_freq_min.setRange(0.01, 100.0)
        self.spin_freq_min.setValue(1.0)
        self.spin_freq_min.setDecimals(2)
        self.spin_freq_min.setSuffix(" Hz")
        
        self.spin_freq_max = QtWidgets.QDoubleSpinBox()
        self.spin_freq_max.setRange(0.1, 500.0)
        self.spin_freq_max.setValue(50.0)
        self.spin_freq_max.setDecimals(1)
        self.spin_freq_max.setSuffix(" Hz")
        
        freq_layout.addWidget(self.spin_freq_min)
        freq_layout.addWidget(QtWidgets.QLabel("to"))
        freq_layout.addWidget(self.spin_freq_max)
        freq_layout.addStretch()
        
        params_layout.addRow("Freq Range:", freq_widget)
        
        self.edit_site_name = QtWidgets.QLineEdit("Site")
        params_layout.addRow("Site Name:", self.edit_site_name)
        
        layout.addWidget(params_group)
        
        self.btn_generate = QtWidgets.QPushButton("Generate Curves")
        self.btn_generate.clicked.connect(self._on_generate)
        layout.addWidget(self.btn_generate)
        
        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.progress_label)
        
        layout.addStretch()
        
        return widget
    
    def _on_selection_mode_changed(self) -> None:
        """Handle selection mode radio button change."""
        misfit_selected = self.radio_misfit.isChecked()
        self.spin_misfit.setEnabled(misfit_selected)
    
    def rebuild(self) -> None:
        """Rebuild the layers list from current curves."""
        while self.layers_layout.count():
            item = self.layers_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for curve in self.renderer.curves:
            self._add_curve_widget(curve)
        
        self.layers_layout.addStretch()
    
    def _add_curve_widget(self, curve) -> None:
        """Add a widget for a single curve."""
        from dc_cut.theoretical_curves.config import TheoreticalCurve
        
        container = QtWidgets.QGroupBox(curve.name)
        container.setCheckable(True)
        container.setChecked(curve.visible)
        container.setProperty("curve_id", curve.curve_id)
        container.toggled.connect(lambda checked, cid=curve.curve_id: self._on_curve_visibility(cid, checked))
        
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(4)
        
        chk_median = QtWidgets.QCheckBox("Median Line")
        chk_median.setChecked(curve.median_visible)
        chk_median.toggled.connect(lambda checked, cid=curve.curve_id: self._on_median_visibility(cid, checked))
        layout.addWidget(chk_median)
        
        median_style = QtWidgets.QWidget()
        median_layout = QtWidgets.QHBoxLayout(median_style)
        median_layout.setContentsMargins(20, 0, 0, 0)
        
        btn_color = QtWidgets.QPushButton()
        btn_color.setFixedSize(24, 24)
        btn_color.setStyleSheet(f"background-color: {curve.style.median_color}; border: 1px solid gray;")
        btn_color.clicked.connect(lambda _, cid=curve.curve_id, btn=btn_color: self._pick_median_color(cid, btn))
        median_layout.addWidget(QtWidgets.QLabel("Color:"))
        median_layout.addWidget(btn_color)
        median_layout.addSpacing(10)
        
        # Median opacity slider
        median_layout.addWidget(QtWidgets.QLabel("Opacity:"))
        median_opacity_slider = QtWidgets.QSlider()
        try:
            median_opacity_slider.setOrientation(QtCore.Qt.Horizontal)
        except AttributeError:
            median_opacity_slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        median_opacity_slider.setMinimum(0)
        median_opacity_slider.setMaximum(100)
        median_opacity_slider.setValue(int(curve.style.median_alpha * 100))
        median_opacity_slider.setMaximumWidth(80)
        median_opacity_slider.valueChanged.connect(lambda val, cid=curve.curve_id: self._on_median_alpha(cid, val / 100.0))
        median_layout.addWidget(median_opacity_slider)
        
        median_pct_label = QtWidgets.QLabel(f"{int(curve.style.median_alpha * 100)}%")
        median_pct_label.setMinimumWidth(30)
        median_opacity_slider.valueChanged.connect(lambda val, lbl=median_pct_label: lbl.setText(f"{val}%"))
        median_layout.addWidget(median_pct_label)
        median_layout.addStretch()
        
        layout.addWidget(median_style)
        
        chk_band = QtWidgets.QCheckBox("Uncertainty Band")
        chk_band.setChecked(curve.band_visible)
        chk_band.toggled.connect(lambda checked, cid=curve.curve_id: self._on_band_visibility(cid, checked))
        layout.addWidget(chk_band)
        
        band_style = QtWidgets.QWidget()
        band_layout = QtWidgets.QHBoxLayout(band_style)
        band_layout.setContentsMargins(20, 0, 0, 0)
        
        # Band color button
        btn_band_color = QtWidgets.QPushButton()
        btn_band_color.setFixedSize(24, 24)
        btn_band_color.setStyleSheet(f"background-color: {curve.style.band_color}; border: 1px solid gray;")
        btn_band_color.clicked.connect(lambda _, cid=curve.curve_id, btn=btn_band_color: self._pick_band_color(cid, btn))
        band_layout.addWidget(QtWidgets.QLabel("Color:"))
        band_layout.addWidget(btn_band_color)
        band_layout.addSpacing(10)
        
        band_layout.addWidget(QtWidgets.QLabel("Opacity:"))
        slider = QtWidgets.QSlider()
        try:
            slider.setOrientation(QtCore.Qt.Horizontal)
        except AttributeError:
            slider.setOrientation(QtCore.Qt.Orientation.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(int(curve.style.band_alpha * 100))
        slider.valueChanged.connect(lambda val, cid=curve.curve_id: self._on_band_alpha(cid, val / 100.0))
        band_layout.addWidget(slider, 1)
        
        pct_label = QtWidgets.QLabel(f"{int(curve.style.band_alpha * 100)}%")
        pct_label.setMinimumWidth(35)
        slider.valueChanged.connect(lambda val, lbl=pct_label: lbl.setText(f"{val}%"))
        band_layout.addWidget(pct_label)
        
        layout.addWidget(band_style)
        
        info_label = QtWidgets.QLabel(f"Mode {curve.mode} | {curve.wave_type} | {len(curve.frequencies)} pts")
        info_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_label)
        
        self.layers_layout.addWidget(container)
    
    def _on_enable_all_changed(self, enabled: bool) -> None:
        """Toggle all curves visibility."""
        for curve in self.renderer.curves:
            self.renderer.set_visibility(curve.curve_id, enabled)
        self.rebuild()
    
    def _on_curve_visibility(self, curve_id: str, visible: bool) -> None:
        """Handle curve visibility toggle."""
        self.renderer.set_visibility(curve_id, visible)
    
    def _on_median_visibility(self, curve_id: str, visible: bool) -> None:
        """Handle median line visibility toggle."""
        self.renderer.set_median_visibility(curve_id, visible)
    
    def _on_band_visibility(self, curve_id: str, visible: bool) -> None:
        """Handle band visibility toggle."""
        self.renderer.set_band_visibility(curve_id, visible)
    
    def _on_band_alpha(self, curve_id: str, alpha: float) -> None:
        """Handle band opacity change."""
        self.renderer.set_band_alpha(curve_id, alpha)
    
    def _on_median_alpha(self, curve_id: str, alpha: float) -> None:
        """Handle median line opacity change."""
        self.renderer.set_median_alpha(curve_id, alpha)
    
    def _pick_median_color(self, curve_id: str, button: QtWidgets.QPushButton) -> None:
        """Open color picker for median line."""
        curve = self.renderer.get_curve(curve_id)
        if curve is None:
            return
        
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(curve.style.median_color),
            self,
            "Select Median Color"
        )
        if color.isValid():
            hex_color = color.name()
            self.renderer.set_median_color(curve_id, hex_color)
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid gray;")
    
    def _pick_band_color(self, curve_id: str, button: QtWidgets.QPushButton) -> None:
        """Open color picker for uncertainty band."""
        curve = self.renderer.get_curve(curve_id)
        if curve is None:
            return
        
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(curve.style.band_color),
            self,
            "Select Band Color"
        )
        if color.isValid():
            hex_color = color.name()
            self.renderer.set_band_color(curve_id, hex_color)
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid gray;")
    
    def _on_remove_clicked(self) -> None:
        """Remove curves that are unchecked (hidden)."""
        to_remove = [c.curve_id for c in self.renderer.curves if not c.visible]
        
        if not to_remove:
            QtWidgets.QMessageBox.information(
                self,
                "No Selection",
                "Uncheck (hide) the curves you want to remove, then click this button."
            )
            return
        
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove Curves",
            f"Remove {len(to_remove)} unchecked curve(s)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            for cid in to_remove:
                self.renderer.remove_curve(cid)
            self.rebuild()
    
    def _on_open_csv(self) -> None:
        """Open CSV file(s) dialog."""
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Open Theoretical Curve CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if files:
            self._load_csv_files(files)
    
    def _load_csv_files(self, filepaths: List[str]) -> None:
        """Load curves from CSV files."""
        from dc_cut.theoretical_curves.io import load_multiple_csv
        
        try:
            curves = load_multiple_csv(filepaths)
            for curve in curves:
                self.renderer.add_curve(curve)
            
            self.rebuild()
            self.tabs.setCurrentIndex(0)
            
            QtWidgets.QMessageBox.information(
                self,
                "Loaded",
                f"Loaded {len(curves)} theoretical curve(s)"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to load CSV files:\n{e}"
            )
    
    def _browse_report(self) -> None:
        """Browse for report file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Geopsy Report File",
            "",
            "Report Files (*.report);;All Files (*)"
        )
        if path:
            self.edit_report.setText(path)
            if not self.edit_output.text():
                self.edit_output.setText(str(Path(path).parent / "theoretical_curves"))
    
    def _browse_output(self) -> None:
        """Browse for output directory."""
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )
        if path:
            self.edit_output.setText(path)
    
    def _on_generate(self) -> None:
        """Generate theoretical curves from report."""
        from dc_cut.theoretical_curves.config import GenerationConfig
        from dc_cut.theoretical_curves.generator import TheoreticalCurveGenerator, validate_geopsy_installation
        
        if not self.edit_report.text():
            QtWidgets.QMessageBox.warning(self, "Missing Input", "Please select a report file.")
            return
        
        if not self.edit_output.text():
            QtWidgets.QMessageBox.warning(self, "Missing Input", "Please select an output directory.")
            return
        
        geopsy_bin = self.edit_geopsy_bin.text()
        if not validate_geopsy_installation(geopsy_bin):
            QtWidgets.QMessageBox.warning(
                self,
                "Geopsy Not Found",
                f"Could not find gpdc/gpdcreport in:\n{geopsy_bin}\n\n"
                "Please verify the Geopsy installation path."
            )
            return
        
        config = GenerationConfig(
            report_file=self.edit_report.text(),
            output_dir=self.edit_output.text(),
            geopsy_bin=geopsy_bin,
            git_bash=self.edit_git_bash.text(),
            selection_mode="misfit" if self.radio_misfit.isChecked() else "best",
            n_best_profiles=self.spin_n_profiles.value(),
            misfit_max=self.spin_misfit.value(),
            max_profiles=self.spin_n_profiles.value(),
            curve_type=self.combo_curve_type.currentText(),
            num_modes=self.spin_num_modes.value(),
            site_name=self.edit_site_name.text(),
            freq_min=self.spin_freq_min.value(),
            freq_max=self.spin_freq_max.value(),
        )
        
        self.btn_generate.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("Generating curves... This may take a few minutes.")
        QtWidgets.QApplication.processEvents()
        
        try:
            generator = TheoreticalCurveGenerator(config)
            curves = generator.generate(progress_callback=lambda msg: self._update_progress(msg))
            
            for curve in curves:
                self.renderer.add_curve(curve)
            
            self.rebuild()
            self.tabs.setCurrentIndex(0)
            
            self.progress_label.setText(f"Generated {len(curves)} curves")
            
            QtWidgets.QMessageBox.information(
                self,
                "Generation Complete",
                f"Generated {len(curves)} theoretical curve(s)\n"
                f"Output: {config.output_dir}"
            )
            
        except Exception as e:
            self.progress_label.setText(f"Error: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Generation Failed",
                f"Failed to generate curves:\n{e}"
            )
        finally:
            self.btn_generate.setEnabled(True)
            self.progress_bar.setVisible(False)
    
    def _update_progress(self, message: str) -> None:
        """Update progress label."""
        self.progress_label.setText(message)
        QtWidgets.QApplication.processEvents()
