from __future__ import annotations

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore    = qt_compat.QtCore


class ColumnMapperDialog(QtWidgets.QDialog):
    """Column mapping dialog for Geopsy .max files.
    
    Allows user to map columns to data types (Frequency, Slowness/Velocity, etc.).
    """
    
    def __init__(self, columns_data, parent=None, total_data_lines: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Map .max File Columns")
        self.resize(800, 550)
        self.columns_data = columns_data  # List of column arrays
        self.mapping = {}  # {col_idx: type_str}
        self.total_data_lines = total_data_lines
        self.data_start_line = 0
        
        v = QtWidgets.QVBoxLayout(self)
        
        # Data start line control
        start_layout = QtWidgets.QHBoxLayout()
        start_layout.addWidget(QtWidgets.QLabel("Data starts at line:"))
        self.spin_start_line = QtWidgets.QSpinBox(self)
        self.spin_start_line.setRange(0, max(0, total_data_lines - 1))
        self.spin_start_line.setValue(0)
        self.spin_start_line.setToolTip("Skip this many data lines from the beginning")
        start_layout.addWidget(self.spin_start_line)
        start_layout.addWidget(QtWidgets.QLabel(f"(of {total_data_lines} total lines)"))
        start_layout.addStretch()
        v.addLayout(start_layout)
        
        v.addWidget(QtWidgets.QLabel("<b>Map each column to its data type:</b>"))
        
        # Status label
        self.status_label = QtWidgets.QLabel("")
        v.addWidget(self.status_label)
        
        # Scroll area for columns
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded if hasattr(QtCore.Qt, 'ScrollBarPolicy') else QtCore.Qt.ScrollBarAsNeeded)
        
        # Container for columns
        container = QtWidgets.QWidget()
        self.col_layout = QtWidgets.QHBoxLayout(container)
        self.col_layout.setSpacing(4)
        scroll.setWidget(container)
        v.addWidget(scroll, 1)
        
        # Column type options
        self.type_options = [
            "Skipped",
            "Frequency (Hz)",
            "Slowness (s/km)",
            "Velocity (m/s)",
            "Wavelength (m)",
            "Power/Amplitude",
            "Azimuth",
            "Time (s)"
        ]
        
        # Create column widgets
        self.combo_boxes = []
        for i, col_data in enumerate(columns_data):
            col_widget = self._make_column_widget(i, col_data)
            self.col_layout.addWidget(col_widget)
        
        # Remember mapping checkbox
        self.chk_remember = QtWidgets.QCheckBox("Remember this mapping for similar files", self)
        v.addWidget(self.chk_remember)
        
        # Buttons
        btns = QtWidgets.QDialogButtonBox(self)
        try:
            ok = QtWidgets.QDialogButtonBox.Ok
            cancel = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        btns.setStandardButtons(ok | cancel)
        self.btn_ok = btns.button(ok)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        
        # Auto-detect and validate
        self._auto_detect()
        self._validate()
    
    def _make_column_widget(self, col_idx, col_data):
        """Create widget for one column."""
        w = QtWidgets.QWidget()
        w.setMinimumWidth(120)
        w.setMaximumWidth(200)
        vbox = QtWidgets.QVBoxLayout(w)
        vbox.setContentsMargins(2, 2, 2, 2)
        
        # Column header
        lbl = QtWidgets.QLabel(f"<b>Column {col_idx + 1}</b>")
        try:
            lbl.setAlignment(QtCore.Qt.AlignCenter)
        except AttributeError:
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl)
        
        # Type selector
        combo = QtWidgets.QComboBox(w)
        combo.addItems(self.type_options)
        combo.currentTextChanged.connect(lambda: self._validate())
        self.combo_boxes.append(combo)
        vbox.addWidget(combo)
        
        # Data preview (ALL rows with vertical scroll)
        preview = QtWidgets.QTextEdit(w)
        preview.setReadOnly(True)
        preview.setMaximumHeight(350)
        # Show ALL data rows, not just first 20
        preview_text = "\n".join([f"{val:.6g}" if isinstance(val, (int, float)) else str(val) for val in col_data])
        preview.setPlainText(preview_text)
        # Vertical scrollbar will appear automatically when needed
        vbox.addWidget(preview, 1)
        
        return w
    
    def _auto_detect(self):
        """Auto-detect column types based on Geopsy .max format and data patterns.
        
        Standard Geopsy .max format has 7 columns:
        1. Time (seconds_from_start)
        2. Frequency (cfreq in Hz)
        3. Slowness (slow in s/km)
        4. Azimuth (az)
        5. Phi (math_phi)
        6. Semblance (coherence)
        7. Beam power (beampow)
        """
        import numpy as np
        
        # If exactly 7 columns, assume standard Geopsy format
        if len(self.combo_boxes) == 7:
            self.combo_boxes[0].setCurrentText("Time (s)")
            self.combo_boxes[1].setCurrentText("Frequency (Hz)")
            self.combo_boxes[2].setCurrentText("Slowness (s/km)")
            self.combo_boxes[3].setCurrentText("Azimuth")
            self.combo_boxes[4].setCurrentText("Skipped")  # phi
            self.combo_boxes[5].setCurrentText("Skipped")  # semblance
            self.combo_boxes[6].setCurrentText("Power/Amplitude")
            return
        
        # Otherwise, use pattern detection
        for i, col_data in enumerate(self.columns_data):
            if i >= len(self.combo_boxes):
                break
            
            # Try to convert to numeric, skip if fails (text column)
            try:
                arr = np.array(col_data, dtype=float)
                arr = arr[np.isfinite(arr)]  # Remove NaN/inf
            except (ValueError, TypeError):
                # Non-numeric column (e.g., station names, polarization text)
                continue
            
            if arr.size == 0:
                continue
            
            min_val = float(np.min(arr))
            max_val = float(np.max(arr))
            mean_val = float(np.mean(arr))
            
            # Detect frequency: typically 1-100 Hz, monotonically increasing
            is_increasing = np.all(np.diff(arr) >= 0) if arr.size > 1 else False
            if is_increasing and 0.5 <= min_val <= 100 and 1 <= max_val <= 200:
                self.combo_boxes[i].setCurrentText("Frequency (Hz)")
            
            # Detect slowness: s/km values typically 0.2 - 5.0 (for vel 200-5000 m/s)
            elif 0.1 <= min_val <= 10.0 and 0.15 <= max_val <= 15.0:
                self.combo_boxes[i].setCurrentText("Slowness (s/km)")
            
            # Detect velocity: larger values (50-5000 m/s)
            elif 50 <= min_val and max_val <= 10000:
                self.combo_boxes[i].setCurrentText("Velocity (m/s)")
            
            # Detect wavelength: medium range (1-500 m)
            elif 0.5 <= min_val <= 1000 and mean_val < max_val * 0.8:
                self.combo_boxes[i].setCurrentText("Wavelength (m)")
            
            # Default: keep as Skipped
            else:
                pass  # Leave at default (Skipped)
    
    def _validate(self):
        """Validate required columns are mapped."""
        types = [cb.currentText() for cb in self.combo_boxes]
        has_freq = "Frequency (Hz)" in types
        has_vel = "Velocity (m/s)" in types or "Slowness (s/km)" in types
        
        if has_freq and has_vel:
            self.status_label.setText("✅ <span style='color:green;'>Valid mapping</span>")
            self.btn_ok.setEnabled(True)
        else:
            missing = []
            if not has_freq:
                missing.append("Frequency")
            if not has_vel:
                missing.append("Velocity or Slowness")
            self.status_label.setText(f"❌ <span style='color:red;'>Missing: {', '.join(missing)}</span>")
            self.btn_ok.setEnabled(False)
    
    def get_mapping(self):
        """Return column mapping dict: {type_str: col_idx}."""
        mapping = {}
        for i, cb in enumerate(self.combo_boxes):
            type_str = cb.currentText()
            if type_str != "Skipped":
                mapping[type_str] = i
        return mapping
    
    def get_data_start_line(self) -> int:
        """Return the user-specified data start line."""
        return self.spin_start_line.value()


class KlimitsMapperDialog(QtWidgets.QDialog):
    """Column mapping dialog for k-limits CSV files.
    
    Allows user to map columns to kmin, kmax, and optionally diameter.
    """
    
    def __init__(self, columns_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map K-Limits CSV Columns")
        self.resize(500, 400)
        self.columns_data = columns_data
        
        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(QtWidgets.QLabel("<b>Map columns to k-limits values:</b>"))
        
        # Status label
        self.status_label = QtWidgets.QLabel("")
        v.addWidget(self.status_label)
        
        # Scroll area for columns
        scroll = QtWidgets.QScrollArea(self)
        scroll.setWidgetResizable(True)
        
        container = QtWidgets.QWidget()
        self.col_layout = QtWidgets.QHBoxLayout(container)
        self.col_layout.setSpacing(4)
        scroll.setWidget(container)
        v.addWidget(scroll, 1)
        
        # Column type options
        self.type_options = [
            "Skipped",
            "K-min (rad/m)",
            "K-max (rad/m)",
            "Diameter (m)"
        ]
        
        # Create column widgets
        self.combo_boxes = []
        for i, col_data in enumerate(columns_data):
            col_widget = self._make_column_widget(i, col_data)
            self.col_layout.addWidget(col_widget)
        
        # Default diameter for 2-column files
        default_layout = QtWidgets.QHBoxLayout()
        default_layout.addWidget(QtWidgets.QLabel("Default diameter (if not in file):"))
        self.spin_default_diameter = QtWidgets.QSpinBox(self)
        self.spin_default_diameter.setRange(1, 10000)
        self.spin_default_diameter.setValue(0)
        self.spin_default_diameter.setSpecialValueText("Use row index")
        default_layout.addWidget(self.spin_default_diameter)
        default_layout.addStretch()
        v.addLayout(default_layout)
        
        # Buttons
        btns = QtWidgets.QDialogButtonBox(self)
        try:
            ok = QtWidgets.QDialogButtonBox.Ok
            cancel = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        btns.setStandardButtons(ok | cancel)
        self.btn_ok = btns.button(ok)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        
        # Auto-detect and validate
        self._auto_detect()
        self._validate()
    
    def _make_column_widget(self, col_idx, col_data):
        """Create widget for one column."""
        w = QtWidgets.QWidget()
        w.setMinimumWidth(120)
        w.setMaximumWidth(180)
        vbox = QtWidgets.QVBoxLayout(w)
        vbox.setContentsMargins(2, 2, 2, 2)
        
        lbl = QtWidgets.QLabel(f"<b>Column {col_idx + 1}</b>")
        try:
            lbl.setAlignment(QtCore.Qt.AlignCenter)
        except AttributeError:
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(lbl)
        
        combo = QtWidgets.QComboBox(w)
        combo.addItems(self.type_options)
        combo.currentTextChanged.connect(lambda: self._validate())
        self.combo_boxes.append(combo)
        vbox.addWidget(combo)
        
        preview = QtWidgets.QTextEdit(w)
        preview.setReadOnly(True)
        preview.setMaximumHeight(250)
        preview_text = "\n".join([f"{val:.6g}" if isinstance(val, (int, float)) else str(val) for val in col_data])
        preview.setPlainText(preview_text)
        vbox.addWidget(preview, 1)
        
        return w
    
    def _auto_detect(self):
        """Auto-detect column types based on data patterns."""
        import numpy as np
        
        n_cols = len(self.combo_boxes)
        
        if n_cols == 2:
            # 2-column: assume kmin, kmax
            self.combo_boxes[0].setCurrentText("K-min (rad/m)")
            self.combo_boxes[1].setCurrentText("K-max (rad/m)")
        elif n_cols >= 3:
            # 3-column: assume diameter, kmin, kmax
            self.combo_boxes[0].setCurrentText("Diameter (m)")
            self.combo_boxes[1].setCurrentText("K-min (rad/m)")
            self.combo_boxes[2].setCurrentText("K-max (rad/m)")
    
    def _validate(self):
        """Validate required columns are mapped."""
        types = [cb.currentText() for cb in self.combo_boxes]
        has_kmin = "K-min (rad/m)" in types
        has_kmax = "K-max (rad/m)" in types
        
        if has_kmin and has_kmax:
            self.status_label.setText("✅ <span style='color:green;'>Valid mapping</span>")
            self.btn_ok.setEnabled(True)
        else:
            missing = []
            if not has_kmin:
                missing.append("K-min")
            if not has_kmax:
                missing.append("K-max")
            self.status_label.setText(f"❌ <span style='color:red;'>Missing: {', '.join(missing)}</span>")
            self.btn_ok.setEnabled(False)
    
    def get_mapping(self):
        """Return column mapping dict: {type_str: col_idx}."""
        mapping = {}
        for i, cb in enumerate(self.combo_boxes):
            type_str = cb.currentText()
            if type_str != "Skipped":
                mapping[type_str] = i
        return mapping
    
    def get_default_diameter(self) -> int:
        """Return the default diameter for 2-column files."""
        return self.spin_default_diameter.value()


class CircularArrayTab(QtWidgets.QWidget):
    """Tab for Circular Array HRFK workflow input.
    
    Allows loading raw .max files for new workflow or existing .pkl to continue.
    Supports preset diameters (500/200/50m) plus custom diameters.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.array_rows = []  # List of (diameter_spinbox, path_edit, btn_browse, btn_map)
        self.klimits_mapping = None  # Column mapping for klimits CSV
        self.array_mappings = {}  # {diameter: {'column_mapping': dict, 'data_start_line': int}}
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # Site name
        site_layout = QtWidgets.QHBoxLayout()
        site_layout.addWidget(QtWidgets.QLabel("Site Name:"))
        self.site_name = QtWidgets.QLineEdit()
        self.site_name.setPlaceholderText("e.g., Redfield")
        site_layout.addWidget(self.site_name, 1)
        layout.addLayout(site_layout)

        # Output directory (REQUIRED)
        output_group = QtWidgets.QGroupBox("Output Directory (Required)")
        output_layout = QtWidgets.QHBoxLayout(output_group)
        self.output_dir = QtWidgets.QLineEdit()
        self.output_dir.setPlaceholderText("Select output directory for all workflow files...")
        self.btn_output = QtWidgets.QPushButton("Browse...")
        self.btn_output.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_dir, 1)
        output_layout.addWidget(self.btn_output)
        layout.addWidget(output_group)

        # Array files group with dynamic table
        arrays_group = QtWidgets.QGroupBox("Array Data Files (.max)")
        arrays_vbox = QtWidgets.QVBoxLayout(arrays_group)
        
        # Use column mapping checkbox
        self.use_max_mapping = QtWidgets.QCheckBox("Use column mapping for .max files (uncheck for auto-detection)")
        self.use_max_mapping.setChecked(False)
        arrays_vbox.addWidget(self.use_max_mapping)
        
        # Table for arrays
        self.arrays_table = QtWidgets.QTableWidget()
        self.arrays_table.setColumnCount(4)
        self.arrays_table.setHorizontalHeaderLabels(["Diameter (m)", "Data File", "Browse", "Map Columns"])
        self.arrays_table.horizontalHeader().setStretchLastSection(False)
        self.arrays_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch if hasattr(QtWidgets.QHeaderView, 'ResizeMode') else QtWidgets.QHeaderView.Stretch)
        self.arrays_table.setMinimumHeight(150)
        arrays_vbox.addWidget(self.arrays_table)
        
        # Add/Remove buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_add_preset = QtWidgets.QPushButton("Add Preset (500/200/50m)")
        self.btn_add_preset.clicked.connect(self._add_preset_arrays)
        self.btn_add_custom = QtWidgets.QPushButton("Add Custom Array")
        self.btn_add_custom.clicked.connect(self._add_custom_array)
        self.btn_remove_array = QtWidgets.QPushButton("Remove Selected")
        self.btn_remove_array.clicked.connect(self._remove_selected_array)
        btn_layout.addWidget(self.btn_add_preset)
        btn_layout.addWidget(self.btn_add_custom)
        btn_layout.addWidget(self.btn_remove_array)
        btn_layout.addStretch()
        arrays_vbox.addLayout(btn_layout)
        
        layout.addWidget(arrays_group)
        
        # Initialize with preset diameters
        self._add_preset_arrays()

        # K-limits file
        klimits_group = QtWidgets.QGroupBox("K-Limits File")
        klimits_vbox = QtWidgets.QVBoxLayout(klimits_group)
        
        # Use column mapping checkbox for klimits
        self.use_klimits_mapping = QtWidgets.QCheckBox("Use column mapping for CSV (uncheck for auto-detection)")
        self.use_klimits_mapping.setChecked(False)
        klimits_vbox.addWidget(self.use_klimits_mapping)
        
        klimits_row = QtWidgets.QHBoxLayout()
        self.klimits_path = QtWidgets.QLineEdit()
        self.klimits_path.setPlaceholderText("Select k-limits .mat or .csv file...")
        self.btn_klimits = QtWidgets.QPushButton("Browse...")
        self.btn_klimits.clicked.connect(self._browse_klimits)
        self.btn_map_klimits = QtWidgets.QPushButton("Map Columns")
        self.btn_map_klimits.clicked.connect(self._map_klimits_columns)
        klimits_row.addWidget(self.klimits_path, 1)
        klimits_row.addWidget(self.btn_klimits)
        klimits_row.addWidget(self.btn_map_klimits)
        klimits_vbox.addLayout(klimits_row)
        
        layout.addWidget(klimits_group)

        # Wave type and velocity cutoff
        params_layout = QtWidgets.QHBoxLayout()

        wave_group = QtWidgets.QGroupBox("Wave Type")
        wave_layout = QtWidgets.QVBoxLayout(wave_group)
        self.wave_combined = QtWidgets.QRadioButton("Rayleigh (Combined)")
        self.wave_vertical = QtWidgets.QRadioButton("Rayleigh Vertical")
        self.wave_radial = QtWidgets.QRadioButton("Rayleigh Radial")
        self.wave_transverse = QtWidgets.QRadioButton("Love Transverse")
        self.wave_combined.setChecked(True)  # Default to combined for RTBF
        self.wave_combined.setToolTip("For RTBF files: show all Rayleigh waves (both vertical and radial components)")
        wave_layout.addWidget(self.wave_combined)
        wave_layout.addWidget(self.wave_vertical)
        wave_layout.addWidget(self.wave_radial)
        wave_layout.addWidget(self.wave_transverse)
        params_layout.addWidget(wave_group)

        vel_group = QtWidgets.QGroupBox("Velocity Cutoff")
        vel_layout = QtWidgets.QFormLayout(vel_group)
        self.vel_cutoff = QtWidgets.QDoubleSpinBox()
        self.vel_cutoff.setRange(100, 20000)
        self.vel_cutoff.setValue(6000)
        self.vel_cutoff.setSuffix(" m/s")
        vel_layout.addRow("Max velocity:", self.vel_cutoff)
        params_layout.addWidget(vel_group)

        layout.addLayout(params_layout)

        # Continue from existing session
        continue_group = QtWidgets.QGroupBox("Or Continue Existing Session")
        continue_layout = QtWidgets.QHBoxLayout(continue_group)
        self.continue_path = QtWidgets.QLineEdit()
        self.continue_path.setPlaceholderText("Load existing .pkl to continue workflow...")
        self.btn_continue = QtWidgets.QPushButton("Browse...")
        self.btn_continue.clicked.connect(lambda: self._browse_file(self.continue_path, "State Files (*.pkl)"))
        continue_layout.addWidget(self.continue_path, 1)
        continue_layout.addWidget(self.btn_continue)
        layout.addWidget(continue_group)

        layout.addStretch()

    def _browse_output(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_dir.setText(path)

    def _browse_file(self, line_edit, filter_str="Max Files (*.max)"):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select File", "", f"{filter_str};;All Files (*.*)"
        )
        if path:
            line_edit.setText(path)
    
    def _add_array_row(self, diameter: int = 100):
        """Add a row to the arrays table."""
        row = self.arrays_table.rowCount()
        self.arrays_table.insertRow(row)
        
        # Diameter spinbox
        spin_diameter = QtWidgets.QSpinBox()
        spin_diameter.setRange(1, 10000)
        spin_diameter.setValue(diameter)
        spin_diameter.setSuffix(" m")
        self.arrays_table.setCellWidget(row, 0, spin_diameter)
        
        # Path line edit
        path_edit = QtWidgets.QLineEdit()
        path_edit.setPlaceholderText(f"(Optional) {diameter}m array .max file")
        self.arrays_table.setCellWidget(row, 1, path_edit)
        
        # Browse button
        btn_browse = QtWidgets.QPushButton("Browse")
        btn_browse.clicked.connect(lambda checked, pe=path_edit: self._browse_file(pe))
        self.arrays_table.setCellWidget(row, 2, btn_browse)
        
        # Map columns button
        btn_map = QtWidgets.QPushButton("Map")
        btn_map.clicked.connect(lambda checked, r=row: self._map_array_columns(r))
        self.arrays_table.setCellWidget(row, 3, btn_map)
        
        self.array_rows.append((spin_diameter, path_edit, btn_browse, btn_map))
    
    def _add_preset_arrays(self):
        """Add preset diameter arrays (500, 200, 50m)."""
        for diameter in [500, 200, 50]:
            # Check if this diameter already exists
            exists = False
            for i in range(self.arrays_table.rowCount()):
                spin = self.arrays_table.cellWidget(i, 0)
                if spin and spin.value() == diameter:
                    exists = True
                    break
            if not exists:
                self._add_array_row(diameter)
    
    def _add_custom_array(self):
        """Add a custom array row with default diameter."""
        self._add_array_row(100)
    
    def _remove_selected_array(self):
        """Remove the selected array row."""
        rows = set(idx.row() for idx in self.arrays_table.selectedIndexes())
        for row in sorted(rows, reverse=True):
            if row < len(self.array_rows):
                self.array_rows.pop(row)
            self.arrays_table.removeRow(row)
    
    def _map_array_columns(self, row: int):
        """Open column mapper for a specific array."""
        if row >= self.arrays_table.rowCount():
            return
        
        path_edit = self.arrays_table.cellWidget(row, 1)
        path = path_edit.text().strip() if path_edit else ""
        
        if not path:
            QtWidgets.QMessageBox.warning(self, "Map Columns", "Select a file first.")
            return
        
        import os
        if not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Map Columns", f"File not found: {path}")
            return
        
        columns_data, total_lines = self._parse_max_preview(path)
        if not columns_data:
            return
        
        dlg = ColumnMapperDialog(columns_data, self, total_lines)
        if dlg.exec() == 1:
            spin = self.arrays_table.cellWidget(row, 0)
            diameter = spin.value() if spin else row
            self.array_mappings[diameter] = {
                'column_mapping': dlg.get_mapping(),
                'data_start_line': dlg.get_data_start_line()
            }
    
    def _parse_max_preview(self, path: str):
        """Parse .max file and return columns data for preview."""
        import re
        import numpy as np
        
        try:
            data_lines = []
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    if stripped[0].isdigit():
                        data_lines.append(stripped)
            
            if not data_lines:
                QtWidgets.QMessageBox.warning(self, "Map Columns", "File contains no data rows")
                return None, 0
            
            rows = []
            for line in data_lines:
                parts = re.split(r'[\s\|]+', line)
                if len(parts) >= 2:
                    rows.append(parts)
            
            if not rows:
                QtWidgets.QMessageBox.warning(self, "Map Columns", "No valid data rows found")
                return None, 0
            
            n_cols = len(rows[0])
            columns_data = []
            for col_idx in range(n_cols):
                col_values = [row[col_idx] if col_idx < len(row) else '' for row in rows]
                try:
                    numeric_vals = [float(v) for v in col_values]
                    columns_data.append(np.array(numeric_vals))
                except (ValueError, TypeError):
                    columns_data.append(np.array(col_values))
            
            return columns_data, len(data_lines)
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to read file:\n{e}")
            return None, 0
    
    def _browse_klimits(self):
        """Browse for klimits file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select K-Limits File", "",
            "K-Limits (*.mat *.csv);;MAT Files (*.mat);;CSV Files (*.csv);;All Files (*.*)"
        )
        if path:
            self.klimits_path.setText(path)
    
    def _map_klimits_columns(self):
        """Open column mapper for klimits CSV file."""
        import os
        import re
        import numpy as np
        
        path = self.klimits_path.text().strip()
        if not path:
            QtWidgets.QMessageBox.warning(self, "Map Columns", "Select a klimits file first.")
            return
        
        if not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Map Columns", f"File not found: {path}")
            return
        
        # Only CSV files can be mapped
        if not path.lower().endswith('.csv'):
            QtWidgets.QMessageBox.information(self, "Map Columns", 
                "Column mapping is only available for CSV files.\nMAT files use auto-detection.")
            return
        
        try:
            rows = []
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = [p.strip() for p in line.replace(',', ' ').split() if p.strip()]
                    if parts:
                        rows.append(parts)
            
            if not rows:
                QtWidgets.QMessageBox.warning(self, "Map Columns", "CSV file contains no data")
                return
            
            n_cols = max(len(row) for row in rows)
            columns_data = []
            for col_idx in range(n_cols):
                col_values = [float(row[col_idx]) if col_idx < len(row) else 0.0 for row in rows]
                columns_data.append(np.array(col_values))
            
            dlg = KlimitsMapperDialog(columns_data, self)
            if dlg.exec() == 1:
                self.klimits_mapping = {
                    'column_mapping': dlg.get_mapping(),
                    'default_diameter': dlg.get_default_diameter()
                }
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to read klimits file:\n{e}")

    def _get_wave_type(self) -> str:
        if self.wave_combined.isChecked():
            return "Rayleigh_Combined"
        elif self.wave_radial.isChecked():
            return "Rayleigh_Radial"
        elif self.wave_transverse.isChecked():
            return "Love_Transverse"
        return "Rayleigh_Vertical"

    def get_config(self) -> dict:
        """Get configuration dict for loading."""
        if self.continue_path.text().strip():
            return {
                'mode': 'circular_array_continue',
                'session_path': self.continue_path.text().strip(),
            }

        # Build arrays dict from table
        arrays = {}
        for row in range(self.arrays_table.rowCount()):
            spin = self.arrays_table.cellWidget(row, 0)
            path_edit = self.arrays_table.cellWidget(row, 1)
            if spin and path_edit:
                diameter = spin.value()
                path = path_edit.text().strip()
                if path:
                    arrays[diameter] = path

        return {
            'mode': 'circular_array_new',
            'site_name': self.site_name.text().strip(),
            'output_dir': self.output_dir.text().strip(),
            'wave_type': self._get_wave_type(),
            'velocity_cutoff': float(self.vel_cutoff.value()),
            'arrays': arrays,
            'klimits_path': self.klimits_path.text().strip(),
            'use_max_mapping': self.use_max_mapping.isChecked(),
            'use_klimits_mapping': self.use_klimits_mapping.isChecked(),
            'array_mappings': self.array_mappings,
            'klimits_mapping': self.klimits_mapping,
        }

    def validate(self) -> tuple:
        """Validate inputs. Returns (is_valid, error_message)."""
        if self.continue_path.text().strip():
            import os
            if not os.path.exists(self.continue_path.text().strip()):
                return False, "Session file does not exist"
            return True, ""

        if not self.site_name.text().strip():
            return False, "Site name is required"
        if not self.output_dir.text().strip():
            return False, "Output directory is required"

        import os
        if not os.path.isdir(self.output_dir.text().strip()):
            return False, "Output directory does not exist"

        # Check arrays from table
        has_array = False
        for row in range(self.arrays_table.rowCount()):
            path_edit = self.arrays_table.cellWidget(row, 1)
            if path_edit:
                path = path_edit.text().strip()
                if path:
                    has_array = True
                    if not os.path.exists(path):
                        return False, f"File not found: {path}"
        
        if not has_array:
            return False, "At least one array .max file is required"

        if not self.klimits_path.text().strip():
            return False, "K-limits file is required"
        if not os.path.exists(self.klimits_path.text().strip()):
            return False, f"K-limits file not found: {self.klimits_path.text()}"

        return True, ""


class OpenDataDialog(QtWidgets.QDialog):
    """Clean Qt dialog to open data from various sources.

    Modes:
      - Active Data: MATLAB (.mat) or CSV (.csv) via nested tabs
      - Passive Data: FK (.max + k-limits) or Passive CSV (freq, slow)
      - State: Session restore (.pkl)
      - Circular Array: Multi-stage HRFK workflow

    Use the `result` property after exec() returns Accepted.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Data")
        self.resize(520, 380)
        self.result: dict | None = None
        self.column_mapping = None  # For .max files

        v = QtWidgets.QVBoxLayout(self)

        # Main tabs: Active Data, Passive Data, State
        self.tabs = QtWidgets.QTabWidget(self)
        v.addWidget(self.tabs, 1)

        self.tab_active  = self._make_tab_active()    # Contains nested MATLAB/CSV tabs
        self.tab_passive = self._make_tab_passive()   # Passive FK data
        self.tab_state   = self._make_tab_state()     # Session restore
        self.tab_circular = CircularArrayTab(self)    # Circular Array workflow

        self.tabs.addTab(self.tab_active,  "Active Data")
        self.tabs.addTab(self.tab_passive, "Passive Data")
        self.tabs.addTab(self.tab_state,   "State")
        self.tabs.addTab(self.tab_circular, "Circular Array")

        btns = QtWidgets.QDialogButtonBox(self)
        try:
            ok = QtWidgets.QDialogButtonBox.Ok; cancel = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        btns.setStandardButtons(ok | cancel)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    # ---- Tabs ----
    def _make_tab_active(self):
        """Active Data tab with nested MATLAB and CSV sub-tabs."""
        w = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        
        # Nested tab widget for MATLAB and CSV
        self.active_tabs = QtWidgets.QTabWidget(w)
        v.addWidget(self.active_tabs, 1)
        
        # Create sub-tabs
        self.tab_matlab = self._make_subtab_matlab()
        self.tab_csv    = self._make_subtab_csv()
        
        self.active_tabs.addTab(self.tab_matlab, "MATLAB")
        self.active_tabs.addTab(self.tab_csv,    "CSV")
        
        return w
    
    def _make_subtab_matlab(self):
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)
        # file
        row = QtWidgets.QHBoxLayout()
        self.mat_path = QtWidgets.QLineEdit(w); self.mat_path.setPlaceholderText("Select .mat file...")
        btn = QtWidgets.QPushButton("Browse", w); btn.clicked.connect(lambda: self._pick_file(self.mat_path, "MAT-file", "*.mat"))
        row.addWidget(self.mat_path, 1); row.addWidget(btn)
        form.addRow("MATLAB:", row)
        # dx
        self.mat_dx = QtWidgets.QDoubleSpinBox(w); self.mat_dx.setRange(0.1, 100.0); self.mat_dx.setValue(2.0); self.mat_dx.setDecimals(2)
        form.addRow("Δx (m):", self.mat_dx)
        return w

    def _make_subtab_csv(self):
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)
        row = QtWidgets.QHBoxLayout()
        self.csv_path = QtWidgets.QLineEdit(w); self.csv_path.setPlaceholderText("Select .csv file...")
        btn = QtWidgets.QPushButton("Browse", w); btn.clicked.connect(lambda: self._pick_file(self.csv_path, "CSV", "*.csv"))
        row.addWidget(self.csv_path, 1); row.addWidget(btn)
        form.addRow("CSV:", row)

        # NEW: Spectrum .npz file (optional)
        row_spectrum = QtWidgets.QHBoxLayout()
        self.csv_spectrum_path = QtWidgets.QLineEdit(w); self.csv_spectrum_path.setPlaceholderText("(Optional) Select spectrum .npz file...")
        btn_spectrum = QtWidgets.QPushButton("Browse", w); btn_spectrum.clicked.connect(lambda: self._pick_file(self.csv_spectrum_path, "Spectrum NPZ", "*.npz"))
        row_spectrum.addWidget(self.csv_spectrum_path, 1); row_spectrum.addWidget(btn_spectrum)
        form.addRow("Spectrum:", row_spectrum)

        # Info label for spectrum
        spectrum_info = QtWidgets.QLabel("<i>Power spectrum background (optional, for visualization)</i>", w)
        spectrum_info.setWordWrap(True)
        spectrum_info.setStyleSheet("color: gray; font-size: 9pt;")
        form.addRow("", spectrum_info)

        self.csv_dx = QtWidgets.QDoubleSpinBox(w); self.csv_dx.setRange(0.1, 100.0); self.csv_dx.setValue(2.0); self.csv_dx.setDecimals(2)
        form.addRow("Δx (m):", self.csv_dx)
        # Optional velocity clamp before opening
        rowy = QtWidgets.QHBoxLayout();
        self.csv_vmin = QtWidgets.QDoubleSpinBox(w); self.csv_vmin.setRange(0.0, 1e6); self.csv_vmin.setDecimals(1); self.csv_vmin.setValue(0.0)
        self.csv_vmax = QtWidgets.QDoubleSpinBox(w); self.csv_vmax.setRange(10.0, 1e6); self.csv_vmax.setDecimals(1); self.csv_vmax.setValue(5000.0)
        rowy.addWidget(QtWidgets.QLabel("Ymin:")); rowy.addWidget(self.csv_vmin); rowy.addSpacing(6)
        rowy.addWidget(QtWidgets.QLabel("Ymax:")); rowy.addWidget(self.csv_vmax)
        form.addRow("Velocity clamp:", rowy)
        return w

    def _make_tab_state(self):
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        
        # Info label
        info = QtWidgets.QLabel("<i>State files restore a complete previous session.</i>", w)
        info.setWordWrap(True)
        form.addRow(info)
        
        # File picker
        row = QtWidgets.QHBoxLayout()
        self.state_path = QtWidgets.QLineEdit(w)
        self.state_path.setPlaceholderText("Select .pkl state file...")
        btn = QtWidgets.QPushButton("Browse", w)
        btn.clicked.connect(lambda: self._pick_file(self.state_path, "State", "*.pkl"))
        row.addWidget(self.state_path, 1)
        row.addWidget(btn)
        form.addRow("State file:", row)
        
        # Spectrum file picker (optional)
        row_spec = QtWidgets.QHBoxLayout()
        self.state_spectrum_path = QtWidgets.QLineEdit(w)
        self.state_spectrum_path.setPlaceholderText("(Optional) Select spectrum .npz file...")
        btn_spec = QtWidgets.QPushButton("Browse", w)
        btn_spec.clicked.connect(lambda: self._pick_file(self.state_spectrum_path, "Spectrum", "*.npz"))
        row_spec.addWidget(self.state_spectrum_path, 1)
        row_spec.addWidget(btn_spec)
        form.addRow("Spectrum:", row_spec)
        
        # dx optional (used for geometry when state lacks it)
        self.state_dx = QtWidgets.QDoubleSpinBox(w)
        self.state_dx.setRange(0.1, 100.0)
        self.state_dx.setValue(2.0)
        self.state_dx.setDecimals(2)
        form.addRow("Δx (m):", self.state_dx)
        
        form.addRow(QtWidgets.QLabel(""))  # Spacer
        return w

    def _make_tab_passive(self):
        w = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        
        # Checkbox: Use column mapping for .max files
        self.use_column_mapping = QtWidgets.QCheckBox("Use column mapping for .max files", w)
        self.use_column_mapping.setChecked(False)  # Unchecked by default (legacy mode)
        self.use_column_mapping.setToolTip("When checked, shows column mapper dialog for .max files.\nWhen unchecked, uses automatic detection (legacy behavior).")
        form.addRow("", self.use_column_mapping)
        
        # data file (.max or .csv)
        rowm = QtWidgets.QHBoxLayout()
        self.max_path = QtWidgets.QLineEdit(w)
        self.max_path.setPlaceholderText("Select .max or passive .csv file...")
        btnm = QtWidgets.QPushButton("Browse", w)
        btnm.clicked.connect(lambda: self._pick_passive_data())
        rowm.addWidget(self.max_path, 1)
        rowm.addWidget(btnm)
        form.addRow("Data:", rowm)
        # k-limits
        rowk = QtWidgets.QHBoxLayout()
        self.kl_path = QtWidgets.QLineEdit(w); self.kl_path.setPlaceholderText("Select k-limits (.mat or .csv)...")
        btnk = QtWidgets.QPushButton("Browse", w); btnk.clicked.connect(lambda: self._pick_file_any(self.kl_path, (("MAT", "*.mat"),("CSV","*.csv"))))
        rowk.addWidget(self.kl_path, 1); rowk.addWidget(btnk)
        form.addRow("k-limits:", rowk)
        # dx
        self.pass_dx = QtWidgets.QDoubleSpinBox(w); self.pass_dx.setRange(0.1, 100.0); self.pass_dx.setValue(2.0); self.pass_dx.setDecimals(2)
        form.addRow("Δx (m):", self.pass_dx)
        # optional time
        self.pass_time = QtWidgets.QLineEdit(w); self.pass_time.setPlaceholderText("(Optional) time slice in seconds")
        form.addRow("Time (s):", self.pass_time)
        # vcut
        self.pass_vcut = QtWidgets.QDoubleSpinBox(w); self.pass_vcut.setRange(10.0, 10000.0); self.pass_vcut.setValue(2000.0); self.pass_vcut.setDecimals(1)
        form.addRow("VelPlotCutoff (m/s):", self.pass_vcut)
        # Wave type filter (for RTBF format .max files)
        self.pass_wave_type = QtWidgets.QComboBox(w)
        self.pass_wave_type.addItems(["All Waves", "Rayleigh (Combined)", "Rayleigh Vertical", "Rayleigh Radial", "Love (Transverse)"])
        self.pass_wave_type.setToolTip("For RTBF format .max files: filter by wave polarization type.\n" +
                                        "Rayleigh (Combined) shows all Rayleigh waves (vertical + radial).\n" +
                                        "Love (Transverse) filters for Love waves.\n" +
                                        "Standard FK format files ignore this setting.")
        form.addRow("Wave Type:", self.pass_wave_type)
        return w

    # ---- helpers ----
    def _pick_file(self, line: QtWidgets.QLineEdit, desc: str, pattern: str):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, f"Select {desc}", "", f"{desc} ({pattern});;All Files (*.*)")
        if path:
            line.setText(path)

    def _pick_file_any(self, line: QtWidgets.QLineEdit, patterns: tuple[tuple[str,str], ...]):
        filters = ";;".join([f"{d} ({p})" for d,p in patterns] + ["All Files (*.*)"])
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File", "", filters)
        if path:
            line.setText(path)

    def _pick_passive_data(self):
        """Pick passive data file and show column mapper for .max files (if checkbox is checked)."""
        filters = "Geopsy FK .max (*.max);;Passive CSV (*.csv);;All Files (*.*)"
        path, selected_filter = QtWidgets.QFileDialog.getOpenFileName(self, "Select Passive Data", "", filters)
        if not path:
            return
        
        self.max_path.setText(path)
        
        # If .max file selected AND checkbox is checked, show column mapper
        import os
        if os.path.splitext(path)[1].lower() == ".max":
            if self.use_column_mapping.isChecked():
                self._show_max_column_mapper(path)
            else:
                # Checkbox unchecked: clear mapping to use legacy auto-detection
                self.column_mapping = None
    
    def _show_max_column_mapper(self, max_path: str):
        """Parse .max file and show column mapping dialog."""
        try:
            import re
            import numpy as np
            
            # Read file and filter valid data lines (same approach as parse_max_file)
            data_lines = []
            with open(max_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    # Skip empty lines and comments
                    if not stripped or stripped.startswith('#'):
                        continue
                    # Data lines start with a number (timestamp or time value)
                    if stripped[0].isdigit():
                        data_lines.append(stripped)
            
            if not data_lines:
                raise ValueError("File contains no data rows")
            
            # Parse the data lines
            rows = []
            for line in data_lines:
                parts = re.split(r'[\s\|]+', line)
                if len(parts) >= 2:  # At least 2 columns
                    rows.append(parts)
            
            if not rows:
                raise ValueError("No valid data rows found")
            
            # Determine number of columns from first row
            n_cols = len(rows[0])
            
            # Convert each column to numpy array for the mapper
            columns_data = []
            for col_idx in range(n_cols):
                col_values = [row[col_idx] if col_idx < len(row) else '' for row in rows]
                # Try to convert to numeric
                try:
                    numeric_vals = [float(v) for v in col_values]
                    columns_data.append(np.array(numeric_vals))
                except (ValueError, TypeError):
                    # Keep as string array (e.g., polarization column)
                    columns_data.append(np.array(col_values))
            
            # Show mapper dialog
            dlg = ColumnMapperDialog(columns_data, self)
            if dlg.exec() == 1:  # Accepted
                self.column_mapping = dlg.get_mapping()
            else:
                # User cancelled - clear file selection
                self.max_path.clear()
                self.column_mapping = None
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to read .max file:\n{e}")
            self.max_path.clear()
            self.column_mapping = None

    # ---- accept ----
    def _on_accept(self):
        idx = self.tabs.currentIndex()
        if idx == 0:  # Active Data (nested tabs)
            active_idx = self.active_tabs.currentIndex()
            if active_idx == 0:  # MATLAB sub-tab
                path = self.mat_path.text().strip()
                if not path:
                    QtWidgets.QMessageBox.warning(self, "MATLAB", "Please select a .mat file."); return
                self.result = {
                    'mode': 'matlab',
                    'path': path,
                    'dx': float(self.mat_dx.value()),
                }
            elif active_idx == 1:  # CSV sub-tab
                path = self.csv_path.text().strip()
                if not path:
                    QtWidgets.QMessageBox.warning(self, "CSV", "Please select a .csv file."); return
                spectrum_path = self.csv_spectrum_path.text().strip() or None  # None if empty
                self.result = {
                    'mode': 'csv',
                    'path': path,
                    'dx': float(self.csv_dx.value()),
                    'vmin': float(self.csv_vmin.value()),
                    'vmax': float(self.csv_vmax.value()),
                    'spectrum_path': spectrum_path,  # NEW: Optional spectrum file
                }
            else:
                QtWidgets.QMessageBox.warning(self, "Active Data", "Unknown sub-tab."); return
        elif idx == 1:  # Passive Data
            max_path = self.max_path.text().strip()
            kl_path  = self.kl_path.text().strip()
            if not max_path or not kl_path:
                QtWidgets.QMessageBox.warning(self, "Passive Data", "Please select both data and k-limits files."); return
            
            # Parse time
            tval = self.pass_time.text().strip()
            time = None
            if tval:
                try:
                    time = float(tval)
                except Exception:
                    QtWidgets.QMessageBox.warning(self, "Passive Data", "Time must be a number (seconds). Use blank for auto."); return
            
            # Get wave_type from combo box
            # Maps GUI text to parser wave_type ('Rayleigh', 'Love', or 'all')
            wave_type_text = self.pass_wave_type.currentText()
            if "Rayleigh" in wave_type_text:
                wave_type = 'Rayleigh'
            elif "Love" in wave_type_text:
                wave_type = 'Love'
            else:
                wave_type = 'all'
            
            self.result = {
                'mode': 'passive',
                'max_path': max_path,
                'kl_path':  kl_path,
                'dx': float(self.pass_dx.value()),
                'vcut': float(self.pass_vcut.value()),
                'time': time,
                'column_mapping': self.column_mapping,  # Include column mapping for .max files
                'wave_type': wave_type,  # Wave type filter for RTBF format
            }
        elif idx == 2:  # State
            path = self.state_path.text().strip()
            if not path:
                QtWidgets.QMessageBox.warning(self, "State", "Please select a .pkl file."); return
            spectrum_path = self.state_spectrum_path.text().strip() if hasattr(self, 'state_spectrum_path') else ''
            self.result = {
                'mode': 'state',
                'path': path,
                'dx': float(self.state_dx.value()),
                'spectrum_path': spectrum_path if spectrum_path else None,
            }
        elif idx == 3:  # Circular Array
            is_valid, error_msg = self.tab_circular.validate()
            if not is_valid:
                QtWidgets.QMessageBox.warning(self, "Circular Array", error_msg)
                return
            self.result = self.tab_circular.get_config()
        else:
            QtWidgets.QMessageBox.warning(self, "Open Data", "Unknown tab."); return
        
        self.accept()
