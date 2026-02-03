"""
Save/Export Widget
==================

Widget for saving/exporting processed curves.
"""

import os
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QCheckBox, QComboBox,
    QLineEdit, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class SaveSettings:
    """Save/export settings."""
    format: str = "txt"  # "txt", "csv", "json"
    directory: str = ""
    filename: str = ""


class SaveWidget(QWidget):
    """Widget for save/export options."""
    
    settings_changed = Signal()
    save_requested = Signal()  # Emitted when Save button is clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._curve_name = "curve"
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Format selection
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["TXT (Dinver)", "CSV", "JSON"])
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        layout.addLayout(format_layout)
        
        # Format info
        self.format_info = QLabel("frequency  slowness  logstd  0")
        self.format_info.setStyleSheet("color: gray; font-size: 10px; font-family: monospace;")
        layout.addWidget(self.format_info)
        
        # Directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Directory:"))
        
        self.dir_edit = QLineEdit()
        self.dir_edit.setPlaceholderText("Select output directory...")
        self.dir_edit.textChanged.connect(self._emit_changed)
        dir_layout.addWidget(self.dir_edit)
        
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(30)
        self.browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(self.browse_btn)
        layout.addLayout(dir_layout)
        
        # Filename
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Filename:"))
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("curve_processed")
        self.name_edit.textChanged.connect(self._emit_changed)
        name_layout.addWidget(self.name_edit)
        
        self.ext_label = QLabel(".txt")
        name_layout.addWidget(self.ext_label)
        layout.addLayout(name_layout)
        
        # Save button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.save_btn = QPushButton("Save Curve")
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
    
    def _on_format_changed(self, index: int):
        formats = [".txt", ".csv", ".json"]
        infos = [
            "frequency  slowness  logstd  0",
            "frequency,velocity,velocity_std",
            '{"frequency": [...], "velocity": [...], "std": [...]}'
        ]
        self.ext_label.setText(formats[index])
        self.format_info.setText(infos[index])
        self._emit_changed()
    
    def _browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self.dir_edit.text()
        )
        if directory:
            self.dir_edit.setText(directory)
    
    def _emit_changed(self):
        self.settings_changed.emit()
    
    def _on_save(self):
        self.save_requested.emit()
    
    def get_settings(self) -> SaveSettings:
        """Get current settings."""
        formats = ["txt", "csv", "json"]
        return SaveSettings(
            format=formats[self.format_combo.currentIndex()],
            directory=self.dir_edit.text(),
            filename=self.name_edit.text() or self._curve_name
        )
    
    def set_settings(self, settings: SaveSettings):
        """Set settings."""
        format_idx = {"txt": 0, "csv": 1, "json": 2}.get(settings.format, 0)
        self.format_combo.setCurrentIndex(format_idx)
        self.dir_edit.setText(settings.directory)
        self.name_edit.setText(settings.filename)
    
    def set_curve_name(self, name: str):
        """Set default filename from curve name."""
        self._curve_name = name
        if not self.name_edit.text():
            self.name_edit.setPlaceholderText(f"{name}_processed")
    
    def set_directory(self, directory: str):
        """Set default directory."""
        if not self.dir_edit.text():
            self.dir_edit.setText(directory)
    
    def get_output_path(self) -> str:
        """Get full output path."""
        settings = self.get_settings()
        ext = {"txt": ".txt", "csv": ".csv", "json": ".json"}[settings.format]
        filename = settings.filename or self._curve_name
        return os.path.join(settings.directory, filename + ext)


def save_curve_txt(filepath: str, frequency: np.ndarray, velocity: np.ndarray, 
                   velstd: np.ndarray, logstd: Optional[np.ndarray] = None):
    """Save curve in Dinver TXT format.
    
    Format: frequency  slowness  logstd  0
    """
    slowness = 1.0 / velocity
    
    if logstd is None:
        # Calculate logstd from velocity std
        # logstd = ln(v_upper/v) where v_upper = v + std
        logstd = np.log((velocity + velstd) / velocity)
    
    with open(filepath, 'w') as f:
        for freq, slow, lstd in zip(frequency, slowness, logstd):
            f.write(f"{freq:.6f} {slow:.10f} {lstd:.10f} 0\n")


def save_curve_csv(filepath: str, frequency: np.ndarray, velocity: np.ndarray, 
                   velstd: np.ndarray):
    """Save curve in CSV format with header."""
    with open(filepath, 'w') as f:
        f.write("frequency,velocity,velocity_std\n")
        for freq, vel, std in zip(frequency, velocity, velstd):
            f.write(f"{freq:.6f},{vel:.4f},{std:.4f}\n")


def save_curve_json(filepath: str, frequency: np.ndarray, velocity: np.ndarray, 
                    velstd: np.ndarray, metadata: Optional[dict] = None):
    """Save curve in JSON format."""
    data = {
        "frequency": frequency.tolist(),
        "velocity": velocity.tolist(),
        "velocity_std": velstd.tolist()
    }
    if metadata:
        data["metadata"] = metadata
    
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
