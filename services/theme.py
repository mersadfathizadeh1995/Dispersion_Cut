from __future__ import annotations

from typing import Dict
from matplotlib.backends import qt_compat

QtWidgets = qt_compat.QtWidgets
QtGui = qt_compat.QtGui


# Dracula-inspired dark theme colors (dimmed, not pure black)
DARK_THEME_COLORS = {
    "background": "#282a36",      # Main background
    "foreground": "#f8f8f2",      # Text color
    "selection": "#44475a",       # Selection background
    "comment": "#6272a4",         # Secondary text
    "cyan": "#8be9fd",           # Accent 1
    "green": "#50fa7b",          # Accent 2
    "orange": "#ffb86c",         # Accent 3
    "pink": "#ff79c6",           # Accent 4
    "purple": "#bd93f9",         # Accent 5
    "red": "#ff5555",            # Error/warning
    "yellow": "#f1fa8c",         # Highlight
}

# Light theme colors (default)
LIGHT_THEME_COLORS = {
    "background": "#ffffff",
    "foreground": "#000000",
    "selection": "#e0e0e0",
    "comment": "#808080",
}


def get_dark_stylesheet() -> str:
    """Return Qt stylesheet for dark theme (Dracula-inspired)."""
    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QMenuBar {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
        border-bottom: 1px solid {DARK_THEME_COLORS['selection']};
    }}

    QMenuBar::item:selected {{
        background-color: {DARK_THEME_COLORS['selection']};
    }}

    QMenu {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['selection']};
    }}

    QMenu::item:selected {{
        background-color: {DARK_THEME_COLORS['selection']};
    }}

    QPushButton {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['comment']};
        padding: 5px 15px;
        border-radius: 3px;
    }}

    QPushButton:hover {{
        background-color: {DARK_THEME_COLORS['comment']};
    }}

    QPushButton:pressed {{
        background-color: {DARK_THEME_COLORS['purple']};
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['comment']};
        padding: 3px;
        border-radius: 2px;
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {DARK_THEME_COLORS['cyan']};
    }}

    QLabel {{
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QGroupBox {{
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['comment']};
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px;
    }}

    QCheckBox, QRadioButton {{
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QDockWidget {{
        color: {DARK_THEME_COLORS['foreground']};
        titlebar-close-icon: url(close.png);
        titlebar-normal-icon: url(float.png);
    }}

    QDockWidget::title {{
        background-color: {DARK_THEME_COLORS['selection']};
        padding: 5px;
    }}

    QTabWidget::pane {{
        border: 1px solid {DARK_THEME_COLORS['comment']};
        background-color: {DARK_THEME_COLORS['background']};
    }}

    QTabBar::tab {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        padding: 5px 10px;
        margin-right: 2px;
    }}

    QTabBar::tab:selected {{
        background-color: {DARK_THEME_COLORS['purple']};
    }}

    QListWidget, QTreeView {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['comment']};
    }}

    QScrollBar:vertical {{
        background-color: {DARK_THEME_COLORS['background']};
        width: 12px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {DARK_THEME_COLORS['comment']};
        min-height: 20px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {DARK_THEME_COLORS['purple']};
    }}

    QScrollBar:horizontal {{
        background-color: {DARK_THEME_COLORS['background']};
        height: 12px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {DARK_THEME_COLORS['comment']};
        min-width: 20px;
        border-radius: 6px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {DARK_THEME_COLORS['purple']};
    }}

    QToolTip {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 1px solid {DARK_THEME_COLORS['comment']};
    }}
    """


def get_light_stylesheet() -> str:
    """Return Qt stylesheet for light theme (default/minimal)."""
    return ""  # Use system default for light theme


def apply_theme(app: QtWidgets.QApplication, theme_name: str = "light") -> None:
    """Apply theme to the Qt application.

    Args:
        app: QApplication instance
        theme_name: Either "light" or "dark"
    """
    if theme_name == "dark":
        app.setStyleSheet(get_dark_stylesheet())
    else:
        app.setStyleSheet(get_light_stylesheet())


def get_matplotlib_style(theme_name: str = "light") -> Dict[str, any]:
    """Get matplotlib rcParams for the given theme.

    Returns dict of matplotlib style parameters to update rcParams with.
    """
    if theme_name == "dark":
        return {
            "figure.facecolor": DARK_THEME_COLORS["background"],
            "figure.edgecolor": DARK_THEME_COLORS["background"],
            "axes.facecolor": DARK_THEME_COLORS["background"],
            "axes.edgecolor": DARK_THEME_COLORS["comment"],
            "axes.labelcolor": DARK_THEME_COLORS["foreground"],
            "text.color": DARK_THEME_COLORS["foreground"],
            "xtick.color": DARK_THEME_COLORS["foreground"],
            "ytick.color": DARK_THEME_COLORS["foreground"],
            "grid.color": DARK_THEME_COLORS["selection"],
            "legend.facecolor": DARK_THEME_COLORS["selection"],
            "legend.edgecolor": DARK_THEME_COLORS["comment"],
        }
    else:
        # Return empty dict for light theme (use matplotlib defaults)
        return {}


def apply_matplotlib_theme(theme_name: str = "light") -> None:
    """Apply theme to matplotlib plots.

    Args:
        theme_name: Either "light" or "dark"
    """
    try:
        import matplotlib.pyplot as plt
        style = get_matplotlib_style(theme_name)
        if style:
            plt.rcParams.update(style)
    except Exception:
        pass  # Matplotlib not available or update failed
