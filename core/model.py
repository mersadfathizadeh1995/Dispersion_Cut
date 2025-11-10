from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class LayerData:
    label: str
    frequency: np.ndarray
    velocity: np.ndarray
    wavelength: np.ndarray
    visible: bool = True


class LayersModel:
    def __init__(self, layers: Optional[List[LayerData]] = None) -> None:
        self.layers: List[LayerData] = list(layers or [])

    @classmethod
    def from_arrays(
        cls,
        velocity_arrays: List[np.ndarray],
        frequency_arrays: List[np.ndarray],
        wavelength_arrays: List[np.ndarray],
        labels: List[str],
    ) -> "LayersModel":
        layers: List[LayerData] = []
        n = min(len(velocity_arrays), len(frequency_arrays), len(wavelength_arrays), len(labels))
        for i in range(n):
            v = np.asarray(velocity_arrays[i], float)
            f = np.asarray(frequency_arrays[i], float)
            w = np.asarray(wavelength_arrays[i], float)
            layers.append(LayerData(label=str(labels[i]), frequency=f, velocity=v, wavelength=w, visible=True))
        return cls(layers)

    def to_arrays(self, only_visible: bool = False) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray], List[str]]:
        v_list: List[np.ndarray] = []
        f_list: List[np.ndarray] = []
        w_list: List[np.ndarray] = []
        labels: List[str] = []
        for ld in self.layers:
            if only_visible and not ld.visible:
                continue
            v_list.append(ld.velocity)
            f_list.append(ld.frequency)
            w_list.append(ld.wavelength)
            labels.append(ld.label)
        return v_list, f_list, w_list, labels

    def add_new_layer(self, label: str, v: np.ndarray, f: np.ndarray, w: np.ndarray) -> None:
        self.layers.append(LayerData(label=label, frequency=np.asarray(f, float), velocity=np.asarray(v, float), wavelength=np.asarray(w, float), visible=True))

    def merge_into(self, idx: int, v: np.ndarray, f: np.ndarray, w: np.ndarray) -> None:
        ld = self.layers[idx]
        ld.velocity = np.concatenate([ld.velocity, np.asarray(v, float)])
        ld.frequency = np.concatenate([ld.frequency, np.asarray(f, float)])
        ld.wavelength = np.concatenate([ld.wavelength, np.asarray(w, float)])

    def set_visible(self, idx: int, visible: bool) -> None:
        self.layers[idx].visible = bool(visible)

    def get_visible_arrays(self) -> Tuple[List[np.ndarray], List[np.ndarray], List[np.ndarray]]:
        v, f, w, _ = self.to_arrays(only_visible=True)
        return v, f, w










