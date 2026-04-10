from __future__ import annotations

import pickle
from typing import Dict


def save_session(state: Dict, filename: str) -> None:
    with open(filename, 'wb') as f:
        pickle.dump(state, f)


def load_session(filename: str) -> Dict:
    with open(filename, 'rb') as f:
        return pickle.load(f)










