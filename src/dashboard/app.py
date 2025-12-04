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
            # For Streamlit Cloud, try multiple locations
            possible_dirs = [
                Path.cwd(),  # Current directory (Streamlit Cloud root)
                Path.cwd().parent,  # Parent directory
                script_path.parent.parent.parent.parent,  # Original structure
            ]
            
            data_dir = None
            for dir_path in possible_dirs:
                csv_path = dir_path / 'bank_transactions.csv'
                if csv_path.exists():
                    data_dir = dir_path
                    break
            
            if data_dir is None:
                st.warning("""
                ⚠️ **Fichiers CSV non trouvés**
                
                Les fichiers de données CSV doivent être dans le repository GitHub pour que l'application fonctionne.
                
                **Fichiers requis:**
                - `bank_transactions.csv`
                - `sales_invoices.csv`
                - `purchase_invoices.csv`
                
                **Solutions:**
                1. Ajoutez les fichiers CSV au repository GitHub
                2. Ou utilisez des données de démonstration (à implémenter)
                """)
                return
            
            config = get_config(script_path)
            bank, sales, purchase = load_all_data(data_dir)
            
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

