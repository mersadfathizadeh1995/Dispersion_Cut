"""Sheet persistence -- save/load complete sheet state (settings + data references).

Each sheet is stored as a folder under ``{project_dir}/sheets/{sheet_name}/``
containing a ``manifest.json`` with the full settings snapshot and metadata.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Tuple, Optional

from .models import ReportStudioSettings
from .config_persistence import settings_to_dict, settings_from_dict

SHEET_STATE_VERSION = 1


def _sanitize_name(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]', '_', name).strip()
    return safe or "sheet"


def save_sheet(
    project_dir: str,
    sheet_name: str,
    settings: ReportStudioSettings,
    *,
    extra_metadata: dict | None = None,
) -> str:
    """Save a sheet to ``{project_dir}/sheets/{sheet_name}/manifest.json``.

    Overwrites any existing sheet with the same name.
    Returns the path to the sheet folder.
    """
    sheets_dir = os.path.join(project_dir, "sheets")
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(sheets_dir, safe_name)

    if os.path.isdir(sheet_dir):
        shutil.rmtree(sheet_dir)
    os.makedirs(sheet_dir, exist_ok=True)

    manifest = {
        "_version": SHEET_STATE_VERSION,
        "sheet_name": sheet_name,
        "settings": settings_to_dict(settings),
    }
    if extra_metadata:
        manifest["metadata"] = extra_metadata

    manifest_path = os.path.join(sheet_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return sheet_dir


def load_sheet(
    sheet_path: str,
) -> Tuple[str, ReportStudioSettings]:
    """Load a sheet from its folder.

    Parameters
    ----------
    sheet_path : str
        Path to the sheet folder (contains ``manifest.json``).

    Returns
    -------
    (sheet_name, settings)
    """
    manifest_path = os.path.join(sheet_path, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    sheet_name = manifest.get("sheet_name", os.path.basename(sheet_path))
    settings_dict = manifest.get("settings", {})
    settings = settings_from_dict(settings_dict)

    return sheet_name, settings


def list_saved_sheets(project_dir: str) -> list:
    """Return ``[(sheet_name, folder_path), ...]`` for saved sheets."""
    sheets_dir = os.path.join(project_dir, "sheets")
    if not os.path.isdir(sheets_dir):
        return []
    results = []
    for entry in sorted(os.listdir(sheets_dir)):
        folder = os.path.join(sheets_dir, entry)
        manifest = os.path.join(folder, "manifest.json")
        if os.path.isfile(manifest):
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                name = data.get("sheet_name", entry)
            except Exception:
                name = entry
            results.append((name, folder))
    return results


def delete_saved_sheet(project_dir: str, sheet_name: str) -> bool:
    """Delete a saved sheet folder. Returns True if deleted."""
    safe_name = _sanitize_name(sheet_name)
    sheet_dir = os.path.join(project_dir, "sheets", safe_name)
    if os.path.isdir(sheet_dir):
        shutil.rmtree(sheet_dir)
        return True
    return False
