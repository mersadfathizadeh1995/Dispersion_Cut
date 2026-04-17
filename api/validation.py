"""Input validation for API operations.

Validates paths, data shapes, and parameter ranges before calling core.
"""
from __future__ import annotations

import os
from typing import List, Dict, Any

import numpy as np


def validate_file_path(path: str, must_exist: bool = True) -> Dict[str, Any]:
    """Validate a file path."""
    errors: List[str] = []
    if not path:
        errors.append("File path is empty.")
    elif must_exist and not os.path.isfile(path):
        errors.append(f"File not found: {path}")
    return {"valid": len(errors) == 0, "errors": errors}


def validate_output_path(path: str) -> Dict[str, Any]:
    """Validate an output file path (parent directory must exist)."""
    errors: List[str] = []
    if not path:
        errors.append("Output path is empty.")
    else:
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent):
            errors.append(f"Output directory does not exist: {parent}")
    return {"valid": len(errors) == 0, "errors": errors}


def validate_arrays(
    velocity: np.ndarray,
    frequency: np.ndarray,
    wavelength: np.ndarray,
) -> Dict[str, Any]:
    """Validate that dispersion arrays are consistent."""
    errors: List[str] = []
    if velocity.shape != frequency.shape:
        errors.append(
            f"Velocity and frequency array shapes differ: "
            f"{velocity.shape} vs {frequency.shape}"
        )
    if velocity.shape != wavelength.shape:
        errors.append(
            f"Velocity and wavelength array shapes differ: "
            f"{velocity.shape} vs {wavelength.shape}"
        )
    if velocity.size == 0:
        errors.append("Arrays are empty.")
    return {"valid": len(errors) == 0, "errors": errors}


def validate_positive(value: float, name: str) -> Dict[str, Any]:
    """Validate that a value is positive."""
    errors: List[str] = []
    if value <= 0:
        errors.append(f"{name} must be positive, got {value}")
    return {"valid": len(errors) == 0, "errors": errors}
