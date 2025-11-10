#!/usr/bin/env python3
"""
Simple runner script to launch DC Cut application.
Just double-click this file or run: python run_dc_cut.py
"""

import sys
import os
from pathlib import Path

# Add the DC_Cut directory to Python path
# Since this script is inside dc_cut folder, we go up one level to DC_Cut
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

# Change to the repository directory
os.chdir(repo_root)

try:
    # Launch the DC Cut application
    print("Starting DC Cut application...")
    from dc_cut.app import main
    main()
    
except ImportError as e:
    print(f"Error: Missing dependencies - {e}")
    print("\nPlease install required packages:")
    print("pip install numpy pandas matplotlib pyqt6 scipy")
    input("\nPress Enter to exit...")
    
except Exception as e:
    print(f"Error starting application: {e}")
    input("\nPress Enter to exit...")
