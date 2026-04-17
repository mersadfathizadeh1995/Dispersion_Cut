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
    "border": "#808080",         # Gray borders (was purple)
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
    """Return Qt stylesheet for dark theme (Dracula-inspired) with improved borders."""
    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QMenuBar {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
        border-bottom: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QMenuBar::item:selected {{
        background-color: {DARK_THEME_COLORS['selection']};
    }}

    QMenu {{
        background-color: {DARK_THEME_COLORS['background']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QMenu::item:selected {{
        background-color: {DARK_THEME_COLORS['selection']};
    }}

    QPushButton {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['border']};
        padding: 5px 15px;
        border-radius: 3px;
    }}

    QPushButton:hover {{
        background-color: {DARK_THEME_COLORS['comment']};
        border: 2px solid {DARK_THEME_COLORS['cyan']};
    }}

    QPushButton:pressed {{
        background-color: {DARK_THEME_COLORS['comment']};
        border: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['border']};
        padding: 3px;
        border-radius: 2px;
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 2px solid {DARK_THEME_COLORS['cyan']};
    }}

    QLabel {{
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QGroupBox {{
        color: {DARK_THEME_COLORS['cyan']};
        border: 2px solid {DARK_THEME_COLORS['border']};
        border-radius: 5px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {DARK_THEME_COLORS['cyan']};
    }}

    QCheckBox, QRadioButton {{
        color: {DARK_THEME_COLORS['foreground']};
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        border: 2px solid {DARK_THEME_COLORS['border']};
        background-color: {DARK_THEME_COLORS['selection']};
    }}

    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {DARK_THEME_COLORS['cyan']};
    }}

    QDockWidget {{
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QDockWidget::title {{
        background-color: {DARK_THEME_COLORS['selection']};
        padding: 5px;
        border-bottom: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QTabWidget::pane {{
        border: 2px solid {DARK_THEME_COLORS['border']};
        background-color: {DARK_THEME_COLORS['background']};
    }}

    QTabBar::tab {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        padding: 5px 10px;
        margin-right: 2px;
        border: 2px solid {DARK_THEME_COLORS['comment']};
    }}

    QTabBar::tab:selected {{
        background-color: {DARK_THEME_COLORS['comment']};
        border: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QListWidget, QTreeView {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['border']};
    }}

    QScrollBar:vertical {{
        background-color: {DARK_THEME_COLORS['background']};
        width: 14px;
        margin: 0px;
        border: 1px solid {DARK_THEME_COLORS['comment']};
    }}

    QScrollBar::handle:vertical {{
        background-color: {DARK_THEME_COLORS['comment']};
        min-height: 20px;
        border-radius: 6px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {DARK_THEME_COLORS['cyan']};
    }}

    QScrollBar:horizontal {{
        background-color: {DARK_THEME_COLORS['background']};
        height: 14px;
        margin: 0px;
        border: 1px solid {DARK_THEME_COLORS['comment']};
    }}

    QScrollBar::handle:horizontal {{
        background-color: {DARK_THEME_COLORS['comment']};
        min-width: 20px;
        border-radius: 6px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {DARK_THEME_COLORS['cyan']};
    }}

    QToolTip {{
        background-color: {DARK_THEME_COLORS['selection']};
        color: {DARK_THEME_COLORS['foreground']};
        border: 2px solid {DARK_THEME_COLORS['cyan']};
    }}

    QAbstractSpinBox, QSpinBox, QDoubleSpinBox {{
        min-height: 24px;
    }}

    QComboBox {{
        min-height: 24px;
    }}
    """


def get_dark_high_contrast_stylesheet() -> str:
    """Return Qt stylesheet for high-contrast dark theme (better visibility)."""
    # Higher contrast colors
    bg = "#1a1a1a"       # Very dark gray
    fg = "#ffffff"        # Pure white text
    border = "#00bfff"    # Bright cyan borders
    accent = "#00ff00"    # Bright green accents
    hover = "#2a2a2a"     # Lighter dark gray
    selected = "#0080ff"  # Bright blue selection

    return f"""
    QMainWindow, QDialog, QWidget {{
        background-color: {bg};
        color: {fg};
    }}

    QMenuBar {{
        background-color: {bg};
        color: {fg};
        border-bottom: 2px solid {border};
    }}

    QMenuBar::item:selected {{
        background-color: {hover};
    }}

    QMenu {{
        background-color: {bg};
        color: {fg};
        border: 2px solid {border};
    }}

    QMenu::item:selected {{
        background-color: {selected};
    }}

    QPushButton {{
        background-color: {hover};
        color: {fg};
        border: 2px solid {border};
        padding: 5px 15px;
        border-radius: 3px;
    }}

    QPushButton:hover {{
        background-color: {selected};
        border: 2px solid {accent};
    }}

    QPushButton:pressed {{
        background-color: {accent};
        border: 2px solid {fg};
        color: {bg};
    }}

    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {hover};
        color: {fg};
        border: 2px solid {border};
        padding: 3px;
        border-radius: 2px;
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 3px solid {accent};
    }}

    QLabel {{
        color: {fg};
    }}

    QGroupBox {{
        color: {accent};
        border: 3px solid {border};
        border-radius: 5px;
        margin-top: 12px;
        padding-top: 10px;
        font-weight: bold;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
        color: {accent};
    }}

    QCheckBox, QRadioButton {{
        color: {fg};
    }}

    QCheckBox::indicator, QRadioButton::indicator {{
        border: 2px solid {border};
        background-color: {hover};
        width: 16px;
        height: 16px;
    }}

    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {accent};
        border: 2px solid {accent};
    }}

    QDockWidget {{
        color: {fg};
        border: 3px solid {border};
    }}

    QDockWidget::title {{
        background-color: {hover};
        padding: 5px;
        border-bottom: 2px solid {border};
    }}

    QTabWidget::pane {{
        border: 2px solid {border};
        background-color: {bg};
    }}

    QTabBar::tab {{
        background-color: {hover};
        color: {fg};
        padding: 5px 10px;
        margin-right: 2px;
        border: 2px solid {border};
    }}

    QTabBar::tab:selected {{
        background-color: {selected};
        border: 3px solid {accent};
    }}

    QListWidget, QTreeView {{
        background-color: {hover};
        color: {fg};
        border: 2px solid {border};
    }}

    QScrollBar:vertical {{
        background-color: {bg};
        width: 16px;
        margin: 0px;
        border: 1px solid {border};
    }}

    QScrollBar::handle:vertical {{
        background-color: {border};
        min-height: 20px;
        border-radius: 7px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {accent};
    }}

    QScrollBar:horizontal {{
        background-color: {bg};
        height: 16px;
        margin: 0px;
        border: 1px solid {border};
    }}

    QScrollBar::handle:horizontal {{
        background-color: {border};
        min-width: 20px;
        border-radius: 7px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {accent};
    }}

    QToolTip {{
        background-color: {hover};
        color: {accent};
        border: 2px solid {accent};
    }}

    QAbstractSpinBox, QSpinBox, QDoubleSpinBox {{
        min-height: 24px;
    }}

    QComboBox {{
        min-height: 24px;
    }}
    """


def get_light_stylesheet() -> str:
    """Return Qt stylesheet for light theme.

    A *minimal* override that only enforces readable colors on
    editable widgets.  On systems whose native palette is dark (e.g.
    Windows with system-wide dark mode) Qt's default rendering
    produces black-on-black cells inside QTableWidget edit sessions
    and QComboBox drop-downs.  The rules below force a neutral
    white-on-black look for the text of every commonly-used input
    widget, matching the rest of the light UI chrome.
    """
    return (
        # ── basic input widgets ────────────────────────────────────
        "QLineEdit, QTextEdit, QPlainTextEdit, "
        "QSpinBox, QDoubleSpinBox, QAbstractSpinBox, "
        "QComboBox {"
        "  background-color: #ffffff;"
        "  color: #000000;"
        "  selection-background-color: #1565C0;"
        "  selection-color: #ffffff;"
        "  border: 1px solid #b0b0b0;"
        "  padding: 2px 4px;"
        "}"
        "QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, "
        "QSpinBox:focus, QDoubleSpinBox:focus, QAbstractSpinBox:focus, "
        "QComboBox:focus {"
        "  border: 1px solid #1565C0;"
        "}"
        "QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, "
        "QComboBox:disabled {"
        "  background-color: #f0f0f0;"
        "  color: #808080;"
        "}"
        # ── combo-box drop-down list ───────────────────────────────
        "QComboBox QAbstractItemView {"
        "  background-color: #ffffff;"
        "  color: #000000;"
        "  selection-background-color: #1565C0;"
        "  selection-color: #ffffff;"
        "  border: 1px solid #b0b0b0;"
        "}"
        # ── QTableWidget / QTreeWidget body + cell editors ─────────
        "QTableView, QTableWidget, QTreeView, QTreeWidget, QListView, "
        "QListWidget {"
        "  background-color: #ffffff;"
        "  alternate-background-color: #f7f7f7;"
        "  color: #000000;"
        "  selection-background-color: #1565C0;"
        "  selection-color: #ffffff;"
        "}"
        "QTableView::item:selected, QTableWidget::item:selected, "
        "QTreeView::item:selected, QTreeWidget::item:selected, "
        "QListView::item:selected, QListWidget::item:selected {"
        "  background-color: #1565C0;"
        "  color: #ffffff;"
        "}"
        # When a QTableWidget opens an editor on double-click, the
        # embedded QLineEdit inherits this rule instead of the OS palette.
        "QTableView QLineEdit, QTableWidget QLineEdit, "
        "QTreeView QLineEdit, QTreeWidget QLineEdit, "
        "QAbstractItemView QLineEdit {"
        "  background-color: #ffffff;"
        "  color: #000000;"
        "  selection-background-color: #1565C0;"
        "  selection-color: #ffffff;"
        "  border: 1px solid #1565C0;"
        "}"
        # ── header sections ────────────────────────────────────────
        "QHeaderView::section {"
        "  background-color: #f0f0f0;"
        "  color: #202020;"
        "  padding: 3px;"
        "  border: 0;"
        "  border-right: 1px solid #d0d0d0;"
        "  border-bottom: 1px solid #d0d0d0;"
        "}"
        # ── Spin/combo sizing (let Fusion paint the buttons) ───────
        # With QStyleFactory.create("Fusion") installed at app
        # startup, Qt already draws well-proportioned step and
        # drop-down buttons with visible arrow glyphs.  We only tune
        # the overall height so they feel comfortable to click.
        "QAbstractSpinBox, QSpinBox, QDoubleSpinBox {"
        "  min-height: 24px;"
        "}"
        "QComboBox {"
        "  min-height: 24px;"
        "}"
    )


def apply_theme(app: QtWidgets.QApplication, theme_name: str = "light") -> None:
    """Apply theme to the Qt application.

    Args:
        app: QApplication instance
        theme_name: "light", "dark", or "dark-high-contrast"
    """
    if theme_name == "dark":
        app.setStyleSheet(get_dark_stylesheet())
    elif theme_name == "dark-high-contrast":
        app.setStyleSheet(get_dark_high_contrast_stylesheet())
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
    elif theme_name == "dark-high-contrast":
        return {
            "figure.facecolor": "#1a1a1a",
            "figure.edgecolor": "#1a1a1a",
            "axes.facecolor": "#1a1a1a",
            "axes.edgecolor": "#00bfff",
            "axes.labelcolor": "#ffffff",
            "text.color": "#ffffff",
            "xtick.color": "#ffffff",
            "ytick.color": "#ffffff",
            "grid.color": "#00bfff",
            "legend.facecolor": "#2a2a2a",
            "legend.edgecolor": "#00bfff",
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
