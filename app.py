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
            from dc_cut.gui.open_data import OpenDataDialog
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Open", f"Dialog import failed:\n{e}")
            return
        dlg = OpenDataDialog(self)
        if dlg.exec() != 1 or not dlg.result:
            return
        spec = dlg.result
        mode = spec.get('mode')
        dx   = float(spec.get('dx', 2.0))

        # Dispatch
        ok = False
        if mode == 'passive':
            ok = self._load_passive(spec)
        elif mode == 'matlab':
            ok = self._load_matlab(spec)
        elif mode == 'csv':
            ok = self._load_csv(spec)
        elif mode == 'state':
            ok = self._load_state(spec)
        else:
            QtWidgets.QMessageBox.warning(self, "Open", f"Unsupported mode: {mode}")
        # Close the launcher if we successfully opened a controller in the shell
        if ok:
            self.close()

    # --- loaders ---
    def _load_passive(self, spec: dict) -> bool:
        try:
            from dc_cut.io.max import load_klimits, parse_max_file
            from dc_cut.core.controller import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
            import pandas as pd
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"Imports failed:\n{e}")
            return False
        data_path = spec['max_path']; kl_path = spec['kl_path']
        dx = float(spec['dx']); vcut = float(spec['vcut']); time = spec.get('time')
        column_mapping = spec.get('column_mapping')  # Get column mapping if provided
        
        # k-limits
        try:
            ext = os.path.splitext(kl_path)[1].lower()
            if ext == ".mat": kmin, kmax = load_klimits(mat_path=kl_path)
            elif ext == ".csv": kmin, kmax = load_klimits(csv_path=kl_path)
            else:
                try: kmin, kmax = load_klimits(mat_path=kl_path)
                except Exception: kmin, kmax = load_klimits(csv_path=kl_path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"k-limits error:\n{e}")
            return False
        # parse data: .max or passive .csv (freq, slow)
        try:
            extd = os.path.splitext(data_path)[1].lower()
            if extd == ".max":
                # Use column mapping if provided
                if column_mapping:
                    # Load raw data using numpy
                    data = np.loadtxt(data_path)
                    if data.ndim == 1:
                        data = data.reshape(1, -1)
                    
                    # Extract columns based on mapping
                    if "Frequency (Hz)" not in column_mapping:
                        raise ValueError("Frequency column not mapped")
                    freq_col = column_mapping["Frequency (Hz)"]
                    freq = data[:, freq_col]
                    
                    # Handle velocity or slowness
                    if "Velocity (m/s)" in column_mapping:
                        vel_col = column_mapping["Velocity (m/s)"]
                        vel = data[:, vel_col]
                        slow = 1000.0 / vel  # Convert m/s to s/km: slow(s/km) = 1000 / vel(m/s)
                    elif "Slowness (s/km)" in column_mapping:
                        slow_col = column_mapping["Slowness (s/km)"]
                        slow = data[:, slow_col]  # Already in s/km (Geopsy standard)
                    else:
                        raise ValueError("Neither Velocity nor Slowness column mapped")
                else:
                    # Fallback to legacy parser
                    df = parse_max_file(data_path)
                    if df.empty:
                        QtWidgets.QMessageBox.critical(self, "Passive", ".max parsed but empty.")
                        return False
                    freq = df['freq'].to_numpy(float)
                    slow = df['slow'].to_numpy(float)
            elif extd == ".csv":
                df = pd.read_csv(data_path)
                cols_lower = [c.lower() for c in df.columns]
                if 'freq' in cols_lower and 'slow' in cols_lower:
                    freq = df[df.columns[cols_lower.index('freq')]].to_numpy(float)
                    slow = df[df.columns[cols_lower.index('slow')]].to_numpy(float)
                else:
                    # Ask user to map columns
                    mapping = ColumnMapDialog(list(df.columns), self).get_mapping()
                    if not mapping:
                        return False
                    c_freq, c_slow = mapping
                    try:
                        freq = df[c_freq].to_numpy(float); slow = df[c_slow].to_numpy(float)
                    except Exception as e:
                        raise ValueError(f"Failed to read selected columns: {e}")
            else:
                raise ValueError("Unsupported passive data file; use .max or .csv")
            # Convert slowness (s/km) to m/s: v = 1000 / slow
            # Wavelength: λ = v / f
            m0 = np.isfinite(freq) & np.isfinite(slow) & (freq > 0) & (slow > 0)
            freq = freq[m0]; slow = slow[m0]
            vel  = 1000.0 / slow
            wave = np.where(freq > 0, vel / freq, np.nan)
            m1 = np.isfinite(vel) & np.isfinite(wave) & (vel >= 0) & (vel <= vcut) & (wave > 0)
            freq = freq[m1]; vel = vel[m1]; wave = wave[m1]
            if vel.size == 0:
                QtWidgets.QMessageBox.critical(self, "Passive", "No picks after filtering.")
                return False
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"Failed to read data:\n{e}")
            return False
        # build controller
        velocity_arrays   = [vel]
        frequency_arrays  = [freq]
        wavelength_arrays = [wave]
        set_leg = ["Passive Array Data"]
        # Get array configuration from preferences
        try:
            P = load_prefs()
            n_phones = int(P.get('default_n_phones', 24))
        except Exception:
            n_phones = 24
        array_positions = np.arange(0, dx * n_phones, dx)
        source_offsets = []
        try:
            ctrl = InteractiveRemovalWithLayers(
                velocity_arrays, frequency_arrays, wavelength_arrays,
                array_positions=array_positions, source_offsets=source_offsets,
                set_leg=set_leg, receiver_dx=dx, legacy_controls=False,
            )
            # Set clamps to match chosen vcut
            ctrl.min_vel = 0.0; ctrl.max_vel = vcut
            # Apply k-guides and user prefs
            ctrl.kmin = float(kmin); ctrl.kmax = float(kmax); ctrl.show_k_guides = True
            try:
                P = load_prefs()
                ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
                ctrl.freq_custom_ticks = P.get('freq_custom_ticks', getattr(ctrl, 'freq_custom_ticks', []))
                # apply k-guides default if present
                if 'show_k_guides_default' in P:
                    ctrl.show_k_guides = bool(P['show_k_guides_default'])
            except Exception:
                pass
            ctrl._draw_k_guides(); ctrl._update_legend()
            app_qt = show_shell(ctrl)
            try:
                app_qt._masw_shell_window.adopt_controller(ctrl)
                ctrl.suppress_mpl_controls_for_shell()
                try: ctrl._enforce_shell_layout()
                except Exception: pass
            except Exception: pass
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Passive", f"Failed to launch controller:\n{e}")
            return False

    def _load_matlab(self, spec: dict) -> bool:
        try:
            from dc_cut.io.matlab import load_matlab_data
            from dc_cut.core.controller import InteractiveRemovalWithLayers
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
            from dc_cut.io.csv import load_combined_csv
            from dc_cut.core.controller import InteractiveRemovalWithLayers
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
            from dc_cut.io.state import load_session
            from dc_cut.core.controller import InteractiveRemovalWithLayers
            from dc_cut.gui.main_window import show_shell
            from dc_cut.services.prefs import load_prefs
            import numpy as np
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "State", f"Imports failed:\n{e}")
            return False
        path = spec['path']; dx = float(spec['dx'])
        try:
            S = load_session(path)
            v = S["velocity_arrays"]; f = S["frequency_arrays"]; w = S["wavelength_arrays"]
            set_leg = S.get("set_leg", None)
            # Get array configuration from preferences
            try:
                P = load_prefs()
                n_phones = int(P.get('default_n_phones', 24))
            except Exception:
                n_phones = 24
            array_positions = np.arange(0, dx * n_phones, dx)
            source_offsets = []
            ctrl = InteractiveRemovalWithLayers(v, f, w, array_positions=array_positions, source_offsets=source_offsets, set_leg=set_leg, receiver_dx=dx, legacy_controls=False)
            # Restore passive FK guides if present
            if 'kmin' in S and 'kmax' in S:
                try:
                    ctrl.kmin = float(S['kmin']); ctrl.kmax = float(S['kmax']); ctrl.show_k_guides = bool(S.get('show_k_guides', False))
                    ctrl._draw_k_guides(); ctrl._update_legend()
                except Exception: pass
            # Apply prefs for ticks if state lacks them
            try:
                P = load_prefs()
                if 'freq_tick_style' in S:
                    ctrl.freq_tick_style = S['freq_tick_style']
                else:
                    ctrl.freq_tick_style = P.get('freq_tick_style', getattr(ctrl, 'freq_tick_style', 'decades'))
                if 'freq_custom_ticks' in S:
                    ctrl.freq_custom_ticks = S['freq_custom_ticks']
                else:
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
            QtWidgets.QMessageBox.critical(self, "State", f"Load failed:\n{e}")
            return False


def open_data_directly():
    """Show file dialog directly and load data without launcher window."""
    try:
        from dc_cut.gui.open_data import OpenDataDialog
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
    elif mode == 'matlab':
        ok = launcher._load_matlab(spec)
    elif mode == 'csv':
        ok = launcher._load_csv(spec)
    elif mode == 'state':
        ok = launcher._load_state(spec)
    else:
        QtWidgets.QMessageBox.warning(None, "Error", f"Unsupported mode: {mode}")

    return ok


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

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
