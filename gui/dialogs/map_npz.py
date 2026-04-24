"""NPZ mapper dialog — let the user map arbitrary ``.npz`` arrays to the
canonical spectrum roles DC-cut needs (``frequencies`` / ``velocities``
/ ``power`` / ``picked_velocities`` …).

This mirrors the UX of :class:`UniversalColumnMapperDialog` but for the
``.npz`` container: each top-level array in the file becomes a column
in a mini inspector, and the user assigns roles via combo boxes.

Public surface:

* :class:`NpzKeySpec` — dataclass describing a mapping.
* :func:`read_npz_with_spec` — apply a spec to load spectra.
* :class:`MapNpzDialog` — the Qt dialog itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
from matplotlib.backends import qt_compat

from dc_cut.core.io.offset_label import (
    from_suffix,
    normalize_offset,
    to_suffix,
)
from dc_cut.core.io.spectrum import SpectrumRecord, _coerce_power

QtWidgets = qt_compat.QtWidgets
QtCore = qt_compat.QtCore

try:
    _DIALOG_ACCEPTED = QtWidgets.QDialog.Accepted
except AttributeError:  # Qt6
    _DIALOG_ACCEPTED = QtWidgets.QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# Spec dataclass
# ---------------------------------------------------------------------------


@dataclass
class NpzKeySpec:
    """Canonical description of how to read a bespoke NPZ layout."""

    layout: str = "single"  # "single" | "combined"

    # Single-offset mapping
    frequencies_key: str = ""
    velocities_key: str = ""
    power_key: str = ""
    picked_velocities_key: str = ""
    wavenumbers_key: str = ""

    # Combined mapping (patterns use ``{suffix}`` as placeholder)
    offsets_key: str = ""  # optional; empty → derive from key scan
    frequencies_pattern: str = "frequencies_{suffix}"
    velocities_pattern: str = "velocities_{suffix}"
    power_pattern: str = "power_{suffix}"
    picked_velocities_pattern: str = "picked_velocities_{suffix}"
    wavenumbers_pattern: str = "wavenumbers_{suffix}"

    # Common behaviour
    transpose_power: bool = False

    # Metadata overrides (blank → fall back to NPZ contents / filename)
    method: str = ""
    version: str = "1.0"
    export_date: str = ""
    offset_override: str = ""  # only meaningful for single layout

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, blob: str) -> "NpzKeySpec":
        data = json.loads(blob)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ---------------------------------------------------------------------------
# Spec application
# ---------------------------------------------------------------------------


def read_npz_with_spec(npz_path: str, spec: NpzKeySpec) -> List[SpectrumRecord]:
    """Load ``npz_path`` according to ``spec`` and return spectrum records.

    Raises :class:`KeyError` if the spec references keys that do not
    exist in the file, and :class:`ValueError` if the chosen arrays
    have incompatible shapes.
    """
    path = Path(npz_path)
    if not path.exists():
        raise FileNotFoundError(f"Spectrum file not found: {path}")

    with np.load(str(path), allow_pickle=True) as data:
        if spec.layout == "combined":
            return _apply_combined(data, spec, path)
        return [_apply_single(data, spec, path)]


def _apply_single(data: Mapping[str, Any], spec: NpzKeySpec, path: Path) -> SpectrumRecord:
    keys = set(data.files)  # type: ignore[attr-defined]

    for role, key in (
        ("frequencies", spec.frequencies_key),
        ("velocities", spec.velocities_key),
        ("power", spec.power_key),
    ):
        if not key:
            raise KeyError(f"Mapping is missing '{role}' — open 'Map NPZ…' to assign it.")
        if key not in keys:
            raise KeyError(f"Mapped key '{key}' does not exist in {path.name}.")

    freqs = np.asarray(data[spec.frequencies_key])
    vels = np.asarray(data[spec.velocities_key])
    power = np.asarray(data[spec.power_key])
    if spec.transpose_power and power.ndim == 2:
        power = power.T
    power = _coerce_power(power, len(vels), len(freqs))

    picked: Optional[np.ndarray] = None
    if spec.picked_velocities_key and spec.picked_velocities_key in keys:
        try:
            picked = np.asarray(data[spec.picked_velocities_key])
        except Exception:
            picked = None

    wavenumbers: Optional[np.ndarray] = None
    if spec.wavenumbers_key and spec.wavenumbers_key in keys:
        try:
            wavenumbers = np.asarray(data[spec.wavenumbers_key])
        except Exception:
            wavenumbers = None

    method = spec.method or _scalar(data, "method", default="unknown") or "unknown"
    offset = normalize_offset(spec.offset_override) or normalize_offset(
        _scalar(data, "offset", default="")
    )
    export_date = spec.export_date or _scalar(data, "export_date", default="") or ""
    version = spec.version or _scalar(data, "version", default="1.0") or "1.0"

    return SpectrumRecord(
        frequencies=freqs,
        velocities=vels,
        power=power,
        picked_velocities=picked,
        method=str(method),
        offset=str(offset or ""),
        export_date=str(export_date),
        version=str(version),
        wavenumbers=wavenumbers,
        vibrosis_mode=bool(_scalar(data, "vibrosis_mode", default=False)),
        vspace=_scalar(data, "vspace", default=None),
        weight_mode=_scalar(data, "weight_mode", default=None),
        extras={},
    )


def _apply_combined(data: Mapping[str, Any], spec: NpzKeySpec, path: Path) -> List[SpectrumRecord]:
    keys = list(data.files)  # type: ignore[attr-defined]

    # 1. Discover the offset list.
    declared: List[str] = []
    if spec.offsets_key and spec.offsets_key in keys:
        try:
            declared = [str(x) for x in np.atleast_1d(data[spec.offsets_key])]
        except Exception:
            declared = []

    if not declared:
        prefix, suffix_suffix = _split_pattern(spec.frequencies_pattern)
        scanned: List[str] = []
        for k in keys:
            if k.startswith(prefix) and k.endswith(suffix_suffix):
                tag = k[len(prefix) : len(k) - len(suffix_suffix)] if suffix_suffix else k[len(prefix) :]
                if tag:
                    scanned.append(tag)
        declared = [from_suffix(s) or s for s in dict.fromkeys(scanned)]

    if not declared:
        raise ValueError(
            f"No offsets could be derived from {path.name}. Provide an "
            "'offsets' array or a 'frequencies_<suffix>' pattern."
        )

    records: List[SpectrumRecord] = []
    for raw in declared:
        suffix = to_suffix(raw)
        if not suffix:
            continue
        freq_key = spec.frequencies_pattern.format(suffix=suffix)
        vel_key = spec.velocities_pattern.format(suffix=suffix)
        power_key = spec.power_pattern.format(suffix=suffix)
        if freq_key not in keys or vel_key not in keys or power_key not in keys:
            continue

        freqs = np.asarray(data[freq_key])
        vels = np.asarray(data[vel_key])
        power = np.asarray(data[power_key])
        if spec.transpose_power and power.ndim == 2:
            power = power.T
        power = _coerce_power(power, len(vels), len(freqs))

        picked: Optional[np.ndarray] = None
        picked_key = spec.picked_velocities_pattern.format(suffix=suffix)
        if picked_key in keys:
            try:
                picked = np.asarray(data[picked_key])
            except Exception:
                picked = None

        wavenumbers: Optional[np.ndarray] = None
        wk_key = spec.wavenumbers_pattern.format(suffix=suffix)
        if wk_key in keys:
            try:
                wavenumbers = np.asarray(data[wk_key])
            except Exception:
                wavenumbers = None

        method = spec.method or _scalar(data, "method", default="unknown") or "unknown"
        export_date = spec.export_date or _scalar(data, "export_date", default="") or ""
        version = spec.version or _scalar(data, "version", default="1.0") or "1.0"

        records.append(
            SpectrumRecord(
                frequencies=freqs,
                velocities=vels,
                power=power,
                picked_velocities=picked,
                method=str(method),
                offset=normalize_offset(raw) or str(raw),
                export_date=str(export_date),
                version=str(version),
                wavenumbers=wavenumbers,
                vibrosis_mode=bool(_scalar(data, f"vibrosis_mode_{suffix}", default=False)),
                vspace=_scalar(data, f"vspace_{suffix}", default=None),
                weight_mode=_scalar(data, f"weight_mode_{suffix}", default=None),
                extras={},
            )
        )

    if not records:
        raise ValueError(
            f"Mapping produced no offsets for {path.name}. Check the "
            "patterns in 'Map NPZ…'."
        )
    return records


def _split_pattern(pattern: str) -> Tuple[str, str]:
    placeholder = "{suffix}"
    if placeholder not in pattern:
        return pattern, ""
    prefix, _, suffix_suffix = pattern.partition(placeholder)
    return prefix, suffix_suffix


def _scalar(data: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if key not in getattr(data, "files", data):
        return default
    try:
        value = data[key]
    except Exception:
        return default
    try:
        arr = np.asarray(value)
    except Exception:
        return value
    if arr.shape == ():
        scalar = arr.item()
        if isinstance(scalar, bytes):
            try:
                return scalar.decode("utf-8")
            except Exception:
                return scalar
        return scalar
    if arr.size == 1:
        return arr.reshape(-1)[0]
    return value


# ---------------------------------------------------------------------------
# QSettings persistence
# ---------------------------------------------------------------------------


_SETTINGS_ORG = "DC-Cut"
_SETTINGS_APP = "DC-Cut"
_SETTINGS_GROUP = "spectrum/npz_mappings"


def _fingerprint(npz_path: str) -> str:
    """Return a stable signature for ``npz_path``'s array layout.

    The signature is based on the sorted list of ``(key, shape, dtype)``
    triples so two files with the same structure can share a mapping.
    """
    try:
        with np.load(str(npz_path), allow_pickle=True) as data:
            triples = []
            for k in sorted(data.files):
                try:
                    arr = data[k]
                    shape = tuple(np.shape(arr))
                    dtype = str(np.asarray(arr).dtype)
                except Exception:
                    shape = ()
                    dtype = "unknown"
                triples.append((k, shape, dtype))
    except Exception:
        triples = [("__error__", (), "unknown")]

    blob = json.dumps(triples, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:16]


def load_saved_spec(npz_path: str) -> Optional[NpzKeySpec]:
    """Retrieve a previously persisted spec for ``npz_path``'s layout."""
    try:
        qs = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        blob = qs.value(f"{_SETTINGS_GROUP}/{_fingerprint(npz_path)}", "")
        if not blob:
            return None
        return NpzKeySpec.from_json(str(blob))
    except Exception:
        return None


def save_spec(npz_path: str, spec: NpzKeySpec) -> None:
    """Persist ``spec`` for every NPZ that shares the same array layout."""
    try:
        qs = QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        qs.setValue(f"{_SETTINGS_GROUP}/{_fingerprint(npz_path)}", spec.to_json())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------


_ROLES = [
    ("Skip", "__skip__"),
    ("Frequencies", "frequencies"),
    ("Velocities", "velocities"),
    ("Power", "power"),
    ("Picked velocities", "picked_velocities"),
    ("Wavenumbers", "wavenumbers"),
    ("Offsets list", "offsets"),
]
_ROLE_LABEL_BY_KEY = {k: label for label, k in _ROLES}


class MapNpzDialog(QtWidgets.QDialog):
    """Interactive mapper for a ``.npz`` spectrum file."""

    def __init__(self, npz_path: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Map NPZ arrays to spectrum roles")
        self.resize(880, 560)
        self.npz_path = str(npz_path)
        self._spec: Optional[NpzKeySpec] = None
        self._keys_meta: List[Tuple[str, Tuple[int, ...], str]] = []
        self._role_combos: Dict[str, QtWidgets.QComboBox] = {}

        self._build_ui()
        self._inspect_file()
        self._prefill_from_saved()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def result_spec(self) -> Optional[NpzKeySpec]:
        """Return the mapping the user confirmed (``None`` if cancelled)."""
        return self._spec

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        v = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel(
            f"<b>File:</b> {Path(self.npz_path).name}<br>"
            "Assign each NPZ array to a canonical role. DC-cut only needs "
            "<i>frequencies</i>, <i>velocities</i> and <i>power</i>; the other "
            "roles are optional."
        )
        header.setWordWrap(True)
        v.addWidget(header)

        # Layout selector
        layout_row = QtWidgets.QHBoxLayout()
        layout_row.addWidget(QtWidgets.QLabel("Layout:"))
        self.cmb_layout = QtWidgets.QComboBox(self)
        self.cmb_layout.addItem("Single offset", userData="single")
        self.cmb_layout.addItem("Combined (multi-offset)", userData="combined")
        self.cmb_layout.currentIndexChanged.connect(self._on_layout_changed)
        layout_row.addWidget(self.cmb_layout)

        self.chk_transpose = QtWidgets.QCheckBox("Transpose power (swap rows/cols)")
        layout_row.addWidget(self.chk_transpose)
        layout_row.addStretch(1)
        v.addLayout(layout_row)

        # Stacked: single vs combined mapping UI
        self.stack = QtWidgets.QStackedWidget(self)
        self.stack.addWidget(self._build_single_page())
        self.stack.addWidget(self._build_combined_page())
        v.addWidget(self.stack, 1)

        # Array inspector
        v.addWidget(QtWidgets.QLabel("<b>Arrays in this file:</b>"))
        self.table = QtWidgets.QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Key", "Shape", "Dtype"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setMaximumHeight(180)
        v.addWidget(self.table)

        # Metadata overrides
        meta_box = QtWidgets.QGroupBox("Metadata overrides (optional)")
        meta_form = QtWidgets.QFormLayout(meta_box)
        self.edt_method = QtWidgets.QLineEdit(self)
        self.edt_version = QtWidgets.QLineEdit(self)
        self.edt_version.setText("1.0")
        self.edt_offset = QtWidgets.QLineEdit(self)
        self.edt_offset.setPlaceholderText("e.g. +66m, -10m")
        meta_form.addRow("Method:", self.edt_method)
        meta_form.addRow("Version:", self.edt_version)
        meta_form.addRow("Offset (single layout):", self.edt_offset)
        v.addWidget(meta_box)

        # Status + buttons
        self.lbl_status = QtWidgets.QLabel("")
        self.lbl_status.setStyleSheet("color: #888;")
        v.addWidget(self.lbl_status)

        btns = QtWidgets.QDialogButtonBox(self)
        try:
            ok_flag = QtWidgets.QDialogButtonBox.Ok
            cancel_flag = QtWidgets.QDialogButtonBox.Cancel
        except AttributeError:
            ok_flag = QtWidgets.QDialogButtonBox.StandardButton.Ok
            cancel_flag = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        btns.setStandardButtons(ok_flag | cancel_flag)
        self._btn_ok = btns.button(ok_flag)
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _build_single_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(page)

        self.cmb_freq_single = QtWidgets.QComboBox(self)
        self.cmb_vel_single = QtWidgets.QComboBox(self)
        self.cmb_power_single = QtWidgets.QComboBox(self)
        self.cmb_picked_single = QtWidgets.QComboBox(self)
        self.cmb_wavenumbers_single = QtWidgets.QComboBox(self)

        form.addRow("Frequencies:", self.cmb_freq_single)
        form.addRow("Velocities:", self.cmb_vel_single)
        form.addRow("Power:", self.cmb_power_single)
        form.addRow("Picked velocities (optional):", self.cmb_picked_single)
        form.addRow("Wavenumbers (optional):", self.cmb_wavenumbers_single)
        return page

    def _build_combined_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        form = QtWidgets.QFormLayout(page)

        self.cmb_offsets_combined = QtWidgets.QComboBox(self)
        self.edt_freq_pattern = QtWidgets.QLineEdit("frequencies_{suffix}")
        self.edt_vel_pattern = QtWidgets.QLineEdit("velocities_{suffix}")
        self.edt_power_pattern = QtWidgets.QLineEdit("power_{suffix}")
        self.edt_picked_pattern = QtWidgets.QLineEdit("picked_velocities_{suffix}")
        self.edt_wavenumbers_pattern = QtWidgets.QLineEdit("wavenumbers_{suffix}")

        form.addRow("Offsets array (optional):", self.cmb_offsets_combined)
        form.addRow("Frequencies pattern:", self.edt_freq_pattern)
        form.addRow("Velocities pattern:", self.edt_vel_pattern)
        form.addRow("Power pattern:", self.edt_power_pattern)
        form.addRow("Picked velocities pattern:", self.edt_picked_pattern)
        form.addRow("Wavenumbers pattern:", self.edt_wavenumbers_pattern)

        hint = QtWidgets.QLabel(
            "Use <code>{suffix}</code> as the placeholder for the per-offset tag "
            "(<code>p66</code> / <code>m10</code> …). When the 'Offsets array' is "
            "left blank, DC-cut derives the list from matching key names."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        form.addRow(hint)
        return page

    # ------------------------------------------------------------------
    # File inspection
    # ------------------------------------------------------------------

    def _inspect_file(self) -> None:
        try:
            with np.load(self.npz_path, allow_pickle=True) as data:
                for key in sorted(data.files):
                    try:
                        arr = np.asarray(data[key])
                        shape = tuple(arr.shape)
                        dtype = str(arr.dtype)
                    except Exception:
                        shape = ()
                        dtype = "?"
                    self._keys_meta.append((key, shape, dtype))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Unable to open NPZ", str(exc))
            self.reject()
            return

        self._populate_inspector()
        self._populate_combos()
        self._auto_guess_single()
        self._auto_guess_combined()
        self._on_layout_changed()

    def _populate_inspector(self) -> None:
        self.table.setRowCount(len(self._keys_meta))
        for row, (key, shape, dtype) in enumerate(self._keys_meta):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(key))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(str(shape)))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(dtype))
        self.table.resizeColumnsToContents()

    def _populate_combos(self) -> None:
        single_combos = [
            (self.cmb_freq_single, False),
            (self.cmb_vel_single, False),
            (self.cmb_power_single, False),
            (self.cmb_picked_single, True),
            (self.cmb_wavenumbers_single, True),
        ]
        for cmb, allow_blank in single_combos:
            cmb.clear()
            if allow_blank:
                cmb.addItem("(none)", userData="")
            for key, shape, dtype in self._keys_meta:
                cmb.addItem(f"{key}  {shape}  [{dtype}]", userData=key)

        self.cmb_offsets_combined.clear()
        self.cmb_offsets_combined.addItem("(auto-detect from suffixed keys)", userData="")
        for key, shape, dtype in self._keys_meta:
            self.cmb_offsets_combined.addItem(
                f"{key}  {shape}  [{dtype}]", userData=key
            )

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    def _auto_guess_single(self) -> None:
        def _first(*names: str) -> str:
            for n in names:
                for key, _shape, _dtype in self._keys_meta:
                    if key == n:
                        return key
            return ""

        self._set_combo_value(self.cmb_freq_single, _first("frequencies", "freqs", "f", "frequency"))
        self._set_combo_value(self.cmb_vel_single, _first("velocities", "vels", "v", "velocity"))
        self._set_combo_value(self.cmb_power_single, _first("power", "amplitude", "dispersion"))
        self._set_combo_value(self.cmb_picked_single, _first("picked_velocities", "picked"))
        self._set_combo_value(self.cmb_wavenumbers_single, _first("wavenumbers", "k"))

    def _auto_guess_combined(self) -> None:
        offsets_key = ""
        for key, _shape, _dtype in self._keys_meta:
            if key == "offsets":
                offsets_key = key
                break
        self._set_combo_value(self.cmb_offsets_combined, offsets_key)

    def _set_combo_value(self, combo: QtWidgets.QComboBox, value: str) -> None:
        if not value:
            return
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------

    def _on_layout_changed(self) -> None:
        idx = 0 if self.cmb_layout.currentData() == "single" else 1
        self.stack.setCurrentIndex(idx)
        self.edt_offset.setEnabled(idx == 0)

    # ------------------------------------------------------------------
    # Accept
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        layout = str(self.cmb_layout.currentData() or "single")
        spec = NpzKeySpec(
            layout=layout,
            transpose_power=self.chk_transpose.isChecked(),
            method=self.edt_method.text().strip(),
            version=self.edt_version.text().strip() or "1.0",
            offset_override=self.edt_offset.text().strip(),
        )

        if layout == "single":
            spec.frequencies_key = str(self.cmb_freq_single.currentData() or "")
            spec.velocities_key = str(self.cmb_vel_single.currentData() or "")
            spec.power_key = str(self.cmb_power_single.currentData() or "")
            spec.picked_velocities_key = str(self.cmb_picked_single.currentData() or "")
            spec.wavenumbers_key = str(self.cmb_wavenumbers_single.currentData() or "")
            missing = [
                role
                for role, key in (
                    ("Frequencies", spec.frequencies_key),
                    ("Velocities", spec.velocities_key),
                    ("Power", spec.power_key),
                )
                if not key
            ]
            if missing:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Incomplete mapping",
                    "Please assign: " + ", ".join(missing) + ".",
                )
                return
        else:
            spec.offsets_key = str(self.cmb_offsets_combined.currentData() or "")
            spec.frequencies_pattern = self.edt_freq_pattern.text().strip() or "frequencies_{suffix}"
            spec.velocities_pattern = self.edt_vel_pattern.text().strip() or "velocities_{suffix}"
            spec.power_pattern = self.edt_power_pattern.text().strip() or "power_{suffix}"
            spec.picked_velocities_pattern = (
                self.edt_picked_pattern.text().strip() or "picked_velocities_{suffix}"
            )
            spec.wavenumbers_pattern = (
                self.edt_wavenumbers_pattern.text().strip() or "wavenumbers_{suffix}"
            )
            for role, pattern in (
                ("Frequencies", spec.frequencies_pattern),
                ("Velocities", spec.velocities_pattern),
                ("Power", spec.power_pattern),
            ):
                if "{suffix}" not in pattern:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Incomplete mapping",
                        f"The {role} pattern must include '{{suffix}}'.",
                    )
                    return

        # Validate the mapping immediately so the user gets feedback now
        # rather than on load.
        try:
            records = read_npz_with_spec(self.npz_path, spec)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Mapping error", str(exc))
            return

        self._spec = spec
        save_spec(self.npz_path, spec)
        self.lbl_status.setText(f"Loaded {len(records)} spectrum record(s).")
        self.accept()

    # ------------------------------------------------------------------
    # Prefill
    # ------------------------------------------------------------------

    def _prefill_from_saved(self) -> None:
        saved = load_saved_spec(self.npz_path)
        if saved is None:
            return
        idx = 0 if saved.layout == "single" else 1
        self.cmb_layout.setCurrentIndex(idx)
        self.chk_transpose.setChecked(bool(saved.transpose_power))
        self.edt_method.setText(saved.method)
        self.edt_version.setText(saved.version or "1.0")
        self.edt_offset.setText(saved.offset_override)

        if saved.layout == "single":
            self._set_combo_value(self.cmb_freq_single, saved.frequencies_key)
            self._set_combo_value(self.cmb_vel_single, saved.velocities_key)
            self._set_combo_value(self.cmb_power_single, saved.power_key)
            self._set_combo_value(self.cmb_picked_single, saved.picked_velocities_key)
            self._set_combo_value(self.cmb_wavenumbers_single, saved.wavenumbers_key)
        else:
            self._set_combo_value(self.cmb_offsets_combined, saved.offsets_key)
            self.edt_freq_pattern.setText(saved.frequencies_pattern)
            self.edt_vel_pattern.setText(saved.velocities_pattern)
            self.edt_power_pattern.setText(saved.power_pattern)
            self.edt_picked_pattern.setText(saved.picked_velocities_pattern)
            self.edt_wavenumbers_pattern.setText(saved.wavenumbers_pattern)


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def prompt_map_npz(
    npz_path: str,
    parent: Optional[QtWidgets.QWidget] = None,
) -> Optional[List[SpectrumRecord]]:
    """Open :class:`MapNpzDialog` and return the loaded records, or ``None``."""
    dlg = MapNpzDialog(npz_path, parent=parent)
    try:
        accepted = dlg.exec() == _DIALOG_ACCEPTED
    except Exception:
        accepted = dlg.exec_() == _DIALOG_ACCEPTED
    if not accepted:
        return None
    spec = dlg.result_spec()
    if spec is None:
        return None
    try:
        return read_npz_with_spec(npz_path, spec)
    except Exception as exc:
        QtWidgets.QMessageBox.critical(parent, "Map NPZ", str(exc))
        return None


__all__ = [
    "NpzKeySpec",
    "MapNpzDialog",
    "read_npz_with_spec",
    "save_spec",
    "load_saved_spec",
    "prompt_map_npz",
]
