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


class UniversalColumnMapperDialog(QtWidgets.QDialog):
    """Universal column mapping dialog for any file type (MAT/CSV/TXT).
    
    Features:
    - Auto-detects delimiter (comma, tab, space, pipe)
    - Horizontal + vertical scrolling for wide files
    - Data start line selector
    - Offset grouping for multi-offset data
    """
    
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Universal Column Mapper")
        self.resize(900, 600)
        self.file_path = file_path
        self.columns_data = []
        self.delimiter = 'auto'
        self.data_start_line = 0
        self.total_lines = 0
        
        self._build_ui()
        self._load_file()
    
    def _build_ui(self):
        import numpy as np
        v = QtWidgets.QVBoxLayout(self)
        
        # File info and controls
        info_layout = QtWidgets.QHBoxLayout()
        import os
        self.lbl_file = QtWidgets.QLabel(f"<b>File:</b> {os.path.basename(self.file_path)}")
        info_layout.addWidget(self.lbl_file)
        info_layout.addStretch()
        
        # Delimiter selector
        info_layout.addWidget(QtWidgets.QLabel("Delimiter:"))
        self.cmb_delimiter = QtWidgets.QComboBox()
        self.cmb_delimiter.addItems(["Auto", "Comma", "Tab", "Space", "Pipe"])
        self.cmb_delimiter.currentTextChanged.connect(self._on_delimiter_changed)
        info_layout.addWidget(self.cmb_delimiter)
        
        # Data start line
        info_layout.addWidget(QtWidgets.QLabel("Start line:"))
        self.spin_start = QtWidgets.QSpinBox()
        self.spin_start.setRange(0, 10000)
        self.spin_start.setValue(0)
        self.spin_start.valueChanged.connect(self._on_start_changed)
        info_layout.addWidget(self.spin_start)
        self.lbl_total = QtWidgets.QLabel("(of 0 lines)")
        info_layout.addWidget(self.lbl_total)
        v.addLayout(info_layout)
        
        v.addWidget(QtWidgets.QLabel("<b>Map each column to its data type:</b>"))
        
        # Status label
        self.status_label = QtWidgets.QLabel("")
        v.addWidget(self.status_label)
        
        # Scroll area for columns (both H and V)
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        try:
            self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except AttributeError:
            self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        
        self.container = QtWidgets.QWidget()
        self.col_layout = QtWidgets.QHBoxLayout(self.container)
        self.col_layout.setSpacing(4)
        self.scroll.setWidget(self.container)
        v.addWidget(self.scroll, 1)
        
        # Column type options
        self.type_options = [
            "Skipped",
            "Frequency (Hz)",
            "Slowness (s/km)",
            "Velocity (m/s)",
            "Wavelength (m)",
            "Power/Amplitude",
            "Azimuth",
            "Time (s)",
            "Label/ID"
        ]
        
        # Offset grouping
        group_layout = QtWidgets.QHBoxLayout()
        group_layout.addWidget(QtWidgets.QLabel("Offset grouping:"))
        self.cmb_grouping = QtWidgets.QComboBox()
        self.cmb_grouping.addItems(["None (single offset)", "Auto-detect", "2 cols/offset", "3 cols/offset"])
        group_layout.addWidget(self.cmb_grouping)
        group_layout.addStretch()
        v.addLayout(group_layout)
        
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
        
        self.combo_boxes = []
    
    def _load_file(self):
        """Load and parse file based on extension."""
        import os
        import re
        import numpy as np
        
        ext = os.path.splitext(self.file_path)[1].lower()
        
        try:
            if ext == '.mat':
                self._load_mat_file()
            else:
                self._load_text_file()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
    
    def _load_mat_file(self):
        """Load MATLAB .mat file and show available variables."""
        import numpy as np
        try:
            from scipy.io import loadmat
        except ImportError:
            QtWidgets.QMessageBox.critical(self, "Error", "scipy required for .mat files")
            return
        
        mat = loadmat(self.file_path, squeeze_me=True)
        # Filter out metadata keys
        var_names = [k for k in mat.keys() if not k.startswith('__')]
        
        # Show each variable as a "column"
        for var_name in var_names:
            arr = mat[var_name]
            if isinstance(arr, np.ndarray):
                if arr.ndim == 2:
                    # Multi-column variable - show each column
                    for col_idx in range(arr.shape[1]):
                        col_data = arr[:, col_idx]
                        self.columns_data.append(col_data)
                        self._add_column_widget(f"{var_name}[:,{col_idx}]", col_data)
                elif arr.ndim == 1:
                    self.columns_data.append(arr)
                    self._add_column_widget(var_name, arr)
        
        self.total_lines = len(self.columns_data[0]) if self.columns_data else 0
        self.lbl_total.setText(f"(of {self.total_lines} rows)")
        self._auto_detect()
        self._validate()
    
    def _load_text_file(self):
        """Load CSV/TXT file with delimiter detection."""
        import re
        import numpy as np
        
        # Pattern to strip ANSI escape codes
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[\d*m')
        
        # Read and clean lines
        raw_lines = []
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean = ansi_escape.sub('', line).strip()
                if clean and not clean.startswith('#'):
                    raw_lines.append(clean)
        
        if not raw_lines:
            QtWidgets.QMessageBox.warning(self, "Warning", "File contains no data")
            return
        
        # Detect delimiter
        delimiters = {
            'Comma': ',',
            'Tab': '\t',
            'Space': r'\s+',
            'Pipe': r'\|',
            'Auto': None
        }
        
        delimiter_choice = self.cmb_delimiter.currentText()
        if delimiter_choice == 'Auto':
            # Auto-detect by counting separators in first data line
            first_line = raw_lines[0]
            counts = {
                'Comma': first_line.count(','),
                'Tab': first_line.count('\t'),
                'Pipe': first_line.count('|'),
                'Space': len(re.split(r'\s+', first_line)) - 1
            }
            best = max(counts, key=counts.get)
            delimiter = delimiters[best]
        else:
            delimiter = delimiters[delimiter_choice]
        
        # Parse rows
        rows = []
        for line in raw_lines:
            if delimiter and delimiter not in [r'\s+', r'\|']:
                parts = [p.strip() for p in line.split(delimiter)]
            else:
                parts = re.split(delimiter or r'[\s\|,]+', line)
            parts = [p for p in parts if p]
            if parts:
                rows.append(parts)
        
        if not rows:
            return
        
        self.total_lines = len(rows)
        self.lbl_total.setText(f"(of {self.total_lines} lines)")
        self.spin_start.setMaximum(max(0, self.total_lines - 1))
        
        # Build column data
        n_cols = max(len(row) for row in rows)
        self._rebuild_columns(rows, n_cols)
    
    def _rebuild_columns(self, rows, n_cols):
        """Rebuild column widgets from parsed rows."""
        import numpy as np
        
        # Clear existing
        self.columns_data.clear()
        self.combo_boxes.clear()
        while self.col_layout.count():
            item = self.col_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Apply start line offset
        start = self.spin_start.value()
        rows = rows[start:] if start < len(rows) else []
        
        for col_idx in range(n_cols):
            col_values = [row[col_idx] if col_idx < len(row) else '' for row in rows]
            
            # Try to convert to numeric
            try:
                numeric = [float(v) for v in col_values]
                col_data = np.array(numeric)
            except (ValueError, TypeError):
                col_data = np.array(col_values)
            
            self.columns_data.append(col_data)
            self._add_column_widget(f"Col {col_idx + 1}", col_data)
        
        self._auto_detect()
        self._validate()
    
    def _add_column_widget(self, label: str, col_data):
        """Add a column widget to the layout."""
        import numpy as np
        
        w = QtWidgets.QWidget()
        w.setMinimumWidth(130)
        w.setMaximumWidth(200)
        vbox = QtWidgets.QVBoxLayout(w)
        vbox.setContentsMargins(2, 2, 2, 2)
        
        # Column header
        lbl = QtWidgets.QLabel(f"<b>{label}</b>")
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
        
        # Data preview with scroll
        preview = QtWidgets.QTextEdit(w)
        preview.setReadOnly(True)
        preview.setMaximumHeight(350)
        
        # Format preview text
        if col_data.dtype.kind in 'iuf':  # numeric
            preview_text = "\n".join([f"{v:.6g}" for v in col_data[:500]])
        else:
            preview_text = "\n".join([str(v) for v in col_data[:500]])
        if len(col_data) > 500:
            preview_text += f"\n... ({len(col_data)} total)"
        preview.setPlainText(preview_text)
        vbox.addWidget(preview, 1)
        
        self.col_layout.addWidget(w)
    
    def _on_delimiter_changed(self, text):
        """Reload file with new delimiter."""
        import os
        if os.path.splitext(self.file_path)[1].lower() != '.mat':
            self._load_text_file()
    
    def _on_start_changed(self, value):
        """Reload preview with new start line."""
        import os
        if os.path.splitext(self.file_path)[1].lower() != '.mat':
            self._load_text_file()
    
    def _auto_detect(self):
        """Auto-detect column types based on data patterns."""
        import numpy as np
        
        for i, col_data in enumerate(self.columns_data):
            if i >= len(self.combo_boxes):
                break
            
            # Skip non-numeric columns
            if col_data.dtype.kind not in 'iuf':
                continue
            
            try:
                arr = col_data[np.isfinite(col_data)]
                if arr.size == 0:
                    continue
                
                min_val = float(np.min(arr))
                max_val = float(np.max(arr))
                
                # Detect frequency: 0.5-200 Hz range
                if 0.01 <= min_val <= 100 and 0.1 <= max_val <= 300:
                    self.combo_boxes[i].setCurrentText("Frequency (Hz)")
                # Detect slowness: s/km values 0.1-15
                elif 0.1 <= min_val <= 10.0 and 0.15 <= max_val <= 20.0:
                    self.combo_boxes[i].setCurrentText("Slowness (s/km)")
                # Detect velocity: 50-10000 m/s
                elif 50 <= min_val and max_val <= 10000:
                    self.combo_boxes[i].setCurrentText("Velocity (m/s)")
            except Exception:
                pass
    
    def _validate(self):
        """Validate that required columns are mapped."""
        types = [cb.currentText() for cb in self.combo_boxes]
        has_freq = "Frequency (Hz)" in types
        has_vel = "Velocity (m/s)" in types or "Slowness (s/km)" in types
        
        if has_freq and has_vel:
            self.status_label.setText('<span style="color:green">✓ Required columns mapped</span>')
            self.btn_ok.setEnabled(True)
        else:
            missing = []
            if not has_freq:
                missing.append("Frequency")
            if not has_vel:
                missing.append("Velocity or Slowness")
            self.status_label.setText(f'<span style="color:red">Missing: {", ".join(missing)}</span>')
            self.btn_ok.setEnabled(False)
    
    def get_mapping(self) -> dict:
        """Return column mapping as dict {type_str: col_idx}."""
        mapping = {}
        for i, combo in enumerate(self.combo_boxes):
            type_str = combo.currentText()
            if type_str != "Skipped":
                mapping[type_str] = i
        return mapping
    
    def get_data_start_line(self) -> int:
        """Return user-specified data start line."""
        return self.spin_start.value()
    
    def get_offset_grouping(self) -> str:
        """Return offset grouping mode."""
        return self.cmb_grouping.currentText()


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
        
        # Pattern to strip ANSI escape codes
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m|\[\d*m')
        
        try:
            data_lines = []
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Strip ANSI escape codes first
                    clean_line = ansi_escape.sub('', line).strip()
                    if not clean_line or clean_line.startswith('#'):
                        continue
                    # Check if line starts with digit or minus sign (negative number)
                    if clean_line[0].isdigit() or (clean_line[0] == '-' and len(clean_line) > 1 and clean_line[1].isdigit()):
                        data_lines.append(clean_line)
            
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
        """Active Data tab with multi-file support."""
        w = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 6)
        
        # File table storage
        self.active_files = []  # List of {label, path, mapping, spectrum, ...}
        self.active_file_mappings = {}  # {row_idx: mapping_dict}
        
        # Info label
        info = QtWidgets.QLabel("<i>Add data files (MAT, CSV, TXT). Each file becomes a branch in the layer tree.</i>")
        info.setWordWrap(True)
        v.addWidget(info)
        
        # Files table
        files_group = QtWidgets.QGroupBox("Data Files")
        files_layout = QtWidgets.QVBoxLayout(files_group)
        
        self.active_table = QtWidgets.QTableWidget(0, 5)
        self.active_table.setHorizontalHeaderLabels(["Label", "File Path", "Map", "NPZ Spectrum", ""])
        self.active_table.horizontalHeader().setStretchLastSection(False)
        self.active_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive if hasattr(QtWidgets.QHeaderView, 'ResizeMode') else QtWidgets.QHeaderView.Interactive)
        self.active_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch if hasattr(QtWidgets.QHeaderView, 'ResizeMode') else QtWidgets.QHeaderView.Stretch)
        self.active_table.setColumnWidth(0, 100)
        self.active_table.setColumnWidth(2, 50)
        self.active_table.setColumnWidth(3, 180)
        self.active_table.setColumnWidth(4, 30)
        files_layout.addWidget(self.active_table)
        
        # Add/Remove buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("+ Add File")
        btn_add.clicked.connect(self._add_active_file_row)
        btn_remove = QtWidgets.QPushButton("- Remove Selected")
        btn_remove.clicked.connect(self._remove_active_file_row)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        files_layout.addLayout(btn_layout)
        
        v.addWidget(files_group)
        
        # Group mode
        group_layout = QtWidgets.QHBoxLayout()
        group_layout.addWidget(QtWidgets.QLabel("Group files as:"))
        self.active_group_mode = QtWidgets.QComboBox()
        self.active_group_mode.addItems(["Separate branches", "Same branch (merged)"])
        group_layout.addWidget(self.active_group_mode)
        group_layout.addStretch()
        v.addLayout(group_layout)
        
        # Settings
        settings_layout = QtWidgets.QHBoxLayout()
        settings_layout.addWidget(QtWidgets.QLabel("Δx (m):"))
        self.active_dx = QtWidgets.QDoubleSpinBox()
        self.active_dx.setRange(0.1, 100.0)
        self.active_dx.setValue(2.0)
        self.active_dx.setDecimals(2)
        settings_layout.addWidget(self.active_dx)
        
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QtWidgets.QLabel("Vel min:"))
        self.active_vmin = QtWidgets.QDoubleSpinBox()
        self.active_vmin.setRange(0.0, 1e6)
        self.active_vmin.setValue(0.0)
        settings_layout.addWidget(self.active_vmin)
        
        settings_layout.addWidget(QtWidgets.QLabel("max:"))
        self.active_vmax = QtWidgets.QDoubleSpinBox()
        self.active_vmax.setRange(10.0, 1e6)
        self.active_vmax.setValue(5000.0)
        settings_layout.addWidget(self.active_vmax)
        settings_layout.addStretch()
        v.addLayout(settings_layout)
        
        return w
    
    def _add_active_file_row(self):
        """Add a new row to the active files table."""
        row = self.active_table.rowCount()
        self.active_table.insertRow(row)
        
        # Label (editable)
        label_edit = QtWidgets.QLineEdit()
        label_edit.setPlaceholderText(f"File {row + 1}")
        label_edit.setText(f"File {row + 1}")
        self.active_table.setCellWidget(row, 0, label_edit)
        
        # File path
        path_edit = QtWidgets.QLineEdit()
        path_edit.setPlaceholderText("Select file...")
        self.active_table.setCellWidget(row, 1, path_edit)
        
        # Map button
        btn_map = QtWidgets.QPushButton("Map")
        btn_map.setMaximumWidth(50)
        btn_map.clicked.connect(lambda checked, r=row: self._map_active_file(r))
        self.active_table.setCellWidget(row, 2, btn_map)
        
        # NPZ spectrum path
        spectrum_layout = QtWidgets.QWidget()
        spectrum_h = QtWidgets.QHBoxLayout(spectrum_layout)
        spectrum_h.setContentsMargins(0, 0, 0, 0)
        spectrum_edit = QtWidgets.QLineEdit()
        spectrum_edit.setPlaceholderText("(Optional)")
        btn_spectrum = QtWidgets.QPushButton("...")
        btn_spectrum.setMaximumWidth(30)
        btn_spectrum.clicked.connect(lambda checked, e=spectrum_edit: self._browse_spectrum(e))
        spectrum_h.addWidget(spectrum_edit, 1)
        spectrum_h.addWidget(btn_spectrum)
        self.active_table.setCellWidget(row, 3, spectrum_layout)
        
        # Browse button for main file
        btn_browse = QtWidgets.QPushButton("...")
        btn_browse.setMaximumWidth(30)
        btn_browse.clicked.connect(lambda checked, e=path_edit: self._browse_active_file(e))
        self.active_table.setCellWidget(row, 4, btn_browse)
    
    def _remove_active_file_row(self):
        """Remove selected row from active files table."""
        row = self.active_table.currentRow()
        if row >= 0:
            self.active_table.removeRow(row)
            # Clean up mapping
            if row in self.active_file_mappings:
                del self.active_file_mappings[row]
    
    def _browse_active_file(self, path_edit):
        """Browse for data file (MAT/CSV/TXT)."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Data File", "",
            "All Supported (*.mat *.csv *.txt);;MATLAB (*.mat);;CSV (*.csv);;Text (*.txt);;All Files (*.*)"
        )
        if path:
            path_edit.setText(path)
    
    def _browse_spectrum(self, path_edit):
        """Browse for NPZ spectrum file."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Spectrum File", "",
            "NPZ Files (*.npz);;All Files (*.*)"
        )
        if path:
            path_edit.setText(path)
    
    def _map_active_file(self, row: int):
        """Open column mapper for a specific file."""
        if row >= self.active_table.rowCount():
            return
        
        path_widget = self.active_table.cellWidget(row, 1)
        path = path_widget.text().strip() if path_widget else ""
        
        if not path:
            QtWidgets.QMessageBox.warning(self, "Map Columns", "Select a file first.")
            return
        
        import os
        if not os.path.exists(path):
            QtWidgets.QMessageBox.warning(self, "Map Columns", f"File not found: {path}")
            return
        
        dlg = UniversalColumnMapperDialog(path, self)
        if dlg.exec() == 1:
            self.active_file_mappings[row] = {
                'column_mapping': dlg.get_mapping(),
                'data_start_line': dlg.get_data_start_line(),
                'offset_grouping': dlg.get_offset_grouping()
            }
    
    def _get_active_files_config(self) -> list:
        """Get configuration for all active data files."""
        files = []
        for row in range(self.active_table.rowCount()):
            label_widget = self.active_table.cellWidget(row, 0)
            path_widget = self.active_table.cellWidget(row, 1)
            spectrum_widget = self.active_table.cellWidget(row, 3)
            
            label = label_widget.text().strip() if label_widget else f"File {row + 1}"
            path = path_widget.text().strip() if path_widget else ""
            
            # Get spectrum path from nested layout
            spectrum_path = ""
            if spectrum_widget:
                spectrum_edit = spectrum_widget.findChild(QtWidgets.QLineEdit)
                if spectrum_edit:
                    spectrum_path = spectrum_edit.text().strip()
            
            if path:
                files.append({
                    'label': label,
                    'path': path,
                    'spectrum': spectrum_path,
                    'mapping': self.active_file_mappings.get(row, {})
                })
        
        return files

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
        if idx == 0:  # Active Data (multi-file)
            files = self._get_active_files_config()
            if not files:
                QtWidgets.QMessageBox.warning(self, "Active Data", "Please add at least one data file.")
                return
            
            self.result = {
                'mode': 'active',
                'files': files,
                'group_mode': self.active_group_mode.currentText(),
                'dx': float(self.active_dx.value()),
                'vmin': float(self.active_vmin.value()),
                'vmax': float(self.active_vmax.value()),
            }
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
