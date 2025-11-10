from __future__ import annotations

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore    = qt_compat.QtCore


class ColumnMapperDialog(QtWidgets.QDialog):
    """Column mapping dialog for Geopsy .max files.
    
    Allows user to map columns to data types (Frequency, Slowness/Velocity, etc.).
    """
    
    def __init__(self, columns_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map .max File Columns")
        self.resize(800, 500)
        self.columns_data = columns_data  # List of column arrays
        self.mapping = {}  # {col_idx: type_str}
        
        v = QtWidgets.QVBoxLayout(self)
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
            
            arr = np.array(col_data, dtype=float)
            arr = arr[np.isfinite(arr)]  # Remove NaN/inf
            
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


class OpenDataDialog(QtWidgets.QDialog):
    """Clean Qt dialog to open data from various sources.

    Modes:
      - Active Data: MATLAB (.mat) or CSV (.csv) via nested tabs
      - Passive Data: FK (.max + k-limits) or Passive CSV (freq, slow)
      - State: Session restore (.pkl)

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

        self.tabs.addTab(self.tab_active,  "Active Data")
        self.tabs.addTab(self.tab_passive, "Passive Data")
        self.tabs.addTab(self.tab_state,   "State")

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
            import numpy as np
            # Read .max file (simple space-separated format)
            data = np.loadtxt(max_path)
            
            if data.ndim == 1:
                # Single row - reshape
                data = data.reshape(1, -1)
            
            # Split into columns
            columns_data = [data[:, i] for i in range(data.shape[1])]
            
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
                self.result = {
                    'mode': 'csv',
                    'path': path,
                    'dx': float(self.csv_dx.value()),
                    'vmin': float(self.csv_vmin.value()),
                    'vmax': float(self.csv_vmax.value()),
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
            
            self.result = {
                'mode': 'passive',
                'max_path': max_path,
                'kl_path':  kl_path,
                'dx': float(self.pass_dx.value()),
                'vcut': float(self.pass_vcut.value()),
                'time': time,
                'column_mapping': self.column_mapping,  # Include column mapping for .max files
            }
        elif idx == 2:  # State
            path = self.state_path.text().strip()
            if not path:
                QtWidgets.QMessageBox.warning(self, "State", "Please select a .pkl file."); return
            self.result = {
                'mode': 'state',
                'path': path,
                'dx': float(self.state_dx.value()),
            }
        else:
            QtWidgets.QMessageBox.warning(self, "Open Data", "Unknown tab."); return
        
        self.accept()
