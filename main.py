#!/usr/bin/env python3
"""
Cash Flow Forecasting - Main Entry Point

This is the improved, modular version of the cash flow forecasting system.

Usage:
    - Dashboard mode: python main.py
    - Script mode: python main.py --script
    - Dashboard manual: streamlit run main.py
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Check if running in script mode
SCRIPT_MODE = "--script" in sys.argv

# Detect if running via streamlit
IS_STREAMLIT_RUN = "streamlit" in sys.modules or os.environ.get("STREAMLIT_SERVER_PORT") is not None

STREAMLIT_MODE = False
if IS_STREAMLIT_RUN and not SCRIPT_MODE:
    try:
        import streamlit as st
        STREAMLIT_MODE = True
    except ImportError:
        STREAMLIT_MODE = False

# If not in Streamlit and not script mode, launch dashboard automatically
if not STREAMLIT_MODE and not SCRIPT_MODE and __name__ == "__main__":
    import subprocess
    
    script_path = Path(__file__).absolute()
    python_path = sys.executable
    
    print("=" * 70)
    print("🚀 LANCEMENT AUTOMATIQUE DU DASHBOARD (VERSION AMÉLIORÉE)")
    print("=" * 70)
    print(f"📊 Ouverture du dashboard interactif...")
    print(f"🌐 Le navigateur s'ouvrira automatiquement sur http://localhost:8501")
    print(f"\n💡 Pour lancer le mode script (forecast complet), utilisez:")
    print(f"   python {Path(__file__).name} --script")
    print(f"\n⏹️  Pour arrêter le dashboard, appuyez sur Ctrl+C dans ce terminal")
    print("=" * 70)
    print()
    
    try:
        subprocess.run([
            python_path, "-m", "streamlit", "run", str(script_path),
            "--server.headless", "false",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n\n✅ Dashboard arrêté")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur lors du lancement du dashboard: {e}")
        print("\n💡 Essayez manuellement:")
        print(f"   streamlit run {script_path}")
        sys.exit(1)
    
    sys.exit(0)

# Import modules based on mode
if STREAMLIT_MODE:
    # Dashboard mode - import dashboard
    from dashboard.app import main as dashboard_main
    
    if __name__ == "__main__":
        dashboard_main()
elif SCRIPT_MODE:
    # Script mode - run forecast
    from forecast.script import run_forecast_script
    
    if __name__ == "__main__":
        run_forecast_script()

