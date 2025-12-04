"""
Streamlit Dashboard Application - Version Complète

Dashboard interactif complet pour le Cash Flow Forecasting
avec toutes les fonctionnalités: visualisations, forecast, scénarios, etc.
"""
import sys
from pathlib import Path
from datetime import datetime, date
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Add root to path for absolute imports
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

# Use absolute imports from src
from src.config import (
    get_config, MAX_FORECAST_DATE, DEBT_PRINCIPAL, 
    DEBT_INTEREST_RATE, DEBT_MONTHLY_INTEREST, DEBT_SPREAD, EURIBOR_3M_BASE
)
from src.data import load_all_data, calculate_metrics
from src.utils import get_real_exchange_rates
from src.forecast.engine import run_forecast


# CSS personnalisé
def load_css():
    """Charge le CSS personnalisé pour le dashboard"""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f77b4;
            text-align: center;
            padding: 1rem 0;
            border-bottom: 3px solid #1f77b4;
            margin-bottom: 2rem;
        }
        .section-header {
            font-size: 1.8rem;
            font-weight: bold;
            color: #2c3e50;
            margin-top: 2rem;
            margin-bottom: 1rem;
            padding: 0.5rem;
            background: linear-gradient(90deg, #e8f4f8 0%, #ffffff 100%);
            border-left: 5px solid #1f77b4;
        }
        .calculation-box {
            background: #fff3cd;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #ffc107;
            margin: 1rem 0;
            color: #856404;
            font-weight: 500;
        }
        .formula-box {
            background: #e7f3ff;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #0066cc;
            margin: 1rem 0;
            font-family: 'Courier New', monospace;
            color: #004085;
            font-weight: 500;
        }
        .step-box {
            background: #d4edda;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            margin: 1rem 0;
            color: #155724;
            font-weight: 500;
        }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data
def load_data_cached(data_dir: Path):
    """Charge les données avec cache Streamlit"""
    return load_all_data(data_dir)


def main():
    """
    Main dashboard application - Version complète
    """
    st.set_page_config(
        page_title="Cash Flow Forecasting - Dashboard Professionnel",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Charger le CSS
    load_css()
    
    st.markdown('<div class="main-header">📊 Cash Flow Forecasting - Dashboard Professionnel</div>', unsafe_allow_html=True)
    
    # Sidebar Navigation
    st.sidebar.title("📑 Navigation")
    section = st.sidebar.radio(
        "Choisir une section:",
        [
            "🏠 Vue d'ensemble",
            "📚 Méthodes & Théorie",
            "🔢 Calculs Détailés",
            "📈 Visualisations",
            "⚙️ Paramètres & Facteurs",
            "🎯 Lancer Forecast",
            "📊 Scénarios & Risques"
        ]
    )
    
    # Charger les données
    try:
        # Trouver le répertoire des données
        script_path = Path(__file__).absolute()
        possible_dirs = [
            Path.cwd(),  # Streamlit Cloud root
            Path.cwd().parent,
            script_path.parent.parent.parent.parent,
        ]
        
        data_dir = None
        for dir_path in possible_dirs:
            csv_path = dir_path / 'bank_transactions.csv'
            if csv_path.exists():
                data_dir = dir_path
                break
        
        if data_dir is None:
            data_dir = Path.cwd()
            if not (data_dir / 'bank_transactions.csv').exists():
                st.error("❌ Fichiers CSV non trouvés. Vérifiez que les fichiers sont dans le repository.")
                st.stop()
        
        # Charger les données
        bank, sales, purchase = load_data_cached(data_dir)
        
        # Calculer les métriques
        fx_rates = get_real_exchange_rates(verbose=False)
        metrics = calculate_metrics(bank, sales, purchase, fx_rates)
        
        # Variables pour le dashboard (disponibles dans toutes les sections)
        dso_mean = metrics['dso_mean']
        dpo_mean = metrics['dpo_mean']
        bank = metrics['bank']  # Bank avec amount_eur
        
        # Calculer toutes les variables nécessaires pour le forecast
        avg_daily_credit = metrics['avg_daily_credit']
        avg_daily_debit = metrics['avg_daily_debit']
        std_daily_credit = metrics['std_daily_credit']
        std_daily_debit = metrics['std_daily_debit']
        weekly_credit_pattern = metrics['weekly_credit_pattern']
        weekly_debit_pattern = metrics['weekly_debit_pattern']
        
        # Calculer l'inflation depuis les données récurrentes
        bank_recurring = bank[bank['category'].isin(['Supplier Payment', 'Payroll', 'Loan Interest'])].copy()
        monthly_recurring = pd.Series(dtype=float)  # Initialiser pour éviter erreur de scope
        if len(bank_recurring) > 0:
            bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')
            monthly_recurring = bank_recurring.groupby('month')['amount_eur'].sum().sort_index()
            
            if len(monthly_recurring) >= 6:
                growth_rates = []
                for i in range(1, len(monthly_recurring)):
                    if monthly_recurring.iloc[i-1] > 0:
                        growth = (monthly_recurring.iloc[i] - monthly_recurring.iloc[i-1]) / monthly_recurring.iloc[i-1]
                        growth_rates.append(growth)
                if len(growth_rates) > 0:
                    avg_monthly_growth = np.mean(growth_rates)
                    annual_inflation = avg_monthly_growth * 12
                    if annual_inflation < 0 or annual_inflation > 0.10:
                        inflation_rate = 0.02
                    else:
                        inflation_rate = annual_inflation
                else:
                    inflation_rate = 0.02
            else:
                inflation_rate = 0.02
        else:
            inflation_rate = 0.02
        
        # Volatilité des volumes
        volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
        volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
        
        # Taux de retard
        overdue_rate_sales = len(sales[sales['status']=='Overdue']) / len(sales) if len(sales) > 0 else 0
        overdue_rate_purchase = len(purchase[purchase['status']=='Overdue']) / len(purchase) if len(purchase) > 0 else 0
        
        # Écart-types DSO/DPO
        sales_paid_valid = metrics.get('sales_paid_valid', pd.DataFrame())
        purchase_paid_valid = metrics.get('purchase_paid_valid', pd.DataFrame())
        dso_std = sales_paid_valid['days_to_pay'].std() if len(sales_paid_valid) > 0 and 'days_to_pay' in sales_paid_valid.columns else 0
        dpo_std = purchase_paid_valid['days_to_pay'].std() if len(purchase_paid_valid) > 0 and 'days_to_pay' in purchase_paid_valid.columns else 0
        
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des données: {e}")
        import traceback
        with st.expander("🔍 Détails de l'erreur"):
            st.code(traceback.format_exc())
        st.stop()
    
    # ========================================================================
    # SECTION 1: VUE D'ENSEMBLE
    # ========================================================================
    if section == "🏠 Vue d'ensemble":
        st.markdown('<div class="section-header">🏠 Vue d\'ensemble du Projet</div>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 Transactions", f"{len(bank):,}")
        with col2:
            st.metric("💰 Factures Clients", f"{len(sales):,}")
        with col3:
            st.metric("📋 Factures Fournisseurs", f"{len(purchase):,}")
        with col4:
            st.metric("📅 Période", f"{bank['date'].min().strftime('%Y-%m-%d')} à {bank['date'].max().strftime('%Y-%m-%d')}")
        
        st.markdown("---")
        st.markdown("### 📐 Méthode de Forecast: Direct Method")
        st.info("""
        **Direct Method (Méthode Directe)** - Forecast transaction par transaction
        
        Cette méthode est recommandée pour le **court terme (0-13 semaines)** car elle :
        - ✅ Utilise les factures ouvertes réelles
        - ✅ S'appuie sur les moyennes historiques
        - ✅ Intègre les patterns de saisonnalité
        - ✅ Permet une précision élevée sur 3 mois
        """)
        
        st.markdown("### 🔄 Processus de Forecast (8 Étapes)")
        steps = [
            ("1️⃣ Chargement & Nettoyage", "Lecture des CSV, détection d'anomalies, calcul DSO/DPO"),
            ("2️⃣ Classification", "Identification des transactions récurrentes vs non-récurrentes"),
            ("3️⃣ Saisonnalité", "Détection des patterns hebdomadaires et mensuels"),
            ("4️⃣ Facteurs d'Impact", "Calcul de l'inflation, volatilité, retards, impayés, FX"),
            ("5️⃣ Forecast Quotidien", "Calcul jour par jour des encaissements/décaissements"),
            ("6️⃣ Multi-Devises", "Gestion séparée EUR, USD, JPY avec conversion"),
            ("7️⃣ Détection de Risques", "Identification des jours critiques et zones de risque"),
            ("8️⃣ Recommandations", "Actions correctives selon la situation de trésorerie")
        ]
        
        for step_num, step_desc in steps:
            st.markdown(f'<div class="step-box"><strong>{step_num}</strong> {step_desc}</div>', unsafe_allow_html=True)
    
    # ========================================================================
    # SECTION 2: MÉTHODES & THÉORIE
    # ========================================================================
    elif section == "📚 Méthodes & Théorie":
        st.markdown('<div class="section-header">📚 Méthodes de Cash Flow Forecasting</div>', unsafe_allow_html=True)
        
        # DSO
        st.markdown("### 1️⃣ DSO (Days Sales Outstanding) - Délai de Recouvrement")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("""
            **Définition:**
            Le DSO mesure le nombre moyen de jours nécessaires pour recouvrer les créances clients.
            C'est un indicateur clé de la gestion de trésorerie.
            """)
            st.markdown('<div class="formula-box">DSO = (Créances clients / Chiffre d\'affaires) × Nombre de jours</div>', unsafe_allow_html=True)
            st.markdown("""
            **Dans notre calcul:**
            - On utilise les factures payées historiquement
            - DSO = Moyenne des jours entre émission et paiement
            - Permet de prévoir quand les factures ouvertes seront payées
            """)
        with col2:
            st.metric("DSO Moyen", f"{dso_mean:.1f} jours")
            if dso_mean > 45:
                st.warning("⚠️ DSO élevé - Risque de trésorerie")
            elif dso_mean < 30:
                st.success("✅ DSO optimal")
        
        st.markdown("---")
        
        # DPO
        st.markdown("### 2️⃣ DPO (Days Payable Outstanding) - Délai de Paiement")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("""
            **Définition:**
            Le DPO mesure le nombre moyen de jours avant de payer les fournisseurs.
            Un DPO élevé améliore la trésorerie mais peut affecter les relations.
            """)
            st.markdown('<div class="formula-box">DPO = (Dettes fournisseurs / Coûts) × Nombre de jours</div>', unsafe_allow_html=True)
            st.markdown("""
            **Dans notre calcul:**
            - Analyse des factures fournisseurs payées
            - DPO = Moyenne des jours entre émission et paiement
            - Utilisé pour prévoir les décaissements futurs
            """)
        with col2:
            st.metric("DPO Moyen", f"{dpo_mean:.1f} jours")
            if dpo_mean > 60:
                st.info("ℹ️ DPO élevé - Bon pour trésorerie")
            elif dpo_mean < 20:
                st.warning("⚠️ DPO court - Pression sur trésorerie")
        
        st.markdown("---")
        
        # Direct Method
        st.markdown("### 3️⃣ Direct Method (Méthode Directe)")
        st.markdown("""
        **Principe:**
        La méthode directe prévoit les flux de trésorerie en analysant chaque transaction individuellement.
        """)
        st.markdown("""
        **Avantages:**
        - ✅ Précision élevée sur court terme
        - ✅ Utilise les données réelles (factures ouvertes)
        - ✅ Intègre les patterns de paiement réels
        - ✅ Adapté à la gestion quotidienne
        
        **Limitations:**
        - ⚠️ Nécessite des données détaillées
        - ⚠️ Moins adapté au long terme (>1 an)
        - ⚠️ Sensible aux variations exceptionnelles
        """)
        
        st.markdown("---")
        
        # Classification
        st.markdown("### 4️⃣ Classification Récurrent vs Non-Récurrent")
        category_classification = {
            'Payroll': 'Récurrent',
            'Supplier Payment': 'Récurrent',
            'Loan Interest': 'Récurrent',
            'Bank Fee': 'Récurrent',
            'Tax Payment': 'Récurrent',
            'Transfer to Payroll': 'Récurrent'
        }
        bank['flow_type'] = bank['category'].map(category_classification).fillna('Non-récurrent')
        recurring_count = len(bank[bank['flow_type'] == 'Récurrent'])
        non_recurring_count = len(bank[bank['flow_type'] == 'Non-récurrent'])
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(
                values=[recurring_count, non_recurring_count],
                names=['Récurrent', 'Non-récurrent'],
                title="Répartition Récurrent vs Non-récurrent",
                color_discrete_sequence=['#28a745', '#ffc107']
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.markdown("""
            **Justification:**
            - Les transactions récurrentes sont prévisibles (salaires, intérêts)
            - Les transactions non-récurrentes nécessitent une analyse spécifique
            - Cette classification améliore la précision du forecast
            """)
            st.metric("Récurrent", f"{recurring_count:,} ({recurring_count/len(bank)*100:.1f}%)")
            st.metric("Non-récurrent", f"{non_recurring_count:,} ({non_recurring_count/len(bank)*100:.1f}%)")
    
    # ========================================================================
    # SECTION 3: CALCULS DÉTAILLÉS
    # ========================================================================
    elif section == "🔢 Calculs Détailés":
        st.markdown('<div class="section-header">🔢 Calculs Détailés avec Justifications</div>', unsafe_allow_html=True)
        
        variable = st.selectbox(
            "Choisir une variable à analyser:",
            [
                "DSO (Days Sales Outstanding)",
                "DPO (Days Payable Outstanding)",
                "Inflation",
                "Volatilité des Volumes",
                "Solde Initial",
                "Forecast Quotidien"
            ]
        )
        
        if variable == "DSO (Days Sales Outstanding)":
            st.markdown("### 📊 Calcul du DSO")
            
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis données historiques réelles<br>
            📊 <strong>Source :</strong> Factures clients avec status='Paid' dans sales_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Élevée (basée sur transactions réelles payées)
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DSO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Filtrer les factures payées
sales_paid = sales[sales['status'] == 'Paid'].copy()

# Calculer days_to_pay pour les factures avec dates valides
sales_paid['has_valid_dates'] = (
    sales_paid['payment_date'].notna() & 
    sales_paid['issue_date'].notna()
)

sales_paid.loc[sales_paid['has_valid_dates'], 'days_to_pay'] = (
    sales_paid.loc[sales_paid['has_valid_dates'], 'payment_date'] - 
    sales_paid.loc[sales_paid['has_valid_dates'], 'issue_date']
).dt.days

# Calculer la moyenne
sales_paid_valid = sales_paid[sales_paid['has_valid_dates']].copy()
dso_mean = sales_paid_valid['days_to_pay'].mean()
            """, language='python')
            
            st.markdown("**Valeur calculée:**")
            st.metric("DSO Moyen", f"{dso_mean:.1f} jours")
            
            sales_paid_valid_count = len(metrics.get('sales_paid_valid', pd.DataFrame()))
            st.info(f"✅ Calculé depuis **{sales_paid_valid_count}** factures payées avec dates valides")
        
        elif variable == "DPO (Days Payable Outstanding)":
            st.markdown("### 📊 Calcul du DPO")
            
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis données historiques réelles<br>
            📊 <strong>Source :</strong> Factures fournisseurs avec status='Paid' dans purchase_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Élevée (basée sur transactions réelles payées)
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DPO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Filtrer les factures payées
purchase_paid = purchase[purchase['status'] == 'Paid'].copy()

# Calculer days_to_pay pour les factures avec dates valides
purchase_paid['has_valid_dates'] = (
    purchase_paid['payment_date'].notna() & 
    purchase_paid['issue_date'].notna()
)

purchase_paid.loc[purchase_paid['has_valid_dates'], 'days_to_pay'] = (
    purchase_paid.loc[purchase_paid['has_valid_dates'], 'payment_date'] - 
    purchase_paid.loc[purchase_paid['has_valid_dates'], 'issue_date']
).dt.days

# Calculer la moyenne
purchase_paid_valid = purchase_paid[purchase_paid['has_valid_dates']].copy()
dpo_mean = purchase_paid_valid['days_to_pay'].mean()
            """, language='python')
            
            st.markdown("**Valeur calculée:**")
            st.metric("DPO Moyen", f"{dpo_mean:.1f} jours")
            
            purchase_paid_valid_count = len(metrics.get('purchase_paid_valid', pd.DataFrame()))
            st.info(f"✅ Calculé depuis **{purchase_paid_valid_count}** factures payées avec dates valides")
        
        elif variable == "Solde Initial":
            st.markdown("### 💰 Calcul du Solde Initial")
            
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis transactions bancaires historiques<br>
            📊 <strong>Source :</strong> Toutes les transactions dans bank_transactions.csv<br>
            💱 <strong>Multi-devises :</strong> Calculé séparément par devise (EUR, USD, JPY) puis converti en EUR
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Méthode de calcul:**")
            st.markdown("""
            Solde Initial = Σ (toutes les transactions jusqu'à la date de début)
            
            Par devise:
            - EUR: Somme directe
            - USD: Somme × taux USD/EUR
            - JPY: Somme × taux JPY/EUR
            
            Total = EUR + USD_converti + JPY_converti
            """)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Calculer le solde initial par devise
            if 'currency' in bank.columns and 'amount_eur' in bank.columns:
                balance_eur = bank[bank['currency'] == 'EUR']['amount_eur'].sum() if len(bank[bank['currency'] == 'EUR']) > 0 else 0
                balance_usd = bank[bank['currency'] == 'USD']['amount_eur'].sum() if len(bank[bank['currency'] == 'USD']) > 0 else 0
                balance_jpy = bank[bank['currency'] == 'JPY']['amount_eur'].sum() if len(bank[bank['currency'] == 'JPY']) > 0 else 0
                total_balance = balance_eur + balance_usd + balance_jpy
            else:
                total_balance = bank['amount_eur'].sum() if 'amount_eur' in bank.columns else 0
            
            st.markdown("**Valeur calculée:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("EUR", f"{balance_eur:,.2f} EUR" if 'balance_eur' in locals() else "N/A")
            with col2:
                st.metric("USD", f"{balance_usd:,.2f} EUR" if 'balance_usd' in locals() else "N/A")
            with col3:
                st.metric("JPY", f"{balance_jpy:,.2f} EUR" if 'balance_jpy' in locals() else "N/A")
            with col4:
                st.metric("Total", f"{total_balance:,.2f} EUR")
            
            st.info(f"✅ Calculé depuis **{len(bank)}** transactions bancaires historiques")
    
    # ========================================================================
    # SECTION 4: VISUALISATIONS
    # ========================================================================
    elif section == "📈 Visualisations":
        st.markdown('<div class="section-header">📈 Visualisations Interactives</div>', unsafe_allow_html=True)
        
        # Graphique 1: Évolution temporelle
        st.markdown("### 📅 Évolution Temporelle des Flux")
        bank_daily = bank.groupby('date').agg({
            'amount_eur': lambda x: bank.loc[x.index[bank.loc[x.index, 'type']=='credit'], 'amount_eur'].sum() - 
                                bank.loc[x.index[bank.loc[x.index, 'type']=='debit'], 'amount_eur'].sum()
        }).reset_index()
        bank_daily.columns = ['date', 'net_cash_flow']
        
        fig = px.line(
            bank_daily,
            x='date',
            y='net_cash_flow',
            title="Cash Flow Net Quotidien (Historique)",
            labels={'net_cash_flow': 'Cash Flow Net (EUR)', 'date': 'Date'}
        )
        fig.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
        
        # Graphique 2: Pattern hebdomadaire
        st.markdown("### 📆 Pattern Hebdomadaire")
        bank['day_of_week'] = bank['date'].dt.day_name()
        weekly_pattern = bank.groupby(['day_of_week', 'type'])['amount_eur'].sum().unstack(fill_value=0)
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekly_pattern = weekly_pattern.reindex(day_order, fill_value=0)
        
        fig = go.Figure()
        if 'credit' in weekly_pattern.columns:
            fig.add_trace(go.Bar(x=weekly_pattern.index, y=weekly_pattern['credit'], name='Encaissements', marker_color='green'))
        if 'debit' in weekly_pattern.columns:
            fig.add_trace(go.Bar(x=weekly_pattern.index, y=weekly_pattern['debit'], name='Décaissements', marker_color='red'))
        
        fig.update_layout(
            title="Pattern Hebdomadaire des Flux",
            xaxis_title="Jour de la semaine",
            yaxis_title="Montant (EUR)",
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Graphique 3: Distribution par catégorie
        st.markdown("### 📊 Distribution par Catégorie")
        category_flows = bank.groupby('category')['amount_eur'].sum().sort_values(ascending=False)
        fig = px.bar(
            x=category_flows.index,
            y=category_flows.values,
            title="Flux par Catégorie",
            labels={'x': 'Catégorie', 'y': 'Montant Total (EUR)'}
        )
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    
    # ========================================================================
    # SECTION 5: PARAMÈTRES & FACTEURS
    # ========================================================================
    elif section == "⚙️ Paramètres & Facteurs":
        st.markdown('<div class="section-header">⚙️ Paramètres & Facteurs d\'Impact</div>', unsafe_allow_html=True)
        
        st.markdown("### 📋 Tous les Facteurs d'Impact Calculés")
        
        # Les variables sont déjà calculées au début (avg_daily_credit, etc.)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 💱 Taux de Change")
            
            # Nature des valeurs pour taux de change
            usd_rate = fx_rates.get('USD', 0.92)
            jpy_rate = fx_rates.get('JPY', 0.0065)
            
            # Détecter si c'est une valeur réelle ou fallback
            rate_source = "API (temps réel)" if usd_rate != 0.92 or jpy_rate != 0.0065 else "Fallback (moyenne 2024)"
            rate_color = "🟢" if rate_source.startswith("API") else "🟡"
            
            st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em; color: #004085;">
            {rate_color} <strong>Source :</strong> {rate_source}<br>
            📊 <strong>Nature :</strong> {'Taux réel (API)' if rate_source.startswith('API') else 'Valeur par défaut (moyenne 2024)'}
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("USD/EUR", f"{usd_rate:.4f}", 
                     help="Taux réel via API exchangerate-api.com, ou fallback 0.92 (moyenne 2024)")
            st.metric("JPY/EUR", f"{jpy_rate:.6f}", 
                     help="Taux réel via API exchangerate-api.com, ou fallback 0.0065 (moyenne 2024)")
            
            st.markdown("**Volatilité FX (estimée):**")
            st.markdown("""
            <div style="background-color: #fff3e0; padding: 10px; border-radius: 5px; font-size: 0.9em; color: #856404;">
            ⚠️ <strong>ESTIMÉE</strong> : Volatilité historique typique (pas calculée)<br>
            📊 <strong>Source :</strong> Observations historiques moyennes 2024<br>
            💱 USD : ±5% (volatilité typique EUR/USD)<br>
            💱 JPY : ±8% (volatilité typique EUR/JPY, plus volatile)
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Volatilité USD", "±5%", help="Estimation : volatilité historique typique EUR/USD")
            st.metric("Volatilité JPY", "±8%", help="Estimation : volatilité historique typique EUR/JPY")
            
            st.markdown("#### 📈 Inflation")
            
            # Détecter si inflation calculée ou par défaut
            inflation_source = "Calculée (données historiques)" if len(bank_recurring) > 0 and len(monthly_recurring) >= 6 else "Par défaut (2% zone euro)"
            inflation_color = "🟢" if inflation_source.startswith("Calculée") else "🟡"
            
            st.markdown(f"""
            <div style="background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em; color: #155724;">
            {inflation_color} <strong>Source :</strong> {inflation_source}<br>
            📊 <strong>Nature :</strong> {'Valeur calculée' if inflation_source.startswith('Calculée') else 'Valeur par défaut (moyenne zone euro 2024)'}
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Taux Annuel", f"{inflation_rate*100:.2f}%", 
                     help="Calculé depuis évolution coûts récurrents, ou 2% par défaut (moyenne zone euro)")
            st.metric("Impact 90 jours", f"{inflation_rate*90/365*100:.2f}%", 
                     help="Ajustement progressif sur 90 jours (inflation annuelle × 90/365)")
        
        with col2:
            st.markdown("#### ⏱️ Retards de Paiement")
            
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em; color: #155724;">
            ✅ <strong>CALCULÉES</strong> : Statistiques descriptives depuis données réelles<br>
            📊 <strong>Source :</strong> Factures avec status='Overdue' dans fichiers CSV
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Taux retard clients", f"{overdue_rate_sales*100:.1f}%", 
                     help="Calculé : (factures Overdue) / (total factures clients)")
            st.metric("Taux retard fournisseurs", f"{overdue_rate_purchase*100:.1f}%", 
                     help="Calculé : (factures Overdue) / (total factures fournisseurs)")
            
            st.markdown("**Variations (écart-type):**")
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em; color: #155724;">
            ✅ <strong>CALCULÉES</strong> : Écart-type des délais de paiement<br>
            📊 <strong>Source :</strong> Calcul statistique sur factures payées
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Variation DSO", f"±{dso_std:.1f} jours", 
                     help="Écart-type du DSO : dispersion des délais de recouvrement clients")
            st.metric("Variation DPO", f"±{dpo_std:.1f} jours", 
                     help="Écart-type du DPO : dispersion des délais de paiement fournisseurs")
            
            st.markdown("#### 📊 Volatilité des Volumes")
            
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 10px; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em; color: #155724;">
            ✅ <strong>CALCULÉES</strong> : Coefficient de variation (écart-type / moyenne)<br>
            📊 <strong>Source :</strong> Toutes les transactions bancaires historiques
            </div>
            """, unsafe_allow_html=True)
            
            st.metric("Encaissements", f"±{volume_volatility_credit*100:.1f}%", 
                     help="Coefficient de variation : écart-type relatif des encaissements quotidiens")
            st.metric("Décaissements", f"±{volume_volatility_debit*100:.1f}%", 
                     help="Coefficient de variation : écart-type relatif des décaissements quotidiens")
            
            st.markdown("#### 📊 Statistiques Quotidiennes")
            st.metric("Moyenne Encaissements", f"{avg_daily_credit:,.2f} EUR")
            st.metric("Moyenne Décaissements", f"{avg_daily_debit:,.2f} EUR")
            st.metric("Écart-type Encaissements", f"{std_daily_credit:,.2f} EUR")
            st.metric("Écart-type Décaissements", f"{std_daily_debit:,.2f} EUR")
    
    # ========================================================================
    # SECTION 6: LANCER FORECAST
    # ========================================================================
    elif section == "🎯 Lancer Forecast":
        st.markdown('<div class="section-header">🎯 Lancer le Forecast</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 📅 Forecast des 3 Premiers Mois de 2025
        
        Ce forecast utilise les données historiques pour projeter les flux de trésorerie
        de **janvier, février et mars 2025** (jusqu'au 31 mars 2025 maximum).
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "📅 Date de début du forecast:",
                value=datetime(2025, 1, 1).date(),
                min_value=datetime(2025, 1, 1).date(),
                max_value=MAX_FORECAST_DATE
            )
        with col2:
            end_date = st.date_input(
                "📅 Date de fin du forecast:",
                value=MAX_FORECAST_DATE,
                min_value=start_date,
                max_value=MAX_FORECAST_DATE
            )
            forecast_days = (end_date - start_date).days + 1
            st.info(f"**Durée:** {forecast_days} jours")
        
        # Initialiser session_state
        if 'forecast_results' not in st.session_state:
            st.session_state.forecast_results = None
        
        if st.button("🚀 Lancer le Forecast", type="primary", use_container_width=True):
            with st.spinner("⏳ Calcul du forecast en cours..."):
                try:
                    # Utiliser les variables déjà calculées au début
                    # (avg_daily_credit, avg_daily_debit, etc. sont déjà définies)
                    
                    # Exécuter le forecast
                    forecast_results = run_forecast(
                        bank, sales, purchase, start_date, fx_rates,
                        dso_mean, dpo_mean,
                        avg_daily_credit, avg_daily_debit,
                        std_daily_credit, std_daily_debit,
                        weekly_credit_pattern, weekly_debit_pattern,
                        inflation_rate, volume_volatility_credit, volume_volatility_debit,
                        end_date
                    )
                    
                    st.session_state.forecast_results = forecast_results
                    st.success(f"✅ Forecast calculé pour {forecast_results['forecast_days_count']} jours!")
                
                except Exception as e:
                    st.error(f"❌ Erreur lors du forecast: {e}")
                    import traceback
                    with st.expander("🔍 Détails"):
                        st.code(traceback.format_exc())
        
        # Afficher les résultats
        if st.session_state.forecast_results is not None:
            results = st.session_state.forecast_results
            
            st.markdown("### 📊 Résumé du Forecast")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Solde Initial", f"{results['initial_balance']:,.2f} EUR")
            with col2:
                st.metric("Solde Final", f"{results['final_balance']:,.2f} EUR")
            with col3:
                variation = results['final_balance'] - results['initial_balance']
                st.metric("Variation", f"{variation:+,.2f} EUR")
            with col4:
                st.metric("Jours Critiques", len(results['negative_days']))
            
            # Graphique du forecast
            if len(results['forecast_df']) > 0:
                st.markdown("### 📈 Évolution du Forecast")
                fig = px.line(
                    results['forecast_df'],
                    x='Date',
                    y='Cumul_Total_EUR',
                    title="Évolution du Solde (Forecast)",
                    labels={'Cumul_Total_EUR': 'Solde Cumulé (EUR)', 'Date': 'Date'}
                )
                fig.add_hline(y=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig, use_container_width=True)
                
                # Tableau des résultats
                st.markdown("### 📋 Détails Quotidiens")
                st.dataframe(results['forecast_df'], use_container_width=True)
    
    # ========================================================================
    # SECTION 7: SCÉNARIOS & RISQUES
    # ========================================================================
    elif section == "📊 Scénarios & Risques":
        st.markdown('<div class="section-header">📊 Scénarios & Analyse des Risques</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 📋 Conformité avec les Exigences du Projet
        
        Cette section implémente les analyses de risques et scénarios demandés dans le projet :
        - **Dette €20M** à taux variable (Euribor 3M + 1.2%)
        - **Scénarios** : Base, Optimiste, Pessimiste
        - **Risque de taux d'intérêt** : Simulation de chocs ±100bp
        - **Risque FX** : Simulation de variations ±5%
        - **Recommandations** : Placements et financements optimisés
        """)
        
        # ========================================================================
        # DETTE €20M - CALCUL EXPLICITE
        # ========================================================================
        st.markdown("### 💰 Dette Identifiée (selon spécifications)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Principal", f"{DEBT_PRINCIPAL:,.0f} EUR", help="Dette totale selon spécifications")
        with col2:
            st.metric("Taux Variable", f"{DEBT_INTEREST_RATE*100:.2f}%", 
                     help=f"Euribor 3M ({EURIBOR_3M_BASE*100:.2f}%) + Spread ({DEBT_SPREAD*100:.2f}%)")
        with col3:
            st.metric("Intérêts Mensuels", f"{DEBT_MONTHLY_INTEREST:,.2f} EUR",
                     help=f"Calcul: {DEBT_PRINCIPAL:,.0f} × {DEBT_INTEREST_RATE*100:.2f}% / 12")
        
        st.info("""
        **📌 Calcul des Intérêts:**
        - Principal : €20,000,000
        - Taux : Euribor 3M (3.5% estimé) + Spread (1.2%) = **4.7% annuel**
        - Intérêts mensuels : €20,000,000 × 4.7% / 12 = **€78,333.33/mois**
        
        ⚠️ **Note:** Le taux Euribor 3M est estimé à 3.5% pour début 2025. 
        En production, il faudrait récupérer le taux réel via une API financière.
        """)
        
        # ========================================================================
        # SCÉNARIOS : BASE, OPTIMISTE, PESSIMISTE
        # ========================================================================
        st.markdown("### 📊 Scénarios de Forecast")
        
        scenario_tab1, scenario_tab2, scenario_tab3 = st.tabs(["📈 Base", "⬆️ Optimiste", "⬇️ Pessimiste"])
        
        with scenario_tab1:
            st.markdown("#### 📈 Scénario Base")
            st.info("""
            **Hypothèses:**
            - Taux d'intérêt : Euribor 3M + 1.2% (4.7%)
            - Taux de change : Taux actuels (USD/EUR, JPY/EUR)
            - Volumes : Moyennes historiques
            - Inflation : Taux calculé depuis données historiques
            - DSO/DPO : Moyennes historiques
            """)
            if 'forecast_results' in st.session_state and st.session_state.forecast_results is not None:
                st.success("✅ Ce scénario correspond au forecast standard lancé dans la section '🎯 Lancer Forecast'")
            else:
                st.warning("⚠️ Lancez d'abord un forecast dans la section '🎯 Lancer Forecast' pour voir les résultats")
        
        with scenario_tab2:
            st.markdown("#### ⬆️ Scénario Optimiste")
            st.info("""
            **Hypothèses:**
            - Taux d'intérêt : **-100bp** (Euribor 3M baisse de 1%)
            - Taux de change : **+5%** pour USD et JPY (devises étrangères se renforcent)
            - Volumes : **+10%** par rapport à la moyenne
            - Inflation : **-0.5%** par rapport au scénario base
            - DSO : **-5 jours** (recouvrement plus rapide)
            - DPO : **+5 jours** (paiements fournisseurs plus tardifs)
            - Taux d'impayés : **-50%** par rapport au scénario base
            """)
            new_rate_opt = max(0, EURIBOR_3M_BASE - 0.01) + DEBT_SPREAD
            new_interest_opt = DEBT_PRINCIPAL * (new_rate_opt / 12)
            st.warning(f"⚠️ **Impact sur intérêts:** Intérêts mensuels réduits à ~€{new_interest_opt:,.0f}/mois (au lieu de €{DEBT_MONTHLY_INTEREST:,.0f})")
            st.warning("⚠️ **Impact FX:** Encaissements USD/JPY augmentent de 5% en EUR")
        
        with scenario_tab3:
            st.markdown("#### ⬇️ Scénario Pessimiste")
            st.info("""
            **Hypothèses:**
            - Taux d'intérêt : **+100bp** (Euribor 3M hausse de 1%)
            - Taux de change : **-5%** pour USD et JPY (devises étrangères se déprécient)
            - Volumes : **-10%** par rapport à la moyenne
            - Inflation : **+0.5%** par rapport au scénario base
            - DSO : **+5 jours** (recouvrement plus lent)
            - DPO : **-5 jours** (paiements fournisseurs plus précoces)
            - Taux d'impayés : **+50%** par rapport au scénario base
            """)
            new_rate_pess = EURIBOR_3M_BASE + 0.01 + DEBT_SPREAD
            new_interest_pess = DEBT_PRINCIPAL * (new_rate_pess / 12)
            st.error(f"🚨 **Impact sur intérêts:** Intérêts mensuels augmentés à ~€{new_interest_pess:,.0f}/mois (au lieu de €{DEBT_MONTHLY_INTEREST:,.0f})")
            st.error("🚨 **Impact FX:** Encaissements USD/JPY diminuent de 5% en EUR")
        
        # ========================================================================
        # SIMULATION CHOCS DE TAUX D'INTÉRÊT (±100bp)
        # ========================================================================
        st.markdown("### 📈 Simulation Chocs de Taux d'Intérêt (±100bp)")
        
        st.markdown("""
        Selon les spécifications, il faut simuler l'impact de variations de ±100bp (1%) sur le taux Euribor 3M.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ⬆️ Choc +100bp (Hausse)")
            new_rate_up = EURIBOR_3M_BASE + 0.01 + DEBT_SPREAD  # +100bp
            new_interest_up = DEBT_PRINCIPAL * (new_rate_up / 12)
            impact_up = new_interest_up - DEBT_MONTHLY_INTEREST
            
            st.metric("Nouveau Taux", f"{new_rate_up*100:.2f}%", 
                     delta=f"+1.00%", delta_color="inverse")
            st.metric("Nouveaux Intérêts Mensuels", f"{new_interest_up:,.2f} EUR",
                     delta=f"+{impact_up:,.2f} EUR/mois", delta_color="inverse")
            st.metric("Impact Annuel", f"{impact_up*12:,.2f} EUR/an",
                     help="Impact supplémentaire sur les charges d'intérêts")
        
        with col2:
            st.markdown("#### ⬇️ Choc -100bp (Baisse)")
            new_rate_down = max(0, EURIBOR_3M_BASE - 0.01) + DEBT_SPREAD  # -100bp
            new_interest_down = DEBT_PRINCIPAL * (new_rate_down / 12)
            impact_down = DEBT_MONTHLY_INTEREST - new_interest_down
            
            st.metric("Nouveau Taux", f"{new_rate_down*100:.2f}%",
                     delta=f"-1.00%", delta_color="normal")
            st.metric("Nouveaux Intérêts Mensuels", f"{new_interest_down:,.2f} EUR",
                     delta=f"-{impact_down:,.2f} EUR/mois", delta_color="normal")
            st.metric("Économie Annuelle", f"{impact_down*12:,.2f} EUR/an",
                     help="Économie sur les charges d'intérêts")
        
        st.markdown("""
        **💡 Recommandations de Couverture (Hedging):**
        - **Swap de taux d'intérêt (IRS)** : Fixer le taux pour protéger contre les hausses
        - **Cap (plafond)** : Limiter l'exposition à la hausse tout en bénéficiant des baisses
        - **Refinancement** : Négocier un taux fixe si les taux sont bas
        """)
        
        # ========================================================================
        # SIMULATION VARIATIONS FX (±5%)
        # ========================================================================
        st.markdown("### 💱 Simulation Variations FX (±5%)")
        
        usd_rate_current = fx_rates.get('USD', 0.92)
        jpy_rate_current = fx_rates.get('JPY', 0.0065)
        
        # Calculer l'exposition FX depuis les données
        bank_usd = bank[bank['currency'] == 'USD']
        bank_jpy = bank[bank['currency'] == 'JPY']
        exposure_usd_amount = bank_usd['amount'].sum() if len(bank_usd) > 0 else 0
        exposure_jpy_amount = bank_jpy['amount'].sum() if len(bank_jpy) > 0 else 0
        
        st.markdown("#### 📊 Exposition FX Actuelle")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Exposition USD", f"{exposure_usd_amount:,.2f} USD",
                     help="Montant total en USD dans les transactions")
            st.metric("Valeur EUR Actuelle", f"{exposure_usd_amount * usd_rate_current:,.2f} EUR")
        with col2:
            st.metric("Exposition JPY", f"{exposure_jpy_amount:,.2f} JPY",
                     help="Montant total en JPY dans les transactions")
            st.metric("Valeur EUR Actuelle", f"{exposure_jpy_amount * jpy_rate_current:,.2f} EUR")
        
        st.markdown("#### 📈 Impact des Variations ±5%")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### ⬆️ Variation +5% (Devises se renforcent)")
            usd_rate_up = usd_rate_current * 1.05
            jpy_rate_up = jpy_rate_current * 1.05
            impact_usd_up = exposure_usd_amount * (usd_rate_up - usd_rate_current)
            impact_jpy_up = exposure_jpy_amount * (jpy_rate_up - jpy_rate_current)
            
            st.metric("USD/EUR", f"{usd_rate_up:.4f}", delta="+5%", delta_color="normal")
            st.metric("Impact USD", f"+{impact_usd_up:,.2f} EUR",
                     help="Gain sur encaissements USD")
            st.metric("JPY/EUR", f"{jpy_rate_up:.6f}", delta="+5%", delta_color="normal")
            st.metric("Impact JPY", f"+{impact_jpy_up:,.2f} EUR",
                     help="Gain sur encaissements JPY")
            st.success(f"✅ **Gain Total:** +{impact_usd_up + impact_jpy_up:,.2f} EUR")
        
        with col2:
            st.markdown("##### ⬇️ Variation -5% (Devises se déprécient)")
            usd_rate_down = usd_rate_current * 0.95
            jpy_rate_down = jpy_rate_current * 0.95
            impact_usd_down = exposure_usd_amount * (usd_rate_down - usd_rate_current)
            impact_jpy_down = exposure_jpy_amount * (jpy_rate_down - jpy_rate_current)
            
            st.metric("USD/EUR", f"{usd_rate_down:.4f}", delta="-5%", delta_color="inverse")
            st.metric("Impact USD", f"{impact_usd_down:,.2f} EUR",
                     help="Perte sur encaissements USD")
            st.metric("JPY/EUR", f"{jpy_rate_down:.6f}", delta="-5%", delta_color="inverse")
            st.metric("Impact JPY", f"{impact_jpy_down:,.2f} EUR",
                     help="Perte sur encaissements JPY")
            st.error(f"🚨 **Perte Total:** {impact_usd_down + impact_jpy_down:,.2f} EUR")
        
        st.markdown("""
        **💡 Recommandations de Couverture FX:**
        - **Forwards FX** : Verrouiller les taux pour les encaissements futurs
        - **Netting** : Compenser les positions longues et courtes par devise
        - **Options FX** : Protéger contre les pertes tout en bénéficiant des gains
        - **Natural Hedging** : Aligner les encaissements et décaissements par devise
        """)
        
        # ========================================================================
        # ANALYSE DES RISQUES DU FORECAST (si disponible)
        # ========================================================================
        if 'forecast_results' in st.session_state and st.session_state.forecast_results is not None:
            results = st.session_state.forecast_results
            
            st.markdown("### 🎯 Analyse des Risques du Forecast Actuel")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Safe", results['risk_zones']['Safe'], delta="jours")
            with col2:
                st.metric("Warning", results['risk_zones']['Warning'], delta="jours")
            with col3:
                st.metric("Critical", results['risk_zones']['Critical'], delta="jours")
            
            if len(results['negative_days']) > 0:
                st.warning(f"⚠️ {len(results['negative_days'])} jours avec solde négatif détectés")
                st.markdown("**Dates critiques:**")
                for day in results['negative_days'][:10]:  # Afficher les 10 premiers
                    st.write(f"- {day.strftime('%Y-%m-%d')}")
            
            # Graphique des zones de risque
            if len(results['forecast_df']) > 0:
                st.markdown("### 📊 Zones de Risque")
                df = results['forecast_df'].copy()
                df['Risk_Color'] = df['Risk_Level_Net'].map({
                    'Safe': 'green',
                    'Warning': 'orange',
                    'Critical': 'red'
                })
                
                fig = go.Figure()
                for risk_level in ['Safe', 'Warning', 'Critical']:
                    risk_data = df[df['Risk_Level_Net'] == risk_level]
                    if len(risk_data) > 0:
                        fig.add_trace(go.Scatter(
                            x=risk_data['Date'],
                            y=risk_data['Cumul_Net_EUR'],
                            mode='markers',
                            name=risk_level,
                            marker=dict(
                                color=risk_data['Risk_Color'],
                                size=8
                            )
                        ))
                
                fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Solde zéro")
                fig.update_layout(
                    title="Zones de Risque du Forecast",
                    xaxis_title="Date",
                    yaxis_title="Solde Cumulé (EUR)",
                    hovermode='closest'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                fig.update_layout(
                    title="Zones de Risque (Solde Net)",
                    xaxis_title="Date",
                    yaxis_title="Solde Net (EUR)",
                    hovermode='closest'
                )
                fig.add_hline(y=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
