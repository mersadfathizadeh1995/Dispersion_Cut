"""
Export Wizard - Standalone Entry Point
======================================

Run the export wizard as a standalone application:
    python -m dc_cut.export_wizard [file_path]

Arguments:
    file_path: Optional path to a TXT or CSV file to load
"""

import sys
from pathlib import Path


def main():
    """Main entry point for standalone export wizard."""
    from matplotlib.backends import qt_compat
    QtWidgets = qt_compat.QtWidgets
    from .wizard_main import ExportWizardWindow
    
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Export Wizard")
    app.setOrganizationName("DC Cut")
    
    window = ExportWizardWindow()
    window.setWindowTitle("Export Wizard")
    
    # Load file if provided as argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if Path(file_path).exists():
            window.load_file(file_path)
    
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
