from __future__ import annotations

import os
import numpy as np
from typing import Dict, List

try:
    from scipy.io import loadmat
except Exception as _e:
    loadmat = None  # type: ignore


def load_matlab_data(filepath: str) -> Dict:
    """Load MATLAB .mat file with FrequencyRaw, VelocityRaw, WavelengthRaw and optional setLeg.

    Returns a dict with keys:
      - FrequencyRawOffsets: List[np.ndarray]
      - VelocityRawOffsets: List[np.ndarray]
      - WavelengthRawOffsets: List[np.ndarray]
      - setLeg: List[str] (optional)
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Could not find file: {filepath}")
    if loadmat is None:
        raise ImportError("scipy.io.loadmat not available; install SciPy to read .mat files")

    mat_data = loadmat(filepath, squeeze_me=True, struct_as_record=False)
    data_dict: Dict[str, object] = {}

    # setLeg
    if 'setLeg' in mat_data:
        raw = mat_data['setLeg']
        if isinstance(raw, (list, np.ndarray)):
            data_dict['setLeg'] = [str(x) for x in list(raw)]
        else:
            data_dict['setLeg'] = [str(raw)]

    def split_columns(arr, name: str) -> List[np.ndarray]:
        a = np.asarray(arr)
        if a.ndim == 2:
            return [a[:, i] for i in range(a.shape[1])]
        return [a]

    if 'FrequencyRaw' in mat_data:
        data_dict['FrequencyRawOffsets'] = split_columns(mat_data['FrequencyRaw'], 'FrequencyRaw')
    if 'VelocityRaw' in mat_data:
        data_dict['VelocityRawOffsets'] = split_columns(mat_data['VelocityRaw'], 'VelocityRaw')
    if 'WavelengthRaw' in mat_data:
        data_dict['WavelengthRawOffsets'] = split_columns(mat_data['WavelengthRaw'], 'WavelengthRaw')

    # Sanity: compute wavelength if missing
    if 'WavelengthRawOffsets' not in data_dict and 'VelocityRawOffsets' in data_dict and 'FrequencyRawOffsets' in data_dict:
        wlist = []
        for v, f in zip(data_dict['VelocityRawOffsets'], data_dict['FrequencyRawOffsets']):  # type: ignore[index]
            v = np.asarray(v, float); f = np.asarray(f, float)
            with np.errstate(divide='ignore', invalid='ignore'):
                w = np.where(f > 0, v / f, np.nan)
            wlist.append(w)
        data_dict['WavelengthRawOffsets'] = wlist

    return data_dict  # type: ignore[return-value]










