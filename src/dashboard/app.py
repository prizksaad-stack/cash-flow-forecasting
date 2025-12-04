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
from src.config import get_config, MAX_FORECAST_DATE, DEBT_PRINCIPAL
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
        
        # Variables pour le dashboard
        dso_mean = metrics['dso_mean']
        dpo_mean = metrics['dpo_mean']
        bank = metrics['bank']  # Bank avec amount_eur
        
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
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DSO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Valeur calculée:**")
            st.metric("DSO Moyen", f"{dso_mean:.1f} jours")
            st.info(f"Calculé depuis {len(metrics.get('sales_paid_valid', pd.DataFrame()))} factures payées avec dates valides")
        
        elif variable == "DPO (Days Payable Outstanding)":
            st.markdown("### 📊 Calcul du DPO")
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DPO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Valeur calculée:**")
            st.metric("DPO Moyen", f"{dpo_mean:.1f} jours")
            st.info(f"Calculé depuis {len(metrics.get('purchase_paid_valid', pd.DataFrame()))} factures payées avec dates valides")
        
        elif variable == "Solde Initial":
            st.markdown("### 💰 Calcul du Solde Initial")
            st.markdown("""
            Le solde initial est la somme de toutes les transactions jusqu'à la date de début du forecast.
            Calculé séparément par devise puis converti en EUR équivalent.
            """)
            # Calculer le solde initial (simplifié)
            initial_balance = bank['amount_eur'].sum()
            st.metric("Solde Initial Total", f"{initial_balance:,.2f} EUR")
    
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
        
        # Calculer les facteurs
        avg_daily_credit = metrics['avg_daily_credit']
        avg_daily_debit = metrics['avg_daily_debit']
        std_daily_credit = metrics['std_daily_credit']
        std_daily_debit = metrics['std_daily_debit']
        volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
        volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 💱 Taux de Change")
            usd_rate = fx_rates.get('USD', 0.92)
            jpy_rate = fx_rates.get('JPY', 0.0065)
            st.metric("USD/EUR", f"{usd_rate:.4f}")
            st.metric("JPY/EUR", f"{jpy_rate:.6f}")
            
            st.markdown("#### 📈 Inflation")
            inflation_rate = 0.02  # Par défaut
            st.metric("Taux Annuel", f"{inflation_rate*100:.2f}%")
            st.metric("Impact 90 jours", f"{inflation_rate*90/365*100:.2f}%")
        
        with col2:
            st.markdown("#### 📊 Volatilité des Volumes")
            st.metric("Encaissements", f"±{volume_volatility_credit*100:.1f}%")
            st.metric("Décaissements", f"±{volume_volatility_debit*100:.1f}%")
            
            st.markdown("#### 📊 Statistiques Quotidiennes")
            st.metric("Moyenne Encaissements", f"{avg_daily_credit:,.2f} EUR")
            st.metric("Moyenne Décaissements", f"{avg_daily_debit:,.2f} EUR")
    
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
                    # Calculer tous les paramètres
                    weekly_credit_pattern = metrics['weekly_credit_pattern']
                    weekly_debit_pattern = metrics['weekly_debit_pattern']
                    inflation_rate = 0.02
                    
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
        
        if 'forecast_results' not in st.session_state or st.session_state.forecast_results is None:
            st.warning("⚠️ Lancez d'abord un forecast dans la section '🎯 Lancer Forecast'")
        else:
            results = st.session_state.forecast_results
            
            st.markdown("### 🎯 Analyse des Risques")
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
