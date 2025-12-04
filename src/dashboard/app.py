"""
Streamlit Dashboard Application

This is a placeholder for the dashboard. The full dashboard implementation
would be migrated from the original cash_forecast_complete.py file.
"""
import sys
from pathlib import Path
import streamlit as st

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Use absolute imports from src
from src.config import get_config
from src.data import load_all_data, calculate_metrics
from src.utils import get_real_exchange_rates


def main():
    """
    Main dashboard application.
    """
    st.set_page_config(
        page_title="Cash Flow Forecasting - Version Améliorée",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Cash Flow Forecasting")
    st.markdown("### Version Améliorée - Architecture Modulaire")
    
    st.info("""
    🚧 **Dashboard en cours de développement**
    
    Cette version améliorée utilise une architecture modulaire. 
    Le dashboard complet sera migré depuis l'ancienne version.
    
    Pour l'instant, utilisez le mode script:
    ```bash
    python main.py --script
    ```
    """)
    
    # Basic data loading demo
    with st.expander("🔍 Test de chargement des données"):
        try:
            # Get config - data_dir should be parent of Python directory
            script_path = Path(__file__).absolute()
            # Go up: dashboard -> src -> Python -> deliverables_improved
            # For Streamlit Cloud, data should be in parent directory
            data_dir = script_path.parent.parent.parent.parent
            config = get_config(script_path)
            # Try to load from data_dir (parent of Python/)
            try:
                bank, sales, purchase = load_all_data(data_dir)
            except FileNotFoundError:
                # If not found, try current directory (for Streamlit Cloud)
                bank, sales, purchase = load_all_data(Path.cwd())
            
            st.success("✅ Données chargées avec succès!")
            st.write(f"- Transactions: {len(bank)}")
            st.write(f"- Factures clients: {len(sales)}")
            st.write(f"- Factures fournisseurs: {len(purchase)}")
            
            # Calculate metrics
            fx_rates = get_real_exchange_rates(verbose=False)
            metrics = calculate_metrics(bank, sales, purchase, fx_rates)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("DSO", f"{metrics['dso_mean']:.1f} jours")
            with col2:
                st.metric("DPO", f"{metrics['dpo_mean']:.1f} jours")
                
        except Exception as e:
            st.error(f"❌ Erreur: {e}")


if __name__ == "__main__":
    main()

