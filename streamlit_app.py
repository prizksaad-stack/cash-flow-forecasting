#!/usr/bin/env python3
"""
Streamlit App for Cash Flow Forecasting

This is the entry point for Streamlit Cloud deployment.
Streamlit Cloud will automatically run this file.
"""
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add root to path for absolute imports
root_path = Path(__file__).parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

# Import and run dashboard
from src.dashboard.app import main

if __name__ == "__main__":
    main()

