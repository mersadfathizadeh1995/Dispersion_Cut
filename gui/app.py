from __future__ import annotations

import sys
import os

from matplotlib.backends import qt_compat
QtWidgets = qt_compat.QtWidgets
QtCore    = qt_compat.QtCore
QtGui     = qt_compat.QtGui


class ColumnMapDialog(QtWidgets.QDialog):
    def __init__(self, columns: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Map CSV Columns")
        self.resize(360, 140)
        v = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.cmb_freq = QtWidgets.QComboBox(self); self.cmb_freq.addItems(columns)
        self.cmb_slow = QtWidgets.QComboBox(self); self.cmb_slow.addItems(columns)
        form.addRow("Frequency column:", self.cmb_freq)
        form.addRow("Slowness column:", self.cmb_slow)
        v.addLayout(form)
        btns = QtWidgets.QDialogButtonBox(self)
        try:
            ok = QtWidgets.QDialogButtonBox.Ok; cancel = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            ok = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        btns.setStandardButtons(ok | cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def get_mapping(self) -> tuple[str, str] | None:
        if self.exec() == 1:
            return self.cmb_freq.currentText(), self.cmb_slow.currentText()
        return None


class LauncherWindow(QtWidgets.QMainWindow):
    def __init__(self, auto_open=False):
        super().__init__()
        self.setWindowTitle("DC Cut – Launcher (Qt)")
        self.resize(740, 280)
        lab = QtWidgets.QLabel("Welcome to DC Cut\n\nFile → Open Data… to load MATLAB/CSV/State/Passive data files.")
        try:
            align = QtCore.Qt.AlignCenter
        except AttributeError:
            align = QtCore.Qt.AlignmentFlag.AlignCenter
        lab.setAlignment(align)
        self.setCentralWidget(lab)
        self._build_menu()
        # Optionally auto-open on startup
        if auto_open:
            QtCore.QTimer.singleShot(0, self._open_data)

    def _build_menu(self):
        bar = self.menuBar()
        m_file = bar.addMenu("&File")

        act_open = QtGui.QAction("Open Data…", self)
        act_open.triggered.connect(self._open_data)
        m_file.addAction(act_open)

        m_file.addSeparator()
        act_exit = QtGui.QAction("Exit", self)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

    def _open_data(self):
        try:
            from dc_cut.gui.dialogs.open_data import OpenDataDialog
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Open", f"Dialog import failed:\n{e}")
            return
        dlg = OpenDataDialog(self)
        if dlg.exec() != 1 or not dlg.result:
            return
        spec = dlg.result
        mode = spec.get('mode')
        dx   = float(spec.get('dx', 2.0))

        # Dispatch based on mode using dictionary for robustness
        dispatchers = {
            'passive': self._load_passive,
            'active': self._load_active,
            'matlab': self._load_matlab,
            'csv': self._load_csv,
            'state': self._load_state,
            'circular_array_new': self._load_circular_array,
            'circular_array_continue': self._load_circular_array,
        }
        
        # Normalize mode string (strip whitespace, ensure lowercase comparison)
        mode_key = str(mode).strip() if mode else ''
        
        loader = dispatchers.get(mode_key)
        if loader:
            ok = loader(spec)
        else:
            QtWidgets.QMessageBox.warning(self, "Open", f"Unsupported mode: {repr(mode)}")
        # Close the launcher if we successfully opened a controller in the shell
        if ok:
            self.close()

    # --- loaders ---
    def _load_passive(self, spec: dict) -> bool:
        """Load passive data with multi-file support."""
        try:
            from dc_cut.core.io.max_parser import load_klimits, load_klimits_multi, parse_max_file
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
            import pandas as pd
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"Imports failed:\n{e}")
            return False
        
        dx = float(spec['dx'])
        vcut = float(spec['vcut'])
        files = spec.get('files', [])
        shared_klimit_path = spec.get('shared_klimit_path')
        shared_klimit_mapping = spec.get('shared_klimit_mapping')
        
        # Collect all k-limits
        all_klimits = []  # List of (label, kmin, kmax)
        
        # Load shared k-limits (if any)
        if shared_klimit_path:
            try:
                col_map = shared_klimit_mapping.get('column_mapping') if shared_klimit_mapping else None
                shared_klimits = load_klimits_multi(shared_klimit_path, column_mapping=col_map)
                all_klimits.extend(shared_klimits)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Passive", f"Shared k-limits error:\n{e}")
                return False
        
        # Process each file
        all_velocity = []
        all_frequency = []
        all_wavelength = []
        all_labels = []
        
        for file_info in files:
            data_path = file_info['path']
            label = file_info.get('label', os.path.basename(data_path))
            klimit_path = file_info.get('klimit_path')
            klimit_mapping = file_info.get('klimit_mapping')
            column_mapping = file_info.get('column_mapping')
            wave_type = file_info.get('wave_type', 'all')
            
            # Load per-file k-limits (if any)
            if klimit_path:
                try:
                    col_map = klimit_mapping.get('column_mapping') if klimit_mapping else None
                    file_klimits = load_klimits_multi(klimit_path, column_mapping=col_map, default_label=label)
                    all_klimits.extend(file_klimits)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(self, "K-Limits", f"Failed to load k-limits for {label}:\n{e}")
            
            # Parse data file
            try:
                extd = os.path.splitext(data_path)[1].lower()
                if extd == ".max":
                    if column_mapping:
                        raw = pd.read_csv(data_path, comment='#', header=None, sep=r"[\s\|]+", engine='python')
                        if raw.empty:
                            raise ValueError("File parsed but contains no data rows")
                        
                        if "Frequency (Hz)" not in column_mapping:
                            raise ValueError("Frequency column not mapped")
                        freq_col = column_mapping["Frequency (Hz)"]
                        freq = pd.to_numeric(raw.iloc[:, freq_col], errors='coerce').to_numpy()
                        
                        if "Velocity (m/s)" in column_mapping:
                            vel_col = column_mapping["Velocity (m/s)"]
                            vel = pd.to_numeric(raw.iloc[:, vel_col], errors='coerce').to_numpy()
                            slow = 1000.0 / vel
                        elif "Slowness (s/km)" in column_mapping:
                            slow_col = column_mapping["Slowness (s/km)"]
                            slow = pd.to_numeric(raw.iloc[:, slow_col], errors='coerce').to_numpy()
                        else:
                            raise ValueError("Neither Velocity nor Slowness column mapped")
                    else:
                        df = parse_max_file(data_path, wave_type=wave_type)
                        if df.empty:
                            QtWidgets.QMessageBox.warning(self, "Passive", f"{label}: .max parsed but empty.")
                            continue
                        freq = df['freq'].to_numpy(float)
                        slow = df['slow'].to_numpy(float)
                elif extd == ".csv":
                    df = pd.read_csv(data_path)
                    cols_lower = [c.lower() for c in df.columns]
                    if 'freq' in cols_lower and 'slow' in cols_lower:
                        freq = df[df.columns[cols_lower.index('freq')]].to_numpy(float)
                        slow = df[df.columns[cols_lower.index('slow')]].to_numpy(float)
                    else:
                        QtWidgets.QMessageBox.warning(self, "Passive", f"{label}: CSV missing freq/slow columns.")
                        continue
                else:
                    QtWidgets.QMessageBox.warning(self, "Passive", f"{label}: Unsupported file type.")
                    continue
                
                # Convert and filter
                m0 = np.isfinite(freq) & np.isfinite(slow) & (freq > 0) & (slow > 0)
                freq = freq[m0]
                slow = slow[m0]
                vel = 1000.0 / slow
                wave = np.where(freq > 0, vel / freq, np.nan)
                m1 = np.isfinite(vel) & np.isfinite(wave) & (vel >= 0) & (vel <= vcut) & (wave > 0)
                freq = freq[m1]
                vel = vel[m1]
                wave = wave[m1]
                
                if vel.size == 0:
                    QtWidgets.QMessageBox.warning(self, "Passive", f"{label}: No picks after filtering.")
                    continue
                
                all_velocity.append(vel)
                all_frequency.append(freq)
                all_wavelength.append(wave)
                all_labels.append(label)
                
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Passive", f"Failed to read {label}:\n{e}")
                continue
        
        if not all_velocity:
            QtWidgets.QMessageBox.critical(self, "Passive", "No valid data loaded from any file.")
            return False
        
        # Get array configuration from preferences
        try:
            P = load_prefs()
            n_phones = int(P.get('default_n_phones', 24))
        except Exception:
            n_phones = 24
        array_positions = np.arange(0, dx * n_phones, dx)
        
        try:
            ctrl = InteractiveRemovalWithLayers(
                all_velocity, all_frequency, all_wavelength,
                array_positions=array_positions, source_offsets=[],
                set_leg=all_labels, receiver_dx=dx, legacy_controls=False,
            )
            ctrl.min_vel = 0.0
            ctrl.max_vel = vcut
            
            # Set up k-limits
            if all_klimits:
                # Use first k-limit as primary (for backward compatibility)
                ctrl.kmin = float(all_klimits[0][1])
                ctrl.kmax = float(all_klimits[0][2])
                
                # Store all k-limits for multi k-guides display
                ctrl._multi_klimits = all_klimits
                ctrl._klimits_visibility = {k[0]: True for k in all_klimits}
                ctrl.show_k_guides = True
            
            try:
                P = load_prefs()
                ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', getattr(ctrl, 'freq_custom_ticks', []))
                if 'show_k_guides_default' in P:
                    ctrl.show_k_guides = bool(P['show_k_guides_default'])
            except Exception:
                pass
            
            ctrl._draw_k_guides()
            ctrl._update_legend()
            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try:
                    ctrl._enforce_shell_layout()
                except Exception:
                    pass
            except Exception:
                pass
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"Failed to launch controller:\n{e}")
            return False

    def _load_active(self, spec: dict) -> bool:
        """Load active data from multiple files with column mapping."""
        try:
            from dc_cut.core.io.universal import parse_any_file, parse_combined_csv
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
            import os
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Active", f"Imports failed:\n{e}")
            return False
        
        files = spec.get('files', [])
        dx = float(spec.get('dx', 2.0))
        vmin = float(spec.get('vmin', 0.0))
        vmax = float(spec.get('vmax', 5000.0))
        group_mode = spec.get('group_mode', 'Separate branches')
        
        all_velocity = []
        all_frequency = []
        all_wavelength = []
        all_labels = []
        file_boundaries = []  # Track which layers belong to which file
        spectrum_files = {}  # {label: spectrum_path}
        
        try:
            for file_info in files:
                path = file_info['path']
                label = file_info.get('label', os.path.basename(path))
                mapping_info = file_info.get('mapping', {})
                spectrum_path = file_info.get('spectrum', '')
                
                # Get column mapping
                column_mapping = mapping_info.get('column_mapping', {})
                data_start_line = mapping_info.get('data_start_line', 0)
                offset_grouping = mapping_info.get('offset_grouping', 'None (single offset)')
                
                # Determine cols_per_offset
                cols_per_offset = 0
                if '2 cols' in offset_grouping:
                    cols_per_offset = 2
                elif '3 cols' in offset_grouping:
                    cols_per_offset = 3
                elif 'Auto' in offset_grouping:
                    cols_per_offset = 3  # Default for auto
                
                ext = os.path.splitext(path)[1].lower()
                
                if column_mapping:
                    # Use universal parser with mapping
                    v, f, w, labels = parse_any_file(
                        path, column_mapping,
                        data_start_line=data_start_line,
                        cols_per_offset=cols_per_offset
                    )
                elif ext == '.mat':
                    # Try auto-detect for standard MASW MAT files
                    try:
                        v, f, w, labels = parse_any_file(path)
                    except ValueError as e:
                        QtWidgets.QMessageBox.warning(
                            self, "Active", 
                            f"Could not auto-detect MAT format for {os.path.basename(path)}.\n"
                            f"Please use Map button to specify columns.\n\nError: {e}"
                        )
                        continue
                elif ext == '.csv':
                    # Use combined CSV parser (auto-detect)
                    v, f, w, labels = parse_combined_csv(path)
                else:
                    QtWidgets.QMessageBox.warning(
                        self, "Active", 
                        f"No mapping for {os.path.basename(path)}. Please use Map button."
                    )
                    continue
                
                # Apply velocity clamp
                for i in range(len(v)):
                    mask = (v[i] >= vmin) & (v[i] <= vmax)
                    v[i] = v[i][mask]
                    f[i] = f[i][mask]
                    w[i] = w[i][mask]
                
                # Prefix labels with file label
                start_idx = len(all_velocity)
                for i, layer_label in enumerate(labels):
                    full_label = f"{label}/{layer_label}" if group_mode == 'Separate branches' else layer_label
                    all_labels.append(full_label)
                    if spectrum_path:
                        spectrum_files[full_label] = spectrum_path
                
                all_velocity.extend(v)
                all_frequency.extend(f)
                all_wavelength.extend(w)
                file_boundaries.append((label, start_idx, len(all_velocity)))
            
            if not all_velocity:
                QtWidgets.QMessageBox.critical(self, "Active", "No data loaded from files.")
                return False
            
            # Get array configuration
            try:
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
            except Exception:
                n_phones = 24
            
            array_positions = np.arange(0, dx * n_phones, dx)
            
            ctrl = InteractiveRemovalWithLayers(
                all_velocity, all_frequency, all_wavelength,
                array_positions=array_positions,
                source_offsets=[],
                set_leg=all_labels,
                receiver_dx=dx,
                legacy_controls=False
            )
            
            ctrl.min_vel = vmin
            ctrl.max_vel = vmax
            
            # Store file boundaries for layer tree
            ctrl._file_boundaries = file_boundaries
            ctrl._spectrum_files = spectrum_files
            
            try:
                P = load_prefs()
                ctrl.freq_tick_style = P.get('freq_tick_style', 'decades')
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', [])
            except Exception:
                pass
            
            # Load spectrum files
            for label, spectrum_path in spectrum_files.items():
                if spectrum_path and hasattr(ctrl, 'load_combined_spectrum_for_layers'):
                    try:
                        ctrl.load_combined_spectrum_for_layers(spectrum_path)
                    except Exception:
                        pass
            
            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try:
                    ctrl._enforce_shell_layout()
                except Exception:
                    pass
            except Exception:
                pass
            
            return True
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Active", f"Failed to load data:\n{e}")
            return False

    def _load_matlab(self, spec: dict) -> bool:
        try:
            from dc_cut.core.io.matlab import load_matlab_data
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "MATLAB", f"Imports failed:\n{e}")
            return False
        path = spec['path']; dx = float(spec['dx'])
        try:
            data = load_matlab_data(path)
            v = data.get('VelocityRawOffsets', []); f = data.get('FrequencyRawOffsets', []); w = data.get('WavelengthRawOffsets', [])
            set_leg = data.get('setLeg', None)
            # Get array configuration from preferences
            try:
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
            except Exception:
                n_phones = 24
            array_positions = np.arange(0, dx * n_phones, dx)
            source_offsets = []
            ctrl = InteractiveRemovalWithLayers(v, f, w, array_positions=array_positions, source_offsets=source_offsets, set_leg=set_leg, receiver_dx=dx, legacy_controls=False)
            try:
                P = load_prefs()
                ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', getattr(ctrl, 'freq_custom_ticks', []))
            except Exception:
                pass
            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try: ctrl._enforce_shell_layout()
                except Exception: pass
            except Exception: pass
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "MATLAB", f"Load failed:\n{e}")
            return False

    def _load_csv(self, spec: dict) -> bool:
        try:
            from dc_cut.core.io.csv_io import load_combined_csv
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "CSV", f"Imports failed:\n{e}")
            return False
        path = spec['path']; dx = float(spec['dx'])
        vmin = float(spec.get('vmin', 0.0)); vmax = float(spec.get('vmax', 5000.0))
        try:
            v, f, w, set_leg = load_combined_csv(path)
            # Apply velocity clamp prior to plotting if requested
            v2, f2, w2 = [], [], []
            for vi, fi, wi in zip(v, f, w):
                m = (vi >= vmin) & (vi <= vmax)
                v2.append(vi[m]); f2.append(fi[m]); w2.append(wi[m])
            v, f, w = v2, f2, w2
            # Get array configuration from preferences
            try:
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
            except Exception:
                n_phones = 24
            array_positions = np.arange(0, dx * n_phones, dx)
            source_offsets = []
            ctrl = InteractiveRemovalWithLayers(v, f, w, array_positions=array_positions, source_offsets=source_offsets, set_leg=set_leg, receiver_dx=dx, legacy_controls=False)
            # Set clamps on controller too, so axes reflect
            ctrl.min_vel = vmin; ctrl.max_vel = vmax
            try:
                P = load_prefs()
                ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', getattr(ctrl, 'freq_custom_ticks', []))
            except Exception:
                pass

            # Load spectrum background if provided
            spectrum_path = spec.get('spectrum_path')
            if spectrum_path:
                try:
                    # Try loading as combined spectrum first (for combined CSV files)
                    # This will match spectra to layers by offset labels
                    if hasattr(ctrl, 'load_combined_spectrum_for_layers'):
                        try:
                            results = ctrl.load_combined_spectrum_for_layers(spectrum_path)
                            if results:
                                # Combined spectrum loaded successfully
                                matched = sum(1 for v in results.values() if v)
                                try:
                                    from dc_cut.services import log
                                    log.info(f"Loaded combined spectrum: {matched} layers matched")
                                except Exception:
                                    pass
                            else:
                                # No matches - try as single spectrum for layer 0
                                raise ValueError("Not a combined spectrum or no matches")
                        except ValueError:
                            # Fall back to single-layer spectrum loading
                            if hasattr(ctrl, 'load_spectrum_for_layer'):
                                success = ctrl.load_spectrum_for_layer(0, spectrum_path)
                                if not success:
                                    try:
                                        from dc_cut.services import log
                                        log.warning(f"Failed to load spectrum from {spectrum_path}")
                                    except Exception:
                                        pass
                    elif hasattr(ctrl, 'load_spectrum_for_layer'):
                        # Fallback: no combined method available
                        success = ctrl.load_spectrum_for_layer(0, spectrum_path)
                        if not success:
                            try:
                                from dc_cut.services import log
                                log.warning(f"Failed to load spectrum from {spectrum_path}")
                            except Exception:
                                pass
                except Exception as e:
                    # Log error but don't fail the load
                    try:
                        from dc_cut.services import log
                        log.error(f"Error loading spectrum: {e}")
                    except Exception:
                        pass

            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try: ctrl._enforce_shell_layout()
                except Exception: pass
            except Exception: pass
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "CSV", f"Load failed:\n{e}")
            return False

    def _load_state(self, spec: dict) -> bool:
        try:
            from dc_cut.core.io.state import load_session
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "State", f"Imports failed:\n{e}")
            return False

        dx = float(spec.get('dx', 2.0))

        # Backward compat: wrap old single-file spec into multi-file list
        if 'files' in spec:
            files = spec['files']
        else:
            files = [{
                'label': 'State',
                'path': spec['path'],
                'spectrum': spec.get('spectrum_path'),
            }]

        all_velocity, all_frequency, all_wavelength = [], [], []
        all_labels = []
        all_groups = []
        file_boundaries = []
        spectrum_files = {}
        first_state = None

        for file_info in files:
            label = file_info['label']
            path = file_info['path']
            spectrum_path = file_info.get('spectrum')

            try:
                S = load_session(path)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "State",
                    f"Failed to load '{label}':\n{e}"
                )
                return False

            if first_state is None:
                first_state = S

            v = S["velocity_arrays"]
            f = S["frequency_arrays"]
            w = S["wavelength_arrays"]
            set_leg = S.get("set_leg", [f"Layer {i}" for i in range(len(v))])

            start_idx = len(all_velocity)
            for i in range(len(v)):
                all_velocity.append(v[i])
                all_frequency.append(f[i])
                all_wavelength.append(w[i])
                orig = set_leg[i] if i < len(set_leg) else f"Layer {i}"
                all_labels.append(orig)
                all_groups.append(label)
            end_idx = len(all_velocity)

            file_boundaries.append((label, start_idx, end_idx))

            if spectrum_path:
                spectrum_files[label] = spectrum_path

        if not all_velocity:
            QtWidgets.QMessageBox.warning(self, "State", "No layers found in selected state files.")
            return False

        try:
            P = load_prefs()
            n_phones = int(P.get('default_n_phones', 24))
        except Exception:
            n_phones = 24
            P = {}

        array_positions = np.arange(0, dx * n_phones, dx)

        try:
            ctrl = InteractiveRemovalWithLayers(
                all_velocity, all_frequency, all_wavelength,
                array_positions=array_positions, source_offsets=[],
                set_leg=all_labels, receiver_dx=dx, legacy_controls=False,
            )
            ctrl._file_boundaries = file_boundaries
            ctrl._layer_groups = all_groups
            ctrl._spectrum_files = spectrum_files
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "State", f"Controller init failed:\n{e}")
            return False

        # Restore k-guides from first state that has them
        for file_info in files:
            try:
                S = load_session(file_info['path'])
                if 'kmin' in S and 'kmax' in S:
                    ctrl.kmin = float(S['kmin'])
                    ctrl.kmax = float(S['kmax'])
                    ctrl.show_k_guides = bool(S.get('show_k_guides', False))
                    ctrl._draw_k_guides()
                    ctrl._update_legend()
                    break
            except Exception:
                pass

        # Apply tick prefs from first state
        try:
            if first_state and 'freq_tick_style' in first_state:
                ctrl.freq_tick_style = first_state['freq_tick_style']
            else:
                ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
            if first_state and 'freq_custom_ticks' in first_state:
                ctrl.freq_custom_ticks = first_state['freq_custom_ticks']
            else:
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', getattr(ctrl, 'freq_custom_ticks', []))
        except Exception:
            pass

        app_qt = show_shell(ctrl)
        try:
            app_qt._masw_shell_window.adopt_controller(ctrl)
            ctrl.suppress_mpl_controls_for_shell()
            try:
                ctrl._enforce_shell_layout()
            except Exception:
                pass
        except Exception:
            pass

        # Load spectra per-file
        for file_label, spectrum_path in spectrum_files.items():
            try:
                if hasattr(ctrl, 'load_combined_spectrum_for_layers'):
                    results = ctrl.load_combined_spectrum_for_layers(spectrum_path)
                    if results:
                        matched = sum(1 for val in results.values() if val)
                        try:
                            from dc_cut.services import log
                            log.info(f"Loaded spectrum for {matched} layers from '{file_label}'")
                        except Exception:
                            pass
            except Exception as e:
                try:
                    from dc_cut.services import log
                    log.warning(f"Failed to load spectrum for '{file_label}': {e}")
                except Exception:
                    pass

        return True

    def _load_circular_array(self, spec: dict) -> bool:
        """Load circular array data and launch workflow."""
        try:
            from pathlib import Path
            from dc_cut.packages.circular_array.config import WorkflowConfig, ArrayConfig, Stage
            from dc_cut.packages.circular_array.io import load_multi_array_klimits
            from dc_cut.packages.circular_array.orchestrator import CircularArrayOrchestrator
            from dc_cut.core.io.max_parser import parse_max_file
            from dc_cut.core.io.state import load_session
            from dc_cut.gui.controller.composed import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            import numpy as np
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Circular Array", f"Imports failed:\n{e}")
            return False

        mode = spec.get('mode')

        try:
            if mode == 'circular_array_continue':
                session_path = Path(spec['session_path'])
                S = load_session(str(session_path))

                v = S["velocity_arrays"]
                f = S["frequency_arrays"]
                w = S["wavelength_arrays"]
                set_leg = S.get("set_leg", [f"Array {i+1}" for i in range(len(v))])

                if 'workflow_config' not in S:
                    # Legacy session file - reconstruct minimal config from available data
                    # Filter out average labels to get actual array labels
                    array_labels = [lbl for lbl in set_leg if 'Average' not in lbl]
                    
                    # Ask user if they want to load klimits from file
                    reply = QtWidgets.QMessageBox.question(
                        self, "Circular Array - Legacy Session",
                        "This session file doesn't have array configuration.\n\n"
                        "Would you like to load k-limits from a file (.mat or .csv)?\n\n"
                        "Click 'Yes' to select a klimits file, or 'No' to use saved values.",
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.Yes
                    )
                    
                    klimits = None
                    if reply == QtWidgets.QMessageBox.Yes:
                        klimits_file, _ = QtWidgets.QFileDialog.getOpenFileName(
                            self, "Select K-Limits File",
                            str(session_path.parent),
                            "K-Limits Files (*.mat *.csv);;MAT Files (*.mat);;CSV Files (*.csv);;All Files (*)"
                        )
                        if klimits_file:
                            try:
                                klimits = load_multi_array_klimits(Path(klimits_file))
                            except Exception as e:
                                QtWidgets.QMessageBox.warning(
                                    self, "Circular Array",
                                    f"Failed to load klimits file:\n{e}\n\nUsing saved values instead."
                                )
                    
                    # Use saved kmin/kmax as fallback
                    kmin_default = float(S.get('kmin', 0.001))
                    kmax_default = float(S.get('kmax', 0.1))
                    
                    # Mapping from diameter to MATLAB row index (50m=row0, 200m=row1, 500m=row2)
                    klimits_idx_map = {50: 0, 200: 1, 500: 2}
                    
                    arrays_config = []
                    for i, label in enumerate(array_labels):
                        # Try to extract diameter from label like "Passive 500m" or "500m"
                        diameter = 50  # default
                        for d in [500, 200, 50]:
                            if str(d) in label:
                                diameter = d
                                break
                        
                        # Get k-limits from loaded file or use defaults
                        if klimits is not None:
                            matlab_idx = klimits_idx_map.get(diameter, i)
                            kmin, kmax = klimits.get(diameter, klimits.get(matlab_idx, (kmin_default, kmax_default)))
                        else:
                            kmin, kmax = kmin_default, kmax_default
                        
                        arrays_config.append(ArrayConfig(
                            diameter=diameter,
                            max_file_path=Path(f"legacy_array_{i}.max"),
                            kmin=kmin,
                            kmax=kmax,
                        ))
                    
                    config = WorkflowConfig(
                        site_name=session_path.stem,
                        output_dir=session_path.parent,
                        arrays=arrays_config,
                        wave_type='Rayleigh_Vertical',
                        velocity_cutoff=6000.0,
                        current_stage=Stage.INITIAL,
                    )
                    
                    # Show summary of loaded config
                    config_summary = "\n".join([
                        f"  {arr.diameter}m: kmin={arr.kmin:.6f}, kmax={arr.kmax:.6f}"
                        for arr in arrays_config
                    ])
                    QtWidgets.QMessageBox.information(
                        self, "Circular Array",
                        f"Loaded legacy session file.\n\nArray configurations:\n{config_summary}"
                    )
                else:
                    config_data = S['workflow_config']
                    config = WorkflowConfig.from_dict(config_data)

            else:
                klimits_path = Path(spec['klimits_path'])
                klimits = load_multi_array_klimits(klimits_path)

                arrays_config = []
                velocity_arrays = []
                frequency_arrays = []
                wavelength_arrays = []
                set_leg = []
                vcut = float(spec.get('velocity_cutoff', 6000.0))
                
                # Get column mapping options
                use_max_mapping = spec.get('use_max_mapping', False)
                array_mappings = spec.get('array_mappings', {})
                
                # Get wave_type from spec (for RTBF format filtering)
                workflow_wave_type = spec.get('wave_type', 'Rayleigh_Combined')
                if 'Rayleigh' in workflow_wave_type:
                    parser_wave_type = 'Rayleigh'
                elif 'Love' in workflow_wave_type:
                    parser_wave_type = 'Love'
                else:
                    parser_wave_type = 'all'

                # Process all arrays from spec (dynamic diameters)
                arrays_dict = spec.get('arrays', {})
                for diameter, path_str in sorted(arrays_dict.items(), key=lambda x: -x[0]):
                    if not path_str:
                        continue

                    max_path = Path(path_str)
                    # Try to get klimits by diameter, then by index
                    kmin, kmax = klimits.get(diameter, klimits.get(0, (0.001, 0.1)))

                    arrays_config.append(ArrayConfig(
                        diameter=diameter,
                        max_file_path=max_path,
                        kmin=kmin,
                        kmax=kmax,
                    ))

                    # Check if we have manual column mapping for this array
                    arr_mapping = array_mappings.get(diameter, {})
                    data_start_line = arr_mapping.get('data_start_line', 0)
                    column_mapping = arr_mapping.get('column_mapping', None) if use_max_mapping else None
                    
                    if column_mapping:
                        # Use manual column mapping
                        import pandas as pd
                        raw = pd.read_csv(str(max_path), comment='#', header=None, sep=r"[\s\|]+", engine='python')
                        if data_start_line > 0:
                            raw = raw.iloc[data_start_line:]
                        if raw.empty:
                            QtWidgets.QMessageBox.warning(
                                self, "Circular Array",
                                f"Warning: {max_path.name} parsed but empty, skipping."
                            )
                            continue
                        
                        # Extract columns based on mapping
                        import pandas as pd
                        if "Frequency (Hz)" in column_mapping:
                            freq = pd.to_numeric(raw.iloc[:, column_mapping["Frequency (Hz)"]], errors='coerce').to_numpy()
                        else:
                            QtWidgets.QMessageBox.warning(self, "Circular Array", f"Frequency column not mapped for {max_path.name}")
                            continue
                        
                        if "Velocity (m/s)" in column_mapping:
                            vel = pd.to_numeric(raw.iloc[:, column_mapping["Velocity (m/s)"]], errors='coerce').to_numpy()
                            slow = 1000.0 / vel
                        elif "Slowness (s/km)" in column_mapping:
                            slow = pd.to_numeric(raw.iloc[:, column_mapping["Slowness (s/km)"]], errors='coerce').to_numpy()
                        else:
                            QtWidgets.QMessageBox.warning(self, "Circular Array", f"Velocity/Slowness column not mapped for {max_path.name}")
                            continue
                    else:
                        # Use auto-detecting parser (handles FK, RTBF, LDS formats)
                        df = parse_max_file(str(max_path), wave_type=parser_wave_type, data_start_line=data_start_line)
                        if df.empty:
                            QtWidgets.QMessageBox.warning(
                                self, "Circular Array",
                                f"Warning: {max_path.name} parsed but empty, skipping."
                            )
                            continue

                        freq = df['freq'].to_numpy(float)
                        slow = df['slow'].to_numpy(float)

                    m0 = np.isfinite(freq) & np.isfinite(slow) & (freq > 0) & (slow > 0)
                    freq = freq[m0]
                    slow = slow[m0]
                    vel = 1000.0 / slow
                    wave = np.where(freq > 0, vel / freq, np.nan)

                    m1 = np.isfinite(vel) & np.isfinite(wave) & (vel >= 0) & (vel <= vcut)
                    freq = freq[m1]
                    vel = vel[m1]
                    wave = wave[m1]

                    if vel.size == 0:
                        QtWidgets.QMessageBox.warning(
                            self, "Circular Array",
                            f"Warning: {max_path.name} has no points after filtering."
                        )
                        continue

                    velocity_arrays.append(vel)
                    frequency_arrays.append(freq)
                    wavelength_arrays.append(wave)
                    set_leg.append(f"Passive {diameter}m")

                if not velocity_arrays:
                    QtWidgets.QMessageBox.critical(
                        self, "Circular Array", "No valid data loaded from any array."
                    )
                    return False

                config = WorkflowConfig(
                    site_name=spec['site_name'],
                    output_dir=Path(spec['output_dir']),
                    arrays=arrays_config,
                    wave_type=spec.get('wave_type', 'Rayleigh_Vertical'),
                    velocity_cutoff=vcut,
                    current_stage=Stage.INITIAL,
                )

                v = velocity_arrays
                f = frequency_arrays
                w = wavelength_arrays

            ctrl = InteractiveRemovalWithLayers(
                v, f, w,
                set_leg=set_leg,
                legacy_controls=False,
            )

            if config.arrays:
                first_arr = config.arrays[0]
                ctrl.kmin = first_arr.kmin
                ctrl.kmax = first_arr.kmax
                ctrl.show_k_guides = True
                ctrl._draw_k_guides()
                ctrl._update_legend()

            orchestrator = CircularArrayOrchestrator(config, ctrl)
            ctrl._circular_array_config = config
            ctrl._circular_array_orchestrator = orchestrator

            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try:
                    ctrl._enforce_shell_layout()
                except Exception:
                    pass
            except Exception:
                pass

            return True

        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self, "Circular Array", f"Load failed:\n{e}")
            return False


def open_data_directly():
    """Show file dialog directly and load data without launcher window."""
    try:
        from dc_cut.gui.dialogs.open_data import OpenDataDialog
    except Exception as e:
        QtWidgets.QMessageBox.critical(None, "Error", f"Failed to import dialog:\n{e}")
        return False

    # Show the file selection dialog
    dlg = OpenDataDialog(None)
    if dlg.exec() != 1 or not dlg.result:
        return False  # User cancelled

    spec = dlg.result
    mode = spec.get('mode')

    # Create a hidden launcher instance to use its loader methods
    launcher = LauncherWindow(auto_open=False)

    # Dispatch to appropriate loader
    ok = False
    if mode == 'passive':
        ok = launcher._load_passive(spec)
    elif mode == 'active':
        ok = launcher._load_active(spec)
    elif mode == 'matlab':
        ok = launcher._load_matlab(spec)
    elif mode == 'csv':
        ok = launcher._load_csv(spec)
    elif mode == 'state':
        ok = launcher._load_state(spec)
    elif mode in ('circular_array_new', 'circular_array_continue'):
        ok = launcher._load_circular_array(spec)
    else:
        QtWidgets.QMessageBox.warning(None, "Error", f"Unsupported mode: {mode}")

    return ok


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    # Force Fusion as the base style: Qt draws spin-box step buttons
    # and combo-box drop-downs with well-proportioned native-looking
    # arrow glyphs at reasonable click sizes, consistently across
    # Windows / macOS / Linux.  Our theme stylesheet then layers
    # light cosmetic tweaks on top.
    try:
        fusion = QtWidgets.QStyleFactory.create("Fusion")
        if fusion is not None:
            app.setStyle(fusion)
    except Exception:
        pass

    # Apply theme from preferences early
    try:
        from dc_cut.services.prefs import load_prefs
        from dc_cut.services.theme import apply_theme, apply_matplotlib_theme
        prefs = load_prefs()
        theme_name = prefs.get("theme", "light")
        apply_theme(app, theme_name)
        apply_matplotlib_theme(theme_name)
    except Exception:
        pass  # Silently fall back to default theme

    # Simple CLI: allow opening data without the launcher
    try:
        import argparse
        p = argparse.ArgumentParser(add_help=False)
        p.add_argument('--mode', choices=['matlab','csv','state','passive'])
        p.add_argument('--path')
        p.add_argument('--dx', type=float)
        # passive
        p.add_argument('--max')
        p.add_argument('--kl')
        p.add_argument('--vcut', type=float)
        p.add_argument('--time', type=float)
        args, _ = p.parse_known_args()
        if args.mode:
            win = LauncherWindow()
            # Build spec as if returned by OpenDataDialog
            if args.mode == 'matlab' and args.path and args.dx:
                spec = {'mode':'matlab','path':args.path,'dx':args.dx}
                ok = win._load_matlab(spec)
            elif args.mode == 'csv' and args.path and args.dx:
                spec = {'mode':'csv','path':args.path,'dx':args.dx}
                ok = win._load_csv(spec)
            elif args.mode == 'state' and args.path and args.dx:
                spec = {'mode':'state','path':args.path,'dx':args.dx}
                ok = win._load_state(spec)
            elif args.mode == 'passive' and args.max and args.kl and args.dx and args.vcut is not None:
                spec = {'mode':'passive','max_path':args.max,'kl_path':args.kl,'dx':args.dx,'vcut':args.vcut,'time':args.time}
                ok = win._load_passive(spec)
            else:
                ok = False
            if ok:
                app.exec()
                return
    except Exception:
        pass

    # GUI mode: show file dialog directly (no launcher window)
    ok = open_data_directly()
    if ok:
        app.exec()
    # If user cancelled or loading failed, exit gracefully
