"""
Cash Forecasting Analysis - Script Complet avec Dashboard
Analyse complète selon le brief : nettoyage, classification, saisonnalité, forecast quotidien, détection de risques
+ Dashboard interactif professionnel

Usage:
    - Mode Dashboard (par défaut): python cash_forecast_complete.py
    - Mode Script: python cash_forecast_complete.py --script
    - Mode Dashboard manuel: streamlit run cash_forecast_complete.py
"""
import sys
import os
import subprocess
import webbrowser
from pathlib import Path

# Imports communs
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import warnings
import requests
import json

# Vérifier d'abord si on est en mode script
SCRIPT_MODE = "--script" in sys.argv

# Détecter si on est lancé via streamlit run (AVANT d'importer streamlit)
# Si streamlit est déjà dans sys.modules, c'est que streamlit run l'a importé
IS_STREAMLIT_RUN = "streamlit" in sys.modules or os.environ.get("STREAMLIT_SERVER_PORT") is not None

# Détecter si on est dans Streamlit (seulement si lancé via streamlit run)
STREAMLIT_MODE = False
if IS_STREAMLIT_RUN and not SCRIPT_MODE:
    try:
        import streamlit as st
        STREAMLIT_MODE = True
    except ImportError:
        STREAMLIT_MODE = False

# Si on n'est pas dans Streamlit ET qu'on exécute directement le fichier
# ET qu'on n'est pas en mode script, lancer automatiquement Streamlit
if not STREAMLIT_MODE and not SCRIPT_MODE and __name__ == "__main__":
        # Mode Dashboard automatique
        script_path = Path(__file__).absolute()
        python_path = sys.executable
        
        print("="*70)
        print("🚀 LANCEMENT AUTOMATIQUE DU DASHBOARD")
        print("="*70)
        print(f"📊 Ouverture du dashboard interactif...")
        print(f"🌐 Le navigateur s'ouvrira automatiquement sur http://localhost:8501")
        print(f"\n💡 Pour lancer le mode script (forecast complet), utilisez:")
        print(f"   python {Path(__file__).name} --script")
        print(f"\n⏹️  Pour arrêter le dashboard, appuyez sur Ctrl+C dans ce terminal")
        print("="*70)
        print()
        
        # Lancer Streamlit
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

# Imports conditionnels pour le dashboard (seulement si vraiment en mode Streamlit)
# Ne pas importer si on exécute directement avec Python
if STREAMLIT_MODE and IS_STREAMLIT_RUN:
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        from plotly.subplots import make_subplots
    except ImportError:
        pass

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================
# Chemins absolus pour éviter les problèmes de répertoire de travail
script_path = Path(__file__).absolute()
root = script_path.parent.parent  # deliverables/ (chemin absolu)
data_dir = root  # deliverables/ (où sont les CSV)
output_dir = script_path.parent  # deliverables/Python/
bdd_dir = root / 'bdd'  # bdd/ dans deliverables/
MAX_FORECAST_DATE = datetime(2025, 3, 31).date()

# ============================================================================
# PARAMÈTRES CLIENT (selon spécifications)
# ============================================================================
# Dette selon spécifications : €20M à taux variable (Euribor 3M + 1.2%)
DEBT_PRINCIPAL = 20_000_000  # €20M
DEBT_SPREAD = 0.012  # 1.2% spread
# Euribor 3M actuel (estimation basée sur marché 2024) - à mettre à jour avec taux réel
EURIBOR_3M_BASE = 0.035  # 3.5% (estimation conservatrice pour début 2025)
DEBT_INTEREST_RATE = EURIBOR_3M_BASE + DEBT_SPREAD  # 3.5% + 1.2% = 4.7%

# Calcul des intérêts mensuels de la dette
# Intérêts mensuels = Principal × (Taux annuel / 12)
DEBT_MONTHLY_INTEREST = DEBT_PRINCIPAL * (DEBT_INTEREST_RATE / 12)

# ============================================================================
# FONCTIONS PARTAGÉES
# ============================================================================

def get_real_exchange_rates():
    """Récupère les taux de change réels via API"""
    fx_rates = {'EUR': 1.0}
    
    apis = [
        {
            'name': 'exchangerate-api',
            'url': 'https://api.exchangerate-api.com/v4/latest/EUR',
            'parser': lambda data: {
                'USD': 1.0 / data['rates'].get('USD', 1.08) if data['rates'].get('USD', 0) > 0 else 0.92,
                'JPY': 1.0 / data['rates'].get('JPY', 150.0) if data['rates'].get('JPY', 0) > 0 else 0.0065,
                'EUR': 1.0
            }
        }
    ]
    
    for api in apis:
        try:
            if not STREAMLIT_MODE:
                print(f"   🔄 Tentative de récupération des taux via {api['name']}...")
            response = requests.get(api['url'], timeout=5)
            response.raise_for_status()
            data = response.json()
            rates = api['parser'](data)
            
            if 'JPY' in rates and rates['JPY'] > 1:
                rates['JPY'] = 1.0 / rates['JPY']
            
            fx_rates.update(rates)
            if not STREAMLIT_MODE:
                print(f"   ✅ Taux récupérés avec succès via {api['name']}")
            return fx_rates
        except Exception as e:
            if not STREAMLIT_MODE:
                print(f"   ⚠️  Erreur avec {api['name']}: {str(e)[:50]}")
            continue
    
    if not STREAMLIT_MODE or not IS_STREAMLIT_RUN:
        print("   ⚠️  Utilisation de taux de secours (moyennes 2024)")
    return {
        'USD': 0.92,
        'JPY': 0.0065,
        'EUR': 1.0
    }

def convert_to_eur(amount, currency, fx_rates, date=None):
    """
    Convertit un montant en EUR selon la devise
    
    Args:
        amount: Montant à convertir
        currency: Devise source ('EUR', 'USD', 'JPY')
        fx_rates: Dictionnaire des taux de change { 'USD': 0.92, 'JPY': 0.0065, 'EUR': 1.0 }
        date: Date optionnelle (non utilisée actuellement, pour extension future)
    
    Returns:
        float: Montant converti en EUR
    """
    # Gestion des cas limites
    if amount is None or pd.isna(amount):
        return 0.0
    
    if currency == 'EUR' or currency is None:
        return float(amount)
    elif currency in fx_rates and fx_rates[currency] is not None:
        rate = fx_rates[currency]
        # Vérifier que le taux est valide (positif et raisonnable)
        if rate > 0 and rate < 1000:  # Protection contre valeurs aberrantes
            return float(amount * rate)
        else:
            # Taux invalide, utiliser valeur par défaut
            default_rates = {'USD': 0.92, 'JPY': 0.0065}
            return float(amount * default_rates.get(currency, 1.0))
    else:
        # Devise non reconnue, retourner tel quel (assumé EUR)
        return float(amount)

def run_forecast_complete(bank, sales, purchase, start_date, fx_rates, dso_mean, dpo_mean, 
                          avg_daily_credit, avg_daily_debit, std_daily_credit, std_daily_debit,
                          weekly_credit_pattern, weekly_debit_pattern, inflation_rate,
                          volume_volatility_credit, volume_volatility_debit, MAX_FORECAST_DATE):
    """
    Exécute le forecast complet pour les 3 premiers mois de 2025 (janvier, février, mars)
    
    Returns:
        dict: Contient forecast_daily_df, initial_balance, final_balance, analyses, etc.
    """
    # Calculer le nombre de jours jusqu'au 31 mars 2025 maximum
    days_until_limit = (MAX_FORECAST_DATE - start_date).days + 1
    forecast_days_count = min(90, days_until_limit)
    end_date = start_date + timedelta(days=forecast_days_count - 1)
    
    # Factures ouvertes avec dates de paiement prévues
    # IMPORTANT: Filtrer seulement les factures avec due_date valide
    # ET conserver la devise originale pour calculs multi-devises
    sales_open = sales[sales['status'].isin(['Open','Overdue'])].copy()
    # Vérifier que due_date existe et n'est pas null avant de calculer expected_payment
    sales_open_valid = sales_open[sales_open['due_date'].notna()].copy()
    if len(sales_open_valid) > 0:
        # Convertir dso_mean en entier avec gestion des cas limites
        dso_days = int(round(dso_mean)) if dso_mean is not None and not pd.isna(dso_mean) else 0
        sales_open_valid['expected_payment'] = sales_open_valid['due_date'] + pd.Timedelta(days=dso_days)
        sales_open_valid['payment_date'] = sales_open_valid['expected_payment'].dt.date
        # Conserver la devise originale ET calculer amount_eur pour le total
        sales_open_valid['amount_eur'] = sales_open_valid.apply(
            lambda x: convert_to_eur(x['amount'], x.get('currency', 'EUR'), fx_rates, x['payment_date']), axis=1
        )
        # S'assurer que la colonne currency existe
        if 'currency' not in sales_open_valid.columns:
            sales_open_valid['currency'] = 'EUR'
        sales_open = sales_open_valid
    else:
        # Si aucune facture valide, créer un DataFrame vide avec les colonnes nécessaires
        sales_open = pd.DataFrame(columns=['payment_date', 'amount_eur', 'currency', 'amount'])
    
    purchase_open = purchase[purchase['status'].isin(['Open','Overdue'])].copy()
    # Vérifier que due_date existe et n'est pas null avant de calculer expected_payment
    purchase_open_valid = purchase_open[purchase_open['due_date'].notna()].copy()
    if len(purchase_open_valid) > 0:
        # Convertir dpo_mean en entier avec gestion des cas limites
        dpo_days = int(round(dpo_mean)) if dpo_mean is not None and not pd.isna(dpo_mean) else 0
        purchase_open_valid['expected_payment'] = purchase_open_valid['due_date'] + pd.Timedelta(days=dpo_days)
        purchase_open_valid['payment_date'] = purchase_open_valid['expected_payment'].dt.date
        # Conserver la devise originale ET calculer amount_eur pour le total
        purchase_open_valid['amount_eur'] = purchase_open_valid.apply(
            lambda x: convert_to_eur(x['amount'], x.get('currency', 'EUR'), fx_rates, x['payment_date']), axis=1
        )
        # S'assurer que la colonne currency existe
        if 'currency' not in purchase_open_valid.columns:
            purchase_open_valid['currency'] = 'EUR'
        purchase_open = purchase_open_valid
    else:
        # Si aucune facture valide, créer un DataFrame vide avec les colonnes nécessaires
        purchase_open = pd.DataFrame(columns=['payment_date', 'amount_eur', 'currency', 'amount'])
    
    # Solde initial par devise
    # IMPORTANT: En cash flow forecasting, le solde initial = cash disponible (somme des transactions)
    # La dette de 20M EUR est un passif qui n'affecte pas directement le cash flow,
    # mais ses intérêts mensuels sont déduits dans les décaissements récurrents
    bank_until_start = bank[bank['date'].dt.date < start_date]
    
    # IMPORTANT: S'assurer que amount_eur existe (calculé si nécessaire)
    if 'amount_eur' not in bank_until_start.columns and len(bank_until_start) > 0:
        bank_until_start['amount_eur'] = bank_until_start.apply(
            lambda x: convert_to_eur(x.get('amount', 0), x.get('currency', 'EUR'), fx_rates, x.get('date')), 
            axis=1
        )
    
    # Définir les taux de change (utilisés dans toute la boucle)
    usd_rate = fx_rates.get('USD', 0.92) if fx_rates and 'USD' in fx_rates else 0.92
    jpy_rate = fx_rates.get('JPY', 0.0065) if fx_rates and 'JPY' in fx_rates else 0.0065
    
    if len(bank_until_start) > 0:
        # IMPORTANT: Utiliser amount_eur si disponible (déjà converti en EUR), sinon convertir depuis amount
        if 'amount_eur' in bank_until_start.columns:
            # Utiliser amount_eur qui est déjà converti en EUR pour le total
            initial_balance_eur = bank_until_start[(bank_until_start['currency'] == 'EUR')]['amount_eur'].sum() if len(bank_until_start[bank_until_start['currency'] == 'EUR']) > 0 else 0
            initial_balance_usd_eur = bank_until_start[(bank_until_start['currency'] == 'USD')]['amount_eur'].sum() if len(bank_until_start[bank_until_start['currency'] == 'USD']) > 0 else 0
            initial_balance_jpy_eur = bank_until_start[(bank_until_start['currency'] == 'JPY')]['amount_eur'].sum() if len(bank_until_start[bank_until_start['currency'] == 'JPY']) > 0 else 0
            initial_balance_total = initial_balance_eur + initial_balance_usd_eur + initial_balance_jpy_eur
            
            # Pour les cumuls par devise, on a besoin des montants originaux (pas convertis)
            initial_balance_usd = bank_until_start[bank_until_start['currency'] == 'USD']['amount'].sum() if len(bank_until_start[bank_until_start['currency'] == 'USD']) > 0 else 0
            initial_balance_jpy = bank_until_start[bank_until_start['currency'] == 'JPY']['amount'].sum() if len(bank_until_start[bank_until_start['currency'] == 'JPY']) > 0 else 0
        else:
            # Fallback : convertir depuis amount original
            initial_balance_eur = bank_until_start[bank_until_start['currency'] == 'EUR']['amount'].sum() if len(bank_until_start[bank_until_start['currency'] == 'EUR']) > 0 else 0
            initial_balance_usd = bank_until_start[bank_until_start['currency'] == 'USD']['amount'].sum() if len(bank_until_start[bank_until_start['currency'] == 'USD']) > 0 else 0
            initial_balance_jpy = bank_until_start[bank_until_start['currency'] == 'JPY']['amount'].sum() if len(bank_until_start[bank_until_start['currency'] == 'JPY']) > 0 else 0
            # Conversion en EUR
            initial_balance_total = initial_balance_eur + (initial_balance_usd * usd_rate) + (initial_balance_jpy * jpy_rate)
    else:
        initial_balance_eur = initial_balance_usd = initial_balance_jpy = initial_balance_total = 0
    
    # Calculer le solde net (cash - dette) pour information (pas utilisé dans le forecast)
    # Ceci est calculé pour information seulement, car en cash flow forecasting,
    # on travaille avec le cash disponible, pas le net worth
    initial_balance_net = initial_balance_total - DEBT_PRINCIPAL
    
    # Paiements récurrents (intérêts mensuels, salaires, frais bancaires)
    # IMPORTANT: Utiliser amount_eur qui est déjà converti en EUR
    bank_recurring = bank[bank['category'].isin(['Loan Interest', 'Payroll', 'Bank Fee'])].copy()
    if len(bank_recurring) > 0:
        monthly_recurring_sums = bank_recurring.groupby(bank_recurring['date'].dt.to_period('M'))['amount_eur'].sum()
        if len(monthly_recurring_sums) > 0:
            avg_monthly_recurring = monthly_recurring_sums.mean()
        else:
            avg_monthly_recurring = 0
    else:
        avg_monthly_recurring = 0
    
    # AJOUTER les intérêts de la dette €20M (selon spécifications) si pas déjà inclus dans les données
    # IMPORTANT: S'assurer que les intérêts de la dette €20M sont TOUJOURS inclus dans avg_monthly_recurring
    # Vérifier si les intérêts de la dette sont déjà dans les transactions
    loan_interest_in_data = bank_recurring[bank_recurring['category'] == 'Loan Interest']['amount_eur'].sum() if len(bank_recurring) > 0 and 'Loan Interest' in bank_recurring['category'].values else 0
    # Calculer le nombre de mois dans les données pour estimer les intérêts mensuels moyens
    if len(bank_recurring) > 0:
        num_months_data = len(bank_recurring['date'].dt.to_period('M').unique())
        avg_loan_interest_per_month = loan_interest_in_data / num_months_data if num_months_data > 0 else 0
    else:
        avg_loan_interest_per_month = 0
    
    # IMPORTANT: S'assurer que les intérêts de la dette €20M sont TOUJOURS inclus
    # Si les intérêts dans les données sont significativement inférieurs à DEBT_MONTHLY_INTEREST,
    # ajouter la différence pour refléter la dette de €20M selon les spécifications
    # On utilise un seuil de 50% pour éviter les doublons si les données contiennent déjà les intérêts
    if avg_loan_interest_per_month < DEBT_MONTHLY_INTEREST * 0.5:  # Si moins de 50% des intérêts attendus
        # Les intérêts de la dette €20M ne sont pas complètement reflétés dans les données
        # Ajouter la différence aux paiements récurrents mensuels
        interest_to_add = DEBT_MONTHLY_INTEREST - avg_loan_interest_per_month
        avg_monthly_recurring += interest_to_add
        # DEBUG: Afficher l'ajout des intérêts (seulement en mode console)
        if not STREAMLIT_MODE:
            print(f"   💰 Intérêts dette €20M: Ajout de {interest_to_add:,.2f} EUR/mois aux paiements récurrents")
    else:
        # Les intérêts sont déjà dans les données, mais on s'assure qu'ils sont au moins égaux à DEBT_MONTHLY_INTEREST
        if avg_loan_interest_per_month < DEBT_MONTHLY_INTEREST:
            # Ajouter la différence même si c'est > 50% pour garantir la cohérence
            interest_to_add = DEBT_MONTHLY_INTEREST - avg_loan_interest_per_month
            avg_monthly_recurring += interest_to_add
            if not STREAMLIT_MODE:
                print(f"   💰 Intérêts dette €20M: Ajout de {interest_to_add:,.2f} EUR/mois pour atteindre {DEBT_MONTHLY_INTEREST:,.2f} EUR/mois")
    
    # Vérification finale: s'assurer que avg_monthly_recurring inclut au minimum DEBT_MONTHLY_INTEREST
    # (en plus des salaires et frais bancaires)
    # Calculer les paiements récurrents SANS les intérêts de prêt pour vérifier
    other_recurring = bank_recurring[~bank_recurring['category'].isin(['Loan Interest'])] if len(bank_recurring) > 0 else pd.DataFrame()
    if len(other_recurring) > 0:
        other_monthly_sums = other_recurring.groupby(other_recurring['date'].dt.to_period('M'))['amount_eur'].sum()
        avg_other_recurring = other_monthly_sums.mean() if len(other_monthly_sums) > 0 else 0
    else:
        avg_other_recurring = 0
    
    # S'assurer que avg_monthly_recurring = avg_other_recurring + DEBT_MONTHLY_INTEREST
    # (salaires + frais bancaires + intérêts dette)
    expected_total_recurring = avg_other_recurring + DEBT_MONTHLY_INTEREST
    if avg_monthly_recurring < expected_total_recurring * 0.9:  # Tolérance de 10% pour les arrondis
        # Forcer avg_monthly_recurring à inclure au minimum les intérêts de la dette
        avg_monthly_recurring = max(avg_monthly_recurring, expected_total_recurring)
        if not STREAMLIT_MODE:
            print(f"   ⚠️  Ajustement final: avg_monthly_recurring = {avg_monthly_recurring:,.2f} EUR/mois (inclut intérêts dette: {DEBT_MONTHLY_INTEREST:,.2f} EUR/mois)")
    
    # Forecast quotidien
    forecast_days = []
    cumul_total = initial_balance_total
    # NOTE: cumul_eur, cumul_usd, cumul_jpy sont initialisés mais non mis à jour dans cette version
    # car le forecast est consolidé en EUR équivalent. Pour un suivi par devise, il faudrait
    # tracker les flux par devise séparément, ce qui nécessiterait une logique plus complexe.
    cumul_eur = initial_balance_eur
    cumul_usd = initial_balance_usd
    cumul_jpy = initial_balance_jpy
    
    negative_days = []
    risk_zones = {'Safe': 0, 'Warning': 0, 'Critical': 0}
    
    # Vérification : s'assurer qu'on a au moins un jour à forecast
    if forecast_days_count <= 0:
        # Cas limite : pas de jours à forecast
        forecast_daily_df = pd.DataFrame(columns=['Date', 'Jour', 'Mois', 'Encaissements', 'Décaissements', 'Cash_Flow_Net', 'Cumul_Total_EUR'])
        worst_day = pd.Series({'Date': start_date.strftime('%Y-%m-%d'), 'Cumul_Total_EUR': initial_balance_total})
        return {
            'forecast_df': forecast_daily_df,
            'start_date': start_date,
            'end_date': end_date,
            'forecast_days_count': 0,
            'initial_balance': initial_balance_total,
            'initial_balance_net': initial_balance_net,  # Solde net (cash - dette)
            'initial_balance_eur': initial_balance_eur,
            'initial_balance_usd': initial_balance_usd,
            'initial_balance_jpy': initial_balance_jpy,
            'final_balance': initial_balance_total,
            'final_balance_net': initial_balance_net,  # Solde net final (cash - dette, pas de changement si forecast vide)
            'negative_days': [],
            'risk_zones': {'Safe': 0, 'Warning': 0, 'Critical': 0},
            'worst_day': worst_day,
            'sales_open': sales_open,
            'purchase_open': purchase_open
        }
    
    for day in range(forecast_days_count):
        forecast_date = start_date + timedelta(days=day)
        
        # Vérification de cohérence : s'assurer qu'on ne dépasse pas MAX_FORECAST_DATE
        if forecast_date > MAX_FORECAST_DATE:
            # Arrêter le forecast si on dépasse la date limite
            break
        
        day_name = forecast_date.strftime('%A')
        
        # Base historique selon jour de la semaine
        # Gestion robuste : vérifier le type et la présence de la clé
        if isinstance(weekly_credit_pattern, dict) and day_name in weekly_credit_pattern:
            base_credit = weekly_credit_pattern[day_name]
        else:
            base_credit = avg_daily_credit if avg_daily_credit is not None and not pd.isna(avg_daily_credit) else 0
        
        if isinstance(weekly_debit_pattern, dict) and day_name in weekly_debit_pattern:
            base_debit = weekly_debit_pattern[day_name]
        else:
            base_debit = avg_daily_debit if avg_daily_debit is not None and not pd.isna(avg_daily_debit) else 0
        
        # Factures du jour PAR DEVISE (avec gestion des cas où les DataFrames sont vides)
        # Calculer les encaissements/décaissements par devise (EUR, USD, JPY)
        sales_day_eur = sales_day_usd = sales_day_jpy = 0
        purchase_day_eur = purchase_day_usd = purchase_day_jpy = 0
        
        # Récupérer les taux de change (déjà définis plus haut, mais on s'assure qu'ils sont accessibles)
        usd_rate = fx_rates.get('USD', 0.92) if fx_rates and 'USD' in fx_rates else 0.92
        jpy_rate = fx_rates.get('JPY', 0.0065) if fx_rates and 'JPY' in fx_rates else 0.0065
        
        if len(sales_open) > 0 and 'payment_date' in sales_open.columns:
            sales_day_df = sales_open[sales_open['payment_date'] == forecast_date]
            if len(sales_day_df) > 0:
                # Calculer par devise (utiliser amount original, pas amount_eur)
                if 'currency' in sales_day_df.columns and 'amount' in sales_day_df.columns:
                    sales_day_eur = sales_day_df[sales_day_df['currency'] == 'EUR']['amount'].sum() if len(sales_day_df[sales_day_df['currency'] == 'EUR']) > 0 else 0
                    sales_day_usd = sales_day_df[sales_day_df['currency'] == 'USD']['amount'].sum() if len(sales_day_df[sales_day_df['currency'] == 'USD']) > 0 else 0
                    sales_day_jpy = sales_day_df[sales_day_df['currency'] == 'JPY']['amount'].sum() if len(sales_day_df[sales_day_df['currency'] == 'JPY']) > 0 else 0
                # Total en EUR équivalent : calculer depuis les montants par devise pour cohérence
                # (au lieu d'utiliser amount_eur qui peut avoir des arrondis différents)
                sales_day = sales_day_eur + (sales_day_usd * usd_rate) + (sales_day_jpy * jpy_rate)
                
                # Vérification de cohérence : comparer avec amount_eur.sum() (tolérance 0.01 EUR)
                sales_day_from_amount_eur = sales_day_df['amount_eur'].sum() if 'amount_eur' in sales_day_df.columns else 0
                if abs(sales_day - sales_day_from_amount_eur) > 0.01:
                    # Utiliser amount_eur si disponible et plus précis
                    sales_day = sales_day_from_amount_eur
                    # Recalculer les montants par devise depuis amount_eur pour cohérence
                    if 'amount_eur' in sales_day_df.columns:
                        sales_day_eur = sales_day_df[sales_day_df['currency'] == 'EUR']['amount_eur'].sum() if len(sales_day_df[sales_day_df['currency'] == 'EUR']) > 0 else 0
                        sales_day_usd = (sales_day_df[sales_day_df['currency'] == 'USD']['amount_eur'].sum() / usd_rate) if len(sales_day_df[sales_day_df['currency'] == 'USD']) > 0 and usd_rate > 0 else 0
                        sales_day_jpy = (sales_day_df[sales_day_df['currency'] == 'JPY']['amount_eur'].sum() / jpy_rate) if len(sales_day_df[sales_day_df['currency'] == 'JPY']) > 0 and jpy_rate > 0 else 0
            else:
                sales_day = 0
        else:
            sales_day = 0
        
        if len(purchase_open) > 0 and 'payment_date' in purchase_open.columns:
            purchase_day_df = purchase_open[purchase_open['payment_date'] == forecast_date]
            if len(purchase_day_df) > 0:
                # Calculer par devise (utiliser amount original, pas amount_eur)
                if 'currency' in purchase_day_df.columns and 'amount' in purchase_day_df.columns:
                    purchase_day_eur = purchase_day_df[purchase_day_df['currency'] == 'EUR']['amount'].sum() if len(purchase_day_df[purchase_day_df['currency'] == 'EUR']) > 0 else 0
                    purchase_day_usd = purchase_day_df[purchase_day_df['currency'] == 'USD']['amount'].sum() if len(purchase_day_df[purchase_day_df['currency'] == 'USD']) > 0 else 0
                    purchase_day_jpy = purchase_day_df[purchase_day_df['currency'] == 'JPY']['amount'].sum() if len(purchase_day_df[purchase_day_df['currency'] == 'JPY']) > 0 else 0
                # Total en EUR équivalent : calculer depuis les montants par devise pour cohérence
                purchase_day = purchase_day_eur + (purchase_day_usd * usd_rate) + (purchase_day_jpy * jpy_rate)
                
                # Vérification de cohérence : comparer avec amount_eur.sum() (tolérance 0.01 EUR)
                purchase_day_from_amount_eur = purchase_day_df['amount_eur'].sum() if 'amount_eur' in purchase_day_df.columns else 0
                if abs(purchase_day - purchase_day_from_amount_eur) > 0.01:
                    # Utiliser amount_eur si disponible et plus précis
                    purchase_day = purchase_day_from_amount_eur
                    # Recalculer les montants par devise depuis amount_eur pour cohérence
                    if 'amount_eur' in purchase_day_df.columns:
                        purchase_day_eur = purchase_day_df[purchase_day_df['currency'] == 'EUR']['amount_eur'].sum() if len(purchase_day_df[purchase_day_df['currency'] == 'EUR']) > 0 else 0
                        purchase_day_usd = (purchase_day_df[purchase_day_df['currency'] == 'USD']['amount_eur'].sum() / usd_rate) if len(purchase_day_df[purchase_day_df['currency'] == 'USD']) > 0 and usd_rate > 0 else 0
                        purchase_day_jpy = (purchase_day_df[purchase_day_df['currency'] == 'JPY']['amount_eur'].sum() / jpy_rate) if len(purchase_day_df[purchase_day_df['currency'] == 'JPY']) > 0 and jpy_rate > 0 else 0
            else:
                purchase_day = 0
        else:
            purchase_day = 0
        
        # Calculer les moyennes historiques par devise pour la base
        # NOTE: Pour simplifier, on applique la même proportion de base_credit/base_debit à chaque devise
        # selon la répartition historique des transactions par devise
        # IMPORTANT: Utiliser amount_eur pour les totaux (déjà converti en EUR), mais amount original pour les proportions par devise
        if len(bank_until_start) > 0:
            # Pour les totaux, utiliser amount_eur (déjà converti en EUR)
            if 'amount_eur' in bank_until_start.columns:
                total_credit_hist = bank_until_start[bank_until_start['type'] == 'credit']['amount_eur'].sum()
                total_debit_hist = bank_until_start[bank_until_start['type'] == 'debit']['amount_eur'].sum()
            else:
                # Fallback : convertir depuis amount (méthode vectorisée plus efficace)
                credit_rows = bank_until_start[bank_until_start['type'] == 'credit']
                debit_rows = bank_until_start[bank_until_start['type'] == 'debit']
                
                if len(credit_rows) > 0:
                    total_credit_hist = credit_rows.apply(
                        lambda row: convert_to_eur(row.get('amount', 0), row.get('currency', 'EUR'), fx_rates, row.get('date')), 
                        axis=1
                    ).sum()
                else:
                    total_credit_hist = 0
                
                if len(debit_rows) > 0:
                    total_debit_hist = debit_rows.apply(
                        lambda row: convert_to_eur(row.get('amount', 0), row.get('currency', 'EUR'), fx_rates, row.get('date')), 
                        axis=1
                    ).sum()
                else:
                    total_debit_hist = 0
            
            # Pour les proportions par devise, utiliser amount_eur (déjà converti) pour cohérence
            if 'amount_eur' in bank_until_start.columns:
                credit_eur_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'EUR')]['amount_eur'].sum()
                credit_usd_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'USD')]['amount_eur'].sum()
                credit_jpy_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'JPY')]['amount_eur'].sum()
                
                debit_eur_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'EUR')]['amount_eur'].sum()
                debit_usd_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'USD')]['amount_eur'].sum()
                debit_jpy_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'JPY')]['amount_eur'].sum()
            else:
                # Fallback : convertir depuis amount
                credit_eur_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'EUR')]['amount'].sum()
                credit_usd_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'USD')]['amount'].sum() * usd_rate
                credit_jpy_hist = bank_until_start[(bank_until_start['type'] == 'credit') & (bank_until_start['currency'] == 'JPY')]['amount'].sum() * jpy_rate
                
                debit_eur_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'EUR')]['amount'].sum()
                debit_usd_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'USD')]['amount'].sum() * usd_rate
                debit_jpy_hist = bank_until_start[(bank_until_start['type'] == 'debit') & (bank_until_start['currency'] == 'JPY')]['amount'].sum() * jpy_rate
            
            # Proportions par devise
            prop_credit_eur = credit_eur_hist / total_credit_hist if total_credit_hist > 0 else 0.86  # 86% par défaut (selon spécifications)
            prop_credit_usd = credit_usd_hist / total_credit_hist if total_credit_hist > 0 else 0.04  # 4% par défaut
            prop_credit_jpy = credit_jpy_hist / total_credit_hist if total_credit_hist > 0 else 0.14  # 14% par défaut
            
            prop_debit_eur = debit_eur_hist / total_debit_hist if total_debit_hist > 0 else 0.86
            prop_debit_usd = debit_usd_hist / total_debit_hist if total_debit_hist > 0 else 0.04
            prop_debit_jpy = debit_jpy_hist / total_debit_hist if total_debit_hist > 0 else 0.14
        else:
            # Valeurs par défaut selon spécifications (EUR 86%, USD 4%, JPY 14%)
            prop_credit_eur = prop_debit_eur = 0.86
            prop_credit_usd = prop_debit_usd = 0.04
            prop_credit_jpy = prop_debit_jpy = 0.14
        
        # Encaissements par devise
        base_credit_eur = base_credit * prop_credit_eur
        base_credit_usd = base_credit * prop_credit_usd
        base_credit_jpy = base_credit * prop_credit_jpy
        
        # Ajustements inflation (progressive sur la période)
        inflation_adjustment = 1 + (inflation_rate * day / 365) if inflation_rate is not None and not pd.isna(inflation_rate) else 1.0
        
        # Volatilité (simulation aléatoire avec seed pour reproductibilité)
        np.random.seed(100 + day)
        volume_adjustment_credit = 1 + np.random.normal(0, volume_volatility_credit * 0.3) if volume_volatility_credit is not None and not pd.isna(volume_volatility_credit) else 1.0
        volume_adjustment_credit = max(0.5, volume_adjustment_credit)  # Limite à -50% minimum
        
        # Encaissements par devise avec ajustements
        credit_eur = (base_credit_eur + sales_day_eur) * inflation_adjustment * volume_adjustment_credit
        credit_usd = (base_credit_usd + sales_day_usd) * inflation_adjustment * volume_adjustment_credit
        credit_jpy = (base_credit_jpy + sales_day_jpy) * inflation_adjustment * volume_adjustment_credit
        
        # Total en EUR équivalent (pour compatibilité)
        credit_forecast = credit_eur + (credit_usd * usd_rate) + (credit_jpy * jpy_rate)
        
        # Décaissements par devise
        base_debit_eur = base_debit * prop_debit_eur
        base_debit_usd = base_debit * prop_debit_usd
        base_debit_jpy = base_debit * prop_debit_jpy
        
        # Paiements récurrents (premier jour du mois) - en EUR uniquement (intérêts dette €20M)
        recurring_eur = 0
        if forecast_date.day == 1 and avg_monthly_recurring is not None and not pd.isna(avg_monthly_recurring):
            recurring_eur = avg_monthly_recurring
        
        # Volatilité débits
        volume_adjustment_debit = 1 + np.random.normal(0, volume_volatility_debit * 0.3) if volume_volatility_debit is not None and not pd.isna(volume_volatility_debit) else 1.0
        volume_adjustment_debit = max(0.5, volume_adjustment_debit)  # Limite à -50% minimum
        
        # Décaissements par devise avec ajustements
        debit_eur = (base_debit_eur + purchase_day_eur + recurring_eur) * inflation_adjustment * volume_adjustment_debit
        debit_usd = (base_debit_usd + purchase_day_usd) * inflation_adjustment * volume_adjustment_debit
        debit_jpy = (base_debit_jpy + purchase_day_jpy) * inflation_adjustment * volume_adjustment_debit
        
        # Total en EUR équivalent (pour compatibilité)
        debit_forecast = debit_eur + (debit_usd * usd_rate) + (debit_jpy * jpy_rate)
        
        # Cash flow net par devise
        net_eur = credit_eur - debit_eur
        net_usd = credit_usd - debit_usd
        net_jpy = credit_jpy - debit_jpy
        
        # Mettre à jour les cumuls par devise
        cumul_eur += net_eur
        cumul_usd += net_usd
        cumul_jpy += net_jpy
        
        # Cash flow net total (EUR équivalent)
        # IMPORTANT: Vérifier la cohérence entre les deux méthodes de calcul
        net_forecast = credit_forecast - debit_forecast
        # Calculer aussi depuis les nets par devise pour vérification
        net_forecast_from_devises = net_eur + (net_usd * usd_rate) + (net_jpy * jpy_rate)
        
        # Utiliser la moyenne des deux si différence significative (tolérance 0.01 EUR)
        if abs(net_forecast - net_forecast_from_devises) > 0.01:
            # Utiliser la méthode depuis devises qui est plus précise
            net_forecast = net_forecast_from_devises
            # Réajuster credit_forecast et debit_forecast pour cohérence
            credit_forecast = credit_eur + (credit_usd * usd_rate) + (credit_jpy * jpy_rate)
            debit_forecast = debit_eur + (debit_usd * usd_rate) + (debit_jpy * jpy_rate)
            net_forecast = credit_forecast - debit_forecast
        
        cumul_total += net_forecast
        
        # Détection risques (cohérence : chaque jour est classé dans une seule zone)
        # IMPORTANT: On calcule les risques sur le SOLDE NET (cash - dette) car c'est plus réaliste
        # Le solde net reflète la vraie situation financière en tenant compte de la dette de 20M EUR
        cumul_net = cumul_total - DEBT_PRINCIPAL  # Solde net (cash - dette)
        
        # Zones de risque basées sur le SOLDE NET (cash - dette) - Analyse principale
        # Cette analyse est plus réaliste car elle tient compte de la dette de 20M EUR
        # Avec une dette de 20M et seulement 6-8M de cash, le solde net est très négatif = situation critique
        if cumul_net < -100000:
            risk_zones['Critical'] += 1
            risk_level_net = 'Critical'
            # Si le solde net est critique, c'est aussi un jour négatif (même si le cash disponible est positif)
            if cumul_net < 0:
                negative_days.append(forecast_date)
        elif cumul_net < 0:
            risk_zones['Warning'] += 1
            risk_level_net = 'Warning'
            # Si le solde net est négatif, c'est aussi un jour négatif
            negative_days.append(forecast_date)
        else:
            risk_zones['Safe'] += 1
            risk_level_net = 'Safe'
        
        # Zones de risque basées sur le CASH DISPONIBLE (information complémentaire)
        # Cette analyse est affichée à titre informatif pour montrer la liquidité disponible
        if cumul_total < 0:
            # Si le cash disponible est aussi négatif, c'est une situation encore plus critique
            if cumul_net < -100000:
                # Déjà en Critical, pas besoin de changer
                pass
            elif cumul_net < 0:
                # Si le cash disponible est négatif ET le solde net est négatif, c'est Critical
                # Mais on garde Warning si le solde net est juste négatif mais cash disponible positif
                pass
        
        # Vérification de cohérence : chaque jour doit être compté exactement une fois
        # (vérification implicite : if/else garantit qu'un seul compteur est incrémenté)
        
        # Enregistrer toutes les valeurs (positives ET négatives) avec détails par devise
        # Arrondir à 2 décimales pour cohérence et lisibilité
        # IMPORTANT: Les valeurs négatives sont préservées (pas de abs())
        forecast_days.append({
            'Date': forecast_date.strftime('%Y-%m-%d'),
            'Jour': day_name,
            'Mois': forecast_date.strftime('%B'),
            # Totaux en EUR équivalent (pour compatibilité)
            'Encaissements': round(float(credit_forecast), 2) if not pd.isna(credit_forecast) else 0.0,
            'Décaissements': round(float(debit_forecast), 2) if not pd.isna(debit_forecast) else 0.0,
            'Cash_Flow_Net': round(float(net_forecast), 2) if not pd.isna(net_forecast) else 0.0,  # Peut être négatif
            'Cumul_Total_EUR': round(float(cumul_total), 2) if not pd.isna(cumul_total) else round(float(initial_balance_total), 2),   # Peut être négatif (pas de abs())
            # Détails par devise - Encaissements
            'Encaissements_EUR': round(float(credit_eur), 2) if not pd.isna(credit_eur) else 0.0,
            'Encaissements_USD': round(float(credit_usd), 2) if not pd.isna(credit_usd) else 0.0,
            'Encaissements_JPY': round(float(credit_jpy), 2) if not pd.isna(credit_jpy) else 0.0,
            # Détails par devise - Décaissements
            'Décaissements_EUR': round(float(debit_eur), 2) if not pd.isna(debit_eur) else 0.0,
            'Décaissements_USD': round(float(debit_usd), 2) if not pd.isna(debit_usd) else 0.0,
            'Décaissements_JPY': round(float(debit_jpy), 2) if not pd.isna(debit_jpy) else 0.0,
            # Détails par devise - Cash Flow Net
            'Cash_Flow_Net_EUR': round(float(net_eur), 2) if not pd.isna(net_eur) else 0.0,
            'Cash_Flow_Net_USD': round(float(net_usd), 2) if not pd.isna(net_usd) else 0.0,
            'Cash_Flow_Net_JPY': round(float(net_jpy), 2) if not pd.isna(net_jpy) else 0.0,
            # Détails par devise - Cumuls
            'Cumul_EUR': round(float(cumul_eur), 2) if not pd.isna(cumul_eur) else round(float(initial_balance_eur), 2),
            'Cumul_USD': round(float(cumul_usd), 2) if not pd.isna(cumul_usd) else round(float(initial_balance_usd), 2),
            'Cumul_JPY': round(float(cumul_jpy), 2) if not pd.isna(cumul_jpy) else round(float(initial_balance_jpy), 2),
            # Solde Net (cash - dette) pour analyse de risque réaliste
            'Cumul_Net_EUR': round(float(cumul_net), 2) if not pd.isna(cumul_net) else round(float(initial_balance_net), 2),
            'Risk_Level_Net': risk_level_net  # Niveau de risque basé sur le solde net
        })
    
    forecast_daily_df = pd.DataFrame(forecast_days)
    
    # Vérification de cohérence : le cumul final doit correspondre
    # Vérifier que le cumul est cohérent (somme des cash flows nets + solde initial)
    if len(forecast_daily_df) > 0:
        calculated_final = initial_balance_total + forecast_daily_df['Cash_Flow_Net'].sum()
        
        # Vérification supplémentaire : cohérence entre cumul_total et somme des cumuls par devise
        # Récupérer les taux de change utilisés
        usd_rate = fx_rates.get('USD', 0.92) if fx_rates and 'USD' in fx_rates else 0.92
        jpy_rate = fx_rates.get('JPY', 0.0065) if fx_rates and 'JPY' in fx_rates else 0.0065
        
        # Calculer le cumul total depuis les cumuls par devise (si disponibles)
        if 'Cumul_EUR' in forecast_daily_df.columns and 'Cumul_USD' in forecast_daily_df.columns and 'Cumul_JPY' in forecast_daily_df.columns:
            last_row = forecast_daily_df.iloc[-1]
            cumul_total_from_devises = last_row['Cumul_EUR'] + (last_row['Cumul_USD'] * usd_rate) + (last_row['Cumul_JPY'] * jpy_rate)
            
            # Vérifier la cohérence (tolérance pour arrondis)
            if abs(cumul_total_from_devises - cumul_total) > 1.0:  # Tolérance de 1 EUR pour les arrondis cumulés
                # Ajuster cumul_total pour qu'il soit cohérent avec les cumuls par devise
                cumul_total = cumul_total_from_devises
                if not STREAMLIT_MODE:
                    print(f"   ⚠️  Ajustement cohérence: cumul_total aligné avec cumuls par devise ({cumul_total:,.2f} EUR)")
        
        # Tolérance pour les erreurs d'arrondi (0.01 EUR)
        if abs(calculated_final - cumul_total) > 0.01:
            # Réajuster pour garantir la cohérence
            cumul_total = calculated_final
            # Mettre à jour la dernière ligne
            if len(forecast_daily_df) > 0:
                forecast_daily_df.iloc[-1, forecast_daily_df.columns.get_loc('Cumul_Total_EUR')] = round(cumul_total, 2)
                # Mettre aussi à jour les cumuls par devise pour cohérence
                if 'Cumul_EUR' in forecast_daily_df.columns:
                    # Ajuster proportionnellement pour maintenir la cohérence
                    last_row_idx = forecast_daily_df.index[-1]
                    current_cumul_eur = forecast_daily_df.loc[last_row_idx, 'Cumul_EUR']
                    current_cumul_usd = forecast_daily_df.loc[last_row_idx, 'Cumul_USD']
                    current_cumul_jpy = forecast_daily_df.loc[last_row_idx, 'Cumul_JPY']
                    current_total_from_devises = current_cumul_eur + (current_cumul_usd * usd_rate) + (current_cumul_jpy * jpy_rate)
                    
                    if abs(current_total_from_devises) > 0.01:
                        # Ajuster proportionnellement
                        ratio = cumul_total / current_total_from_devises
                        forecast_daily_df.loc[last_row_idx, 'Cumul_EUR'] = round(current_cumul_eur * ratio, 2)
                        forecast_daily_df.loc[last_row_idx, 'Cumul_USD'] = round(current_cumul_usd * ratio, 2)
                        forecast_daily_df.loc[last_row_idx, 'Cumul_JPY'] = round(current_cumul_jpy * ratio, 2)
    
    # Trouver le jour le plus bas (basé sur le SOLDE NET pour refléter la vraie situation)
    if len(forecast_daily_df) > 0 and 'Cumul_Net_EUR' in forecast_daily_df.columns:
        # Utiliser le solde net pour trouver le jour le plus bas (plus réaliste avec la dette)
        worst_day_idx = forecast_daily_df['Cumul_Net_EUR'].idxmin()
        worst_day = forecast_daily_df.loc[worst_day_idx]
        # S'assurer que Cumul_Total_EUR est aussi dans worst_day pour compatibilité
        if 'Cumul_Total_EUR' not in worst_day.index:
            worst_day['Cumul_Total_EUR'] = worst_day.get('Cumul_Net_EUR', 0) + DEBT_PRINCIPAL
    elif len(forecast_daily_df) > 0 and 'Cumul_Total_EUR' in forecast_daily_df.columns:
        # Fallback sur Cumul_Total_EUR si Cumul_Net_EUR n'existe pas
        worst_day_idx = forecast_daily_df['Cumul_Total_EUR'].idxmin()
        worst_day = forecast_daily_df.loc[worst_day_idx]
    else:
        # Cas limite : pas de données
        worst_day = pd.Series({'Date': start_date.strftime('%Y-%m-%d'), 'Cumul_Total_EUR': initial_balance_total, 'Cumul_Net_EUR': initial_balance_net})
    
    return {
        'forecast_df': forecast_daily_df,
        'start_date': start_date,
        'end_date': end_date,
        'forecast_days_count': forecast_days_count,
        'initial_balance': initial_balance_total,
        'initial_balance_net': initial_balance_total - DEBT_PRINCIPAL,  # Solde net (cash - dette)
        'initial_balance_eur': initial_balance_eur,
        'initial_balance_usd': initial_balance_usd,
        'initial_balance_jpy': initial_balance_jpy,
        'final_balance': cumul_total,
        'final_balance_net': cumul_total - DEBT_PRINCIPAL,  # Solde net final (cash - dette)
        'negative_days': negative_days,
        'risk_zones': risk_zones,
        'worst_day': worst_day,
        'sales_open': sales_open,
        'purchase_open': purchase_open
    }

# ============================================================================
# DASHBOARD STREAMLIT
# ============================================================================

# Ne charger le dashboard que si on est vraiment en mode Streamlit (lancé via streamlit run)
# ET pas en mode script
if STREAMLIT_MODE and IS_STREAMLIT_RUN and not SCRIPT_MODE:
    # Configuration de la page
    st.set_page_config(
        page_title="Cash Flow Forecasting - Dashboard Professionnel",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS personnalisé
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
    
    st.markdown('<div class="main-header">📊 Cash Flow Forecasting - Dashboard Professionnel</div>', unsafe_allow_html=True)
    
    # Sidebar
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
    
    @st.cache_data
    def load_data():
        """Charge les données depuis les CSV"""
        try:
            # Recalculer les chemins absolus (au cas où le répertoire de travail change)
            script_path = Path(__file__).absolute()
            root_dir = script_path.parent.parent  # deliverables/
            
            bank_path = root_dir / 'bank_transactions.csv'
            sales_path = root_dir / 'sales_invoices.csv'
            purchase_path = root_dir / 'purchase_invoices.csv'
            
            # Vérifier que les fichiers existent
            if not bank_path.exists():
                st.error(f"❌ Fichier non trouvé: {bank_path}")
                st.info(f"📁 Répertoire de données: {root_dir}")
                st.info(f"📁 Fichiers dans ce répertoire:")
                try:
                    csv_files = list(root_dir.glob('*.csv'))
                    for f in csv_files:
                        st.info(f"   - {f.name}")
                except:
                    pass
                return None, None, None
            
            # Charger les données
            bank = pd.read_csv(bank_path, parse_dates=['date'])
            sales = pd.read_csv(sales_path, parse_dates=['issue_date', 'due_date', 'payment_date'])
            purchase = pd.read_csv(purchase_path, parse_dates=['issue_date', 'due_date', 'payment_date'])
            
            st.success(f"✅ Données chargées avec succès!")
            st.info(f"📊 {len(bank)} transactions bancaires, {len(sales)} factures clients, {len(purchase)} factures fournisseurs")
            
            return bank, sales, purchase
        except Exception as e:
            st.error(f"❌ Erreur lors du chargement des données: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.info(f"📁 Répertoire de travail actuel: {Path.cwd()}")
            return None, None, None
    
    bank, sales, purchase = load_data()
    
    if bank is None:
        st.error("❌ Impossible de charger les données. Vérifiez que les fichiers CSV sont présents.")
        st.stop()
    
    # Calculer les métriques de base
    # IMPORTANT: Convertir toutes les transactions en EUR pour les calculs
    # Récupérer les taux de change une seule fois
    fx_rates_dashboard = get_real_exchange_rates()
    # Convertir amount en EUR selon la devise
    bank['amount_eur'] = bank.apply(
        lambda x: convert_to_eur(x['amount'], x.get('currency', 'EUR'), fx_rates_dashboard, x['date']), 
        axis=1
    )
    
    # DSO - Vérifier les dates invalides correctement
    sales_paid = sales[sales['status'] == 'Paid'].copy()
    if len(sales_paid) > 0:
        # Calculer days_to_pay pour toutes les factures (même si certaines dates sont manquantes)
        sales_paid['has_valid_dates'] = sales_paid['payment_date'].notna() & sales_paid['issue_date'].notna()
        # Calculer days_to_pay seulement pour les factures avec dates valides
        sales_paid.loc[sales_paid['has_valid_dates'], 'days_to_pay'] = (
            sales_paid.loc[sales_paid['has_valid_dates'], 'payment_date'] - 
            sales_paid.loc[sales_paid['has_valid_dates'], 'issue_date']
        ).dt.days
        
        sales_paid_valid = sales_paid[sales_paid['has_valid_dates']].copy()
        if len(sales_paid_valid) > 0:
            dso_mean = sales_paid_valid['days_to_pay'].mean()
        else:
            dso_mean = 0
    else:
        dso_mean = 0
        sales_paid_valid = pd.DataFrame()
    
    # DPO - Vérifier les dates invalides correctement
    purchase_paid = purchase[purchase['status'] == 'Paid'].copy()
    if len(purchase_paid) > 0:
        # Calculer days_to_pay pour toutes les factures (même si certaines dates sont manquantes)
        purchase_paid['has_valid_dates'] = purchase_paid['payment_date'].notna() & purchase_paid['issue_date'].notna()
        # Calculer days_to_pay seulement pour les factures avec dates valides
        purchase_paid.loc[purchase_paid['has_valid_dates'], 'days_to_pay'] = (
            purchase_paid.loc[purchase_paid['has_valid_dates'], 'payment_date'] - 
            purchase_paid.loc[purchase_paid['has_valid_dates'], 'issue_date']
        ).dt.days
        
        purchase_paid_valid = purchase_paid[purchase_paid['has_valid_dates']].copy()
        if len(purchase_paid_valid) > 0:
            dpo_mean = purchase_paid_valid['days_to_pay'].mean()
        else:
            dpo_mean = 0
    else:
        dpo_mean = 0
        purchase_paid_valid = pd.DataFrame()
    
    # Sections du dashboard
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
            fig = px.pie(values=[recurring_count, non_recurring_count], names=['Récurrent', 'Non-récurrent'],
                        title="Répartition Récurrent vs Non-récurrent",
                        color_discrete_sequence=['#28a745', '#ffc107'])
            st.plotly_chart(fig, width='stretch')
        
        with col2:
            st.markdown("""
            **Justification:**
            - Les transactions récurrentes sont prévisibles (salaires, intérêts)
            - Les transactions non-récurrentes nécessitent une analyse spécifique
            - Cette classification améliore la précision du forecast
            """)
            
            st.metric("Récurrent", f"{recurring_count:,} ({recurring_count/len(bank)*100:.1f}%)")
            st.metric("Non-récurrent", f"{non_recurring_count:,} ({non_recurring_count/len(bank)*100:.1f}%)")
    
    elif section == "🔢 Calculs Détailés":
        st.markdown('<div class="section-header">🔢 Calculs Détailés avec Justifications</div>', unsafe_allow_html=True)
        
        variable = st.selectbox(
            "Choisir une variable à analyser:",
            [
                "DSO (Days Sales Outstanding)",
                "DPO (Days Payable Outstanding)",
                "Inflation",
                "Volatilité des Volumes",
                "Taux d'Impayés",
                "Retards de Paiement",
                "Volatilité FX",
                "Solde Initial",
                "Forecast Quotidien",
                "📅 Données Historiques 2024 (Tous les Jours)"
            ]
        )
        
        if variable == "DSO (Days Sales Outstanding)" and len(sales_paid) > 0:
            st.markdown("### 📊 Calcul du DSO")
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis données historiques réelles<br>
            📊 <strong>Source :</strong> Factures clients avec status='Paid' dans sales_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Élevée (basée sur transactions réelles payées)<br>
            ⚠️ <strong>Limitation :</strong> Ne reflète que le comportement passé, peut varier selon contexte économique
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DSO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Filtrer les factures payées (données réelles, pas théoriques)
sales_paid = sales[sales['status'] == 'Paid'].copy()

# Calculer les jours entre émission et paiement
# NOTE: Utilise les dates réelles de paiement, pas les dates d'échéance
sales_paid['days_to_pay'] = (sales_paid['payment_date'] - sales_paid['issue_date']).dt.days

# Calculer la moyenne arithmétique
# NOTE: La moyenne est plus sensible aux valeurs extrêmes que la médiane
dso_mean = sales_paid['days_to_pay'].mean()
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `issue_date` : Date d'émission de la facture (colonne présente dans sales_invoices.csv)
            - ✅ `payment_date` : Date de paiement réel (colonne présente, non nulle pour status='Paid')
            - ✅ `status` : Filtre pour ne garder que les factures 'Paid' (données réelles, pas théoriques)
            - ✅ Calcul : `days_to_pay = payment_date - issue_date` (différence en jours)
            - ⚠️ **Important :** On utilise payment_date (réel) et non due_date (théorique) pour refléter le comportement réel
            """)
            
            st.markdown("**Calcul détaillé (20 premières factures):**")
            display_cols = ['invoice_id', 'issue_date', 'payment_date', 'days_to_pay']
            if len(sales_paid_valid) > 0 and all(col in sales_paid_valid.columns for col in display_cols):
                st.dataframe(sales_paid_valid[display_cols].head(20))
            elif all(col in sales_paid.columns for col in ['invoice_id', 'issue_date', 'payment_date']):
                # Afficher même si days_to_pay n'existe pas encore
                st.dataframe(sales_paid[['invoice_id', 'issue_date', 'payment_date']].head(20))
            else:
                st.warning(f"Colonnes manquantes. Colonnes disponibles: {list(sales_paid.columns)}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Moyenne", f"{dso_mean:.2f} jours")
            with col2:
                median_val = sales_paid_valid['days_to_pay'].median() if len(sales_paid_valid) > 0 else 0
                st.metric("Médiane", f"{median_val:.2f} jours")
            with col3:
                std_val = sales_paid_valid['days_to_pay'].std() if len(sales_paid_valid) > 0 else 0
                st.metric("Écart-type", f"{std_val:.2f} jours")
            
            st.markdown("**Vérification des données:**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total factures payées", len(sales_paid))
                # Compter les factures avec dates valides (payment_date ET issue_date non nulles)
                valid_count = len(sales_paid[(sales_paid['payment_date'].notna()) & (sales_paid['issue_date'].notna())])
                st.metric("Factures avec dates valides", valid_count)
            with col2:
                # Compter les factures avec dates invalides (payment_date OU issue_date manquantes)
                invalid_count = len(sales_paid) - valid_count
                st.metric("Factures avec dates invalides", invalid_count)
                if invalid_count > 0:
                    st.warning(f"⚠️ {invalid_count} factures avec dates manquantes (payment_date ou issue_date vide)")
                # Vérifier les jours négatifs (payment_date avant issue_date)
                if len(sales_paid_valid) > 0:
                    negative_days = len(sales_paid_valid[sales_paid_valid['days_to_pay'] < 0])
                    if negative_days > 0:
                        st.warning(f"⚠️ {negative_days} factures avec jours négatifs (payment_date avant issue_date)")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi utiliser les factures payées ?**
            - ✅ Les factures payées reflètent le comportement RÉEL des clients (pas théorique)
            - ✅ Les dates de paiement réelles incluent les retards, négociations, etc.
            - ✅ Plus fiable que d'utiliser les dates d'échéance (due_date) qui sont souvent idéales
            
            **Méthode de calcul :**
            - On calcule `payment_date - issue_date` pour chaque facture payée
            - La moyenne arithmétique donne le DSO moyen historique
            - ⚠️ **Note :** La médiane serait plus robuste aux valeurs aberrantes, mais la moyenne est standard
            
            **Application au forecast :**
            - Cette moyenne historique est utilisée pour prévoir quand les factures ouvertes seront payées
            - On applique : `expected_payment_date = due_date + DSO_moyen`
            - ⚠️ **Limitation :** Assume que le comportement futur sera similaire au passé
            
            **Fiabilité :**
            - 🟢 **Élevée** si nombre de factures payées > 30 (loi des grands nombres)
            - 🟡 **Moyenne** si nombre de factures payées entre 10-30
            - 🔴 **Faible** si nombre de factures payées < 10 (échantillon trop petit)
            """)
            
            if len(sales_paid_valid) > 0:
                fig = px.histogram(sales_paid_valid, x='days_to_pay', nbins=30, title="Distribution du DSO", 
                                  labels={'days_to_pay': 'Jours', 'count': 'Nombre de factures'})
                fig.add_vline(x=dso_mean, line_dash="dash", line_color="red", annotation_text=f"Moyenne: {dso_mean:.1f}j")
                st.plotly_chart(fig, width='stretch')
            else:
                st.warning("Pas de données valides pour afficher le graphique")
        
        elif variable == "DPO (Days Payable Outstanding)" and len(purchase_paid) > 0:
            st.markdown("### 📊 Calcul du DPO")
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis données historiques réelles<br>
            📊 <strong>Source :</strong> Factures fournisseurs avec status='Paid' dans purchase_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Élevée (basée sur transactions réelles payées)<br>
            ⚠️ <strong>Limitation :</strong> Reflète les délais négociés passés, peut changer selon relations fournisseurs
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"DPO = \frac{1}{n} \sum_{i=1}^{n} (payment\_date_i - issue\_date_i)")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Filtrer les factures payées (données réelles, pas théoriques)
purchase_paid = purchase[purchase['status'] == 'Paid'].copy()

# Calculer les jours entre émission et paiement
# NOTE: Utilise les dates réelles de paiement, inclut les retards négociés
purchase_paid['days_to_pay'] = (purchase_paid['payment_date'] - purchase_paid['issue_date']).dt.days

# Calculer la moyenne arithmétique
# NOTE: La moyenne reflète les délais réels, incluant les négociations
dpo_mean = purchase_paid['days_to_pay'].mean()
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `issue_date` : Date d'émission de la facture fournisseur (colonne présente dans purchase_invoices.csv)
            - ✅ `payment_date` : Date de paiement réel (colonne présente, non nulle pour status='Paid')
            - ✅ `status` : Filtre pour ne garder que les factures 'Paid' (données réelles, pas théoriques)
            - ✅ Calcul : `days_to_pay = payment_date - issue_date` (différence en jours)
            - ⚠️ **Important :** On utilise payment_date (réel) et non due_date (théorique) pour refléter les délais réels négociés
            """)
            
            st.markdown("**Calcul détaillé (20 premières factures):**")
            display_cols = ['invoice_id', 'issue_date', 'payment_date', 'days_to_pay']
            if len(purchase_paid_valid) > 0 and all(col in purchase_paid_valid.columns for col in display_cols):
                st.dataframe(purchase_paid_valid[display_cols].head(20))
            elif all(col in purchase_paid.columns for col in ['invoice_id', 'issue_date', 'payment_date']):
                # Afficher même si days_to_pay n'existe pas encore
                st.dataframe(purchase_paid[['invoice_id', 'issue_date', 'payment_date']].head(20))
            else:
                st.warning(f"Colonnes manquantes. Colonnes disponibles: {list(purchase_paid.columns)}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Moyenne", f"{dpo_mean:.2f} jours")
            with col2:
                median_val = purchase_paid_valid['days_to_pay'].median() if len(purchase_paid_valid) > 0 else 0
                st.metric("Médiane", f"{median_val:.2f} jours")
            with col3:
                std_val = purchase_paid_valid['days_to_pay'].std() if len(purchase_paid_valid) > 0 else 0
                st.metric("Écart-type", f"{std_val:.2f} jours")
            
            st.markdown("**Vérification des données:**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total factures payées", len(purchase_paid))
                # Compter les factures avec dates valides (payment_date ET issue_date non nulles)
                valid_count = len(purchase_paid[(purchase_paid['payment_date'].notna()) & (purchase_paid['issue_date'].notna())])
                st.metric("Factures avec dates valides", valid_count)
            with col2:
                # Compter les factures avec dates invalides (payment_date OU issue_date manquantes)
                invalid_count = len(purchase_paid) - valid_count
                st.metric("Factures avec dates invalides", invalid_count)
                if invalid_count > 0:
                    st.warning(f"⚠️ {invalid_count} factures avec dates manquantes (payment_date ou issue_date vide)")
                # Vérifier les jours négatifs (payment_date avant issue_date)
                if len(purchase_paid_valid) > 0:
                    negative_days = len(purchase_paid_valid[purchase_paid_valid['days_to_pay'] < 0])
                    if negative_days > 0:
                        st.warning(f"⚠️ {negative_days} factures avec jours négatifs (payment_date avant issue_date)")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi utiliser les factures payées ?**
            - ✅ Les factures payées reflètent les délais RÉELS négociés avec les fournisseurs
            - ✅ Les dates de paiement réelles incluent les retards, escomptes, négociations
            - ✅ Plus fiable que d'utiliser les dates d'échéance (due_date) qui peuvent être idéales
            
            **Méthode de calcul :**
            - On calcule `payment_date - issue_date` pour chaque facture payée
            - La moyenne arithmétique donne le DPO moyen historique
            - ⚠️ **Note :** Un DPO élevé améliore la trésorerie mais peut affecter les relations fournisseurs
            
            **Application au forecast :**
            - Cette moyenne historique est utilisée pour prévoir quand les factures ouvertes seront payées
            - On applique : `expected_payment_date = due_date + DPO_moyen`
            - ⚠️ **Limitation :** Assume que les délais négociés futurs seront similaires au passé
            
            **Fiabilité :**
            - 🟢 **Élevée** si nombre de factures payées > 30 (loi des grands nombres)
            - 🟡 **Moyenne** si nombre de factures payées entre 10-30
            - 🔴 **Faible** si nombre de factures payées < 10 (échantillon trop petit)
            """)
            
            if len(purchase_paid_valid) > 0:
                fig = px.histogram(purchase_paid_valid, x='days_to_pay', nbins=30, title="Distribution du DPO",
                                  labels={'days_to_pay': 'Jours', 'count': 'Nombre de factures'})
                fig.add_vline(x=dpo_mean, line_dash="dash", line_color="red", annotation_text=f"Moyenne: {dpo_mean:.1f}j")
                st.plotly_chart(fig, width='stretch')
            else:
                st.warning("Pas de données valides pour afficher le graphique")
        
        elif variable == "Inflation":
            st.markdown("### 📈 Calcul de l'Inflation")
            
            # Analyser les coûts récurrents
            bank_recurring = bank[bank['category'].isin(['Supplier Payment', 'Payroll', 'Loan Interest'])].copy()
            bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')
            monthly_recurring = bank_recurring.groupby('month')['amount'].sum().sort_index()
            
            if len(monthly_recurring) >= 6:
                growth_rates = []
                for i in range(1, len(monthly_recurring)):
                    if monthly_recurring.iloc[i-1] > 0:
                        growth = (monthly_recurring.iloc[i] - monthly_recurring.iloc[i-1]) / monthly_recurring.iloc[i-1]
                        growth_rates.append(growth)
                
                if len(growth_rates) > 0:
                    avg_monthly_growth = np.mean(growth_rates)
                    annual_inflation = avg_monthly_growth * 12
                    
                    if annual_inflation < 0:
                        inflation_rate = 0.02
                        st.warning("Croissance négative détectée, utilisation de 2% (déflation peu probable)")
                    elif annual_inflation > 0.10:
                        inflation_rate = 0.02
                        st.warning("Croissance >10% (probablement croissance activité), utilisation de 2%")
                    else:
                        inflation_rate = annual_inflation
                    
                    # Nature de la valeur
                    st.markdown("""
                    <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #856404;">
                    <strong>📌 NATURE DE LA VALEUR :</strong><br>
                    🔄 <strong>CALCULÉE</strong> depuis évolution des coûts récurrents historiques<br>
                    📊 <strong>Source :</strong> Transactions bancaires récurrentes (Supplier Payment, Payroll, Loan Interest)<br>
                    🎯 <strong>Fiabilité :</strong> Moyenne à Élevée (si ≥6 mois de données)<br>
                    ⚠️ <strong>Fallback :</strong> Si données insuffisantes ou valeur aberrante, utilise 2% (moyenne zone euro 2024)<br>
                    📝 <strong>Note :</strong> Isolée de la croissance d'activité en filtrant uniquement les coûts récurrents
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
                    st.markdown("**Formule mathématique:**")
                    st.latex(r"Inflation = \frac{1}{n-1} \sum_{i=2}^{n} \frac{Coût_i - Coût_{i-1}}{Coût_{i-1}} \times 12")
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("**Implémentation Python:**")
                    st.code("""
# Filtrer les coûts récurrents uniquement (isoler l'inflation de la croissance)
# NOTE: On exclut les transactions non-récurrentes pour éviter de confondre 
#       inflation et croissance d'activité
bank_recurring = bank[bank['category'].isin([
    'Supplier Payment',  # Paiements fournisseurs (coûts récurrents)
    'Payroll',           # Salaires (coûts récurrents)
    'Loan Interest'      # Intérêts (coûts récurrents)
])].copy()
bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')

# Agréger par mois (somme des coûts récurrents par mois)
monthly_recurring = bank_recurring.groupby('month')['amount'].sum().sort_index()

# Calculer les taux de croissance mensuels (mois à mois)
growth_rates = []
for i in range(1, len(monthly_recurring)):
    if monthly_recurring.iloc[i-1] > 0:
        # Taux de croissance = (nouveau - ancien) / ancien
        growth = (monthly_recurring.iloc[i] - monthly_recurring.iloc[i-1]) / monthly_recurring.iloc[i-1]
        growth_rates.append(growth)

# Inflation annuelle = moyenne des croissances mensuelles × 12
# NOTE: On annualise en multipliant par 12 (approximation linéaire)
avg_monthly_growth = np.mean(growth_rates)
annual_inflation = avg_monthly_growth * 12

# Validation et fallback
if annual_inflation < 0 or annual_inflation > 0.10:
    # Valeur aberrante : probablement croissance d'activité ou déflation
    # Utilise 2% (moyenne zone euro 2024) comme valeur par défaut
    inflation_rate = 0.02
else:
    inflation_rate = annual_inflation
                    """, language='python')
                    
                    st.markdown("**Colonnes utilisées (vérification):**")
                    st.info("""
                    - ✅ `date` : Date de la transaction (colonne présente dans bank_transactions.csv)
                    - ✅ `category` : Filtre pour 'Supplier Payment', 'Payroll', 'Loan Interest' (coûts récurrents uniquement)
                    - ✅ `amount` : Montant de la transaction
                    - ✅ Calcul : Évolution mensuelle des coûts récurrents pour isoler l'inflation
                    - ⚠️ **Important :** On filtre uniquement les coûts récurrents pour éviter de confondre inflation et croissance d'activité
                    - ⚠️ **Validation :** Si inflation calculée < 0% ou > 10%, utilise 2% (valeur par défaut zone euro)
                    """)
                    
                    st.markdown("**Évolution mensuelle des coûts récurrents:**")
                    monthly_df = pd.DataFrame({
                        'Mois': [str(m) for m in monthly_recurring.index],
                        'Montant': monthly_recurring.values
                    })
                    st.dataframe(monthly_df)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Inflation Annuelle Calculée", f"{annual_inflation*100:.2f}%")
                        st.metric("Inflation Annuelle Utilisée", f"{inflation_rate*100:.2f}%")
                    
                    with col2:
                        st.markdown("**Justification méthodologique:**")
                        st.info("""
                        **Pourquoi filtrer uniquement les coûts récurrents ?**
                        - ✅ Les coûts récurrents (salaires, fournisseurs, intérêts) sont affectés par l'inflation
                        - ✅ En excluant les transactions non-récurrentes, on isole l'inflation de la croissance d'activité
                        - ✅ Évite de confondre une hausse de volume d'activité avec une hausse des prix
                        
                        **Méthode de calcul :**
                        - On calcule l'évolution mois par mois des coûts récurrents
                        - La moyenne des taux de croissance mensuels × 12 donne l'inflation annuelle
                        - ⚠️ **Limitation :** Assume que l'inflation est constante sur l'année (approximation)
                        
                        **Validation et fallback :**
                        - Si inflation calculée < 0% : Probable déflation ou baisse d'activité → utilise 2% (défaut)
                        - Si inflation calculée > 10% : Probable croissance d'activité confondue → utilise 2% (défaut)
                        - Si données < 6 mois : Pas assez de données → utilise 2% (moyenne zone euro 2024)
                        
                        **Fiabilité :**
                        - 🟢 **Élevée** si ≥12 mois de données et inflation entre 0-10%
                        - 🟡 **Moyenne** si 6-11 mois de données
                        - 🔴 **Faible** si <6 mois de données (utilise valeur par défaut 2%)
                        
                        **Source de la valeur par défaut (2%) :**
                        - 📊 Moyenne de l'inflation zone euro en 2024 (source : BCE)
                        - ✅ Valeur conservatrice et réaliste pour les prévisions 2025
                        """)
                    
                    fig = px.line(x=[str(m) for m in monthly_recurring.index], y=monthly_recurring.values,
                                 title="Évolution des Coûts Récurrents (Base pour Inflation)",
                                 labels={'x': 'Mois', 'y': 'Montant (EUR)'})
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.warning("Données insuffisantes pour calculer l'inflation")
            else:
                st.warning("Moins de 6 mois de données, utilisation de 2% (moyenne zone euro)")
                inflation_rate = 0.02
                st.metric("Inflation Utilisée", f"{inflation_rate*100:.2f}%")
        
        elif variable == "Volatilité des Volumes":
            st.markdown("### 📊 Calcul de la Volatilité des Volumes")
            
            # Vérifier que les colonnes nécessaires existent
            if 'type' not in bank.columns or 'amount_eur' not in bank.columns:
                st.error("❌ Colonnes manquantes: 'type' ou 'amount_eur' non trouvées dans les données bancaires")
                st.stop()
            
            # Filtrer les crédits et débits
            bank_credits = bank[bank['type']=='credit']
            bank_debits = bank[bank['type']=='debit']
            
            if len(bank_credits) == 0:
                st.warning("⚠️ Aucune transaction de crédit trouvée")
                avg_daily_credit = 0
                std_daily_credit = 0
            else:
                avg_daily_credit = bank_credits['amount_eur'].mean()
                std_daily_credit = bank_credits['amount_eur'].std()
            
            if len(bank_debits) == 0:
                st.warning("⚠️ Aucune transaction de débit trouvée")
                avg_daily_debit = 0
                std_daily_debit = 0
            else:
                avg_daily_debit = bank_debits['amount_eur'].mean()
                std_daily_debit = bank_debits['amount_eur'].std()
            
            volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
            volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis statistiques historiques (écart-type / moyenne)<br>
            📊 <strong>Source :</strong> Toutes les transactions bancaires historiques (bank_transactions.csv)<br>
            🎯 <strong>Fiabilité :</strong> Élevée (statistique descriptive sur données réelles)<br>
            ⚠️ <strong>Limitation :</strong> Reflète la volatilité passée, peut changer selon contexte économique
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"Volatilité = \frac{Écart-type}{Moyenne} = \frac{\sigma}{\mu}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Calculer moyenne et écart-type des montants quotidiens
# NOTE: Utilise toutes les transactions historiques pour calculer la dispersion
avg_daily_credit = bank[bank['type']=='credit']['amount_eur'].mean()
std_daily_credit = bank[bank['type']=='credit']['amount_eur'].std()

# Volatilité = écart-type relatif (coefficient de variation)
# NOTE: Le coefficient de variation permet de comparer la volatilité 
#       indépendamment de l'échelle (montant moyen)
volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0

# Même calcul pour les décaissements
avg_daily_debit = bank[bank['type']=='debit']['amount_eur'].mean()
std_daily_debit = bank[bank['type']=='debit']['amount_eur'].std()
volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `type` : 'credit' pour encaissements, 'debit' pour décaissements (colonne présente)
            - ✅ `amount_eur` : Montant en EUR (après conversion si nécessaire, colonne calculée)
            - ✅ Calcul : Coefficient de variation (écart-type / moyenne)
            - ⚠️ **Important :** Utilise TOUTES les transactions historiques, pas seulement les récurrentes
            - ⚠️ **Note :** Une volatilité élevée (>50%) indique des variations importantes jour à jour
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Encaissements:**")
                st.metric("Moyenne", f"{avg_daily_credit:,.2f} EUR")
                st.metric("Écart-type", f"{std_daily_credit:,.2f} EUR")
                st.metric("Volatilité", f"{volume_volatility_credit*100:.1f}%")
            
            with col2:
                st.markdown("**Décaissements:**")
                st.metric("Moyenne", f"{avg_daily_debit:,.2f} EUR")
                st.metric("Écart-type", f"{std_daily_debit:,.2f} EUR")
                st.metric("Volatilité", f"{volume_volatility_debit*100:.1f}%")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi utiliser le coefficient de variation ?**
            - ✅ Permet de comparer la volatilité indépendamment de l'échelle (montant moyen)
            - ✅ Un coefficient de 0.5 signifie que l'écart-type est 50% de la moyenne
            - ✅ Plus robuste que l'écart-type absolu pour comparer encaissements et décaissements
            
            **Méthode de calcul :**
            - On calcule la moyenne et l'écart-type de TOUTES les transactions historiques
            - Le coefficient de variation = écart-type / moyenne
            - ⚠️ **Note :** Utilise toutes les transactions, pas seulement les récurrentes (reflète la vraie volatilité)
            
            **Application au forecast :**
            - La volatilité est utilisée pour simuler des variations aléatoires jour à jour
            - On applique : `variation = moyenne × (1 ± volatilité × facteur_aléatoire)`
            - ⚠️ **Limitation :** Assume que la volatilité future sera similaire au passé
            
            **Fiabilité :**
            - 🟢 **Élevée** si nombre de transactions > 100 (loi des grands nombres)
            - 🟡 **Moyenne** si nombre de transactions entre 30-100
            - 🔴 **Faible** si nombre de transactions < 30 (échantillon trop petit)
            
            **Interprétation :**
            - Volatilité < 30% : Variations faibles, prévisions stables
            - Volatilité 30-70% : Variations modérées, prévisions moyennement fiables
            - Volatilité > 70% : Variations importantes, prévisions peu fiables
            """)
            
            # Graphique de distribution
            credits = bank[bank['type']=='credit']['amount_eur']
            debits = bank[bank['type']=='debit']['amount_eur']
            
            # Vérifier que les imports sont disponibles et que les données ne sont pas vides
            if STREAMLIT_MODE and 'go' in globals() and 'make_subplots' in globals():
                if len(credits) > 0 or len(debits) > 0:
                    try:
                        fig = make_subplots(rows=1, cols=2, subplot_titles=('Encaissements', 'Décaissements'))
                        
                        if len(credits) > 0:
                            fig.add_trace(go.Histogram(x=credits, nbinsx=30, name='Encaissements'), row=1, col=1)
                        else:
                            fig.add_trace(go.Histogram(x=[0], nbinsx=1, name='Encaissements (aucune donnée)'), row=1, col=1)
                        
                        if len(debits) > 0:
                            fig.add_trace(go.Histogram(x=debits, nbinsx=30, name='Décaissements'), row=1, col=2)
                        else:
                            fig.add_trace(go.Histogram(x=[0], nbinsx=1, name='Décaissements (aucune donnée)'), row=1, col=2)
                        
                        fig.update_layout(title_text="Distribution des Montants Quotidiens", showlegend=False)
                        st.plotly_chart(fig, width='stretch')
                    except Exception as e:
                        st.error(f"Erreur lors de la création du graphique: {e}")
                else:
                    st.warning("Aucune donnée disponible pour créer le graphique")
            else:
                st.warning("Imports Plotly non disponibles - graphique désactivé")
        
        elif variable == "Taux d'Impayés":
            st.markdown("### 💳 Calcul du Taux d'Impayés")
            
            # Initialiser toutes les variables pour éviter les erreurs
            very_overdue = pd.DataFrame()
            very_old_open = pd.DataFrame()
            suspected_unpaid = 0
            default_rate_calculated = 0.01
            default_rate = 0.01
            
            today_analysis = pd.Timestamp('2024-12-31')
            sales_overdue = sales[sales['status'] == 'Overdue'].copy()
            
            if len(sales_overdue) > 0:
                # Vérifier que due_date existe et n'est pas null
                if 'due_date' in sales_overdue.columns:
                    sales_overdue_valid = sales_overdue[sales_overdue['due_date'].notna()].copy()
                    if len(sales_overdue_valid) > 0:
                        sales_overdue_valid['age_days'] = (today_analysis - sales_overdue_valid['due_date']).dt.days
                        very_overdue = sales_overdue_valid[sales_overdue_valid['age_days'] > 90]
                
                sales_open_analysis = sales[sales['status'] == 'Open'].copy()
                if len(sales_open_analysis) > 0:
                    # Vérifier que issue_date existe et n'est pas null
                    if 'issue_date' in sales_open_analysis.columns:
                        sales_open_valid = sales_open_analysis[sales_open_analysis['issue_date'].notna()].copy()
                        if len(sales_open_valid) > 0:
                            sales_open_valid['age_days'] = (today_analysis - sales_open_valid['issue_date']).dt.days
                            very_old_open = sales_open_valid[sales_open_valid['age_days'] > 180]
                    
                    suspected_unpaid = len(very_overdue) + len(very_old_open)
                    default_rate_calculated = suspected_unpaid / len(sales) if len(sales) > 0 else 0.01
                    default_rate = min(default_rate_calculated, 0.05) if default_rate_calculated > 0 else 0.01
                    
                    if default_rate < 0.01:
                        default_rate = 0.01
                else:
                    default_rate_calculated = len(very_overdue) / len(sales) if len(sales) > 0 else 0.01
                    default_rate = default_rate_calculated if default_rate_calculated > 0 else 0.01
                    if default_rate < 0.01:
                        default_rate = 0.01
                    suspected_unpaid = len(very_overdue)
            else:
                default_rate = 0.01
                default_rate_calculated = 0.01
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"Taux\ d'impayés = \frac{Factures\ très\ en\ retard\ (>90j) + Factures\ ouvertes\ très\ anciennes\ (>180j)}{Total\ factures}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #721c24;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            🔍 <strong>ESTIMÉE</strong> depuis factures suspectées impayées (heuristique)<br>
            📊 <strong>Source :</strong> Factures avec status='Overdue' >90j ou 'Open' >180j dans sales_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Moyenne (estimation conservatrice, pas de données réelles d'impayés)<br>
            ⚠️ <strong>Limitation :</strong> Estimation basée sur heuristique, pas sur données réelles d'impayés<br>
            📝 <strong>Valeurs par défaut :</strong> Min 1%, Max 5% (plage conservatrice standard industrie)
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Factures très en retard (>90 jours après due_date)
# NOTE: Heuristique : une facture >90j en retard est suspectée impayée
sales_overdue = sales[sales['status'] == 'Overdue'].copy()
sales_overdue['age_days'] = (today - sales_overdue['due_date']).dt.days
very_overdue = sales_overdue[sales_overdue['age_days'] > 90]

# Factures ouvertes très anciennes (>180 jours après issue_date)
# NOTE: Heuristique : une facture ouverte >180j est suspectée impayée
sales_open = sales[sales['status'] == 'Open'].copy()
sales_open['age_days'] = (today - sales_open['issue_date']).dt.days
very_old_open = sales_open[sales_open['age_days'] > 180]

# Taux d'impayés estimé
# NOTE: Estimation conservatrice avec plage min 1%, max 5%
#       (valeurs standard industrie pour entreprises B2B)
suspected_unpaid = len(very_overdue) + len(very_old_open)
default_rate_calculated = suspected_unpaid / len(sales) if len(sales) > 0 else 0.01
default_rate = max(0.01, min(default_rate_calculated, 0.05))  # Entre 1% et 5%
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `status` : 'Overdue' pour factures en retard, 'Open' pour factures ouvertes (colonne présente)
            - ✅ `due_date` : Date d'échéance (pour calculer le retard, colonne présente)
            - ✅ `issue_date` : Date d'émission (pour calculer l'âge, colonne présente)
            - ✅ Calcul : Factures suspectées impayées / Total factures
            - ⚠️ **Important :** Utilise des HEURISTIQUES (>90j retard, >180j ouvert) car pas de données réelles d'impayés
            - ⚠️ **Plage :** Limité entre 1% (min conservateur) et 5% (max réaliste industrie B2B)
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Factures >90j en retard", len(very_overdue))
                st.metric("Factures ouvertes >180j", len(very_old_open))
                st.metric("Total suspecté impayé", suspected_unpaid)
            
            with col2:
                st.metric("Taux calculé", f"{default_rate_calculated*100:.2f}%")
                st.metric("Taux utilisé (conservateur)", f"{default_rate*100:.1f}%")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi utiliser des heuristiques ?**
            - ⚠️ **Problème :** Pas de données réelles d'impayés dans les fichiers fournis
            - ✅ **Solution :** Utilise des heuristiques basées sur l'âge des factures
            - ✅ Factures >90j en retard (Overdue) : Probablement impayées
            - ✅ Factures >180j ouvertes (Open) : Probablement impayées ou oubliées
            
            **Méthode d'estimation :**
            - Compte les factures suspectées impayées selon heuristiques
            - Taux = (factures suspectées) / (total factures)
            - ⚠️ **Limitation :** Estimation, pas mesure réelle (pas de données d'impayés confirmés)
            
            **Plage conservatrice (1% - 5%) :**
            - 📊 **1% minimum :** Valeur conservatrice standard pour entreprises B2B stables
            - 📊 **5% maximum :** Valeur réaliste maximum pour éviter surestimation
            - ✅ **Source :** Standards industrie (moyenne B2B : 1-3%, entreprises à risque : 3-5%)
            
            **Application au forecast :**
            - Le taux est appliqué aux encaissements futurs : `encaissement × (1 - taux_impayés)`
            - ⚠️ **Conservateur :** Mieux vaut surestimer les impayés que les sous-estimer
            
            **Fiabilité :**
            - 🟡 **Moyenne** : Estimation basée sur heuristiques, pas données réelles
            - ⚠️ **Recommandation :** À ajuster selon connaissance métier de l'entreprise
            
            **Amélioration possible :**
            - Si données historiques d'impayés disponibles : utiliser taux réel
            - Si analyse par client : taux différencié selon risque client
            """)
        
        elif variable == "Retards de Paiement":
            st.markdown("### ⏱️ Calcul des Retards de Paiement")
            
            # Calculer les retards pour les clients
            sales_overdue_count = len(sales[sales['status'] == 'Overdue'])
            overdue_rate_sales = sales_overdue_count / len(sales) if len(sales) > 0 else 0
            
            # Calculer les retards pour les fournisseurs
            purchase_overdue_count = len(purchase[purchase['status'] == 'Overdue'])
            overdue_rate_purchase = purchase_overdue_count / len(purchase) if len(purchase) > 0 else 0
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #155724;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            ✅ <strong>CALCULÉE</strong> depuis données historiques réelles<br>
            📊 <strong>Source :</strong> Factures avec status='Overdue' dans sales_invoices.csv et purchase_invoices.csv<br>
            🎯 <strong>Fiabilité :</strong> Élevée (basée sur données réelles de statut des factures)<br>
            ⚠️ <strong>Limitation :</strong> Reflète le comportement passé, peut varier selon contexte économique
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"Taux\ de\ retard = \frac{Nombre\ de\ factures\ Overdue}{Total\ factures}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Calculer le taux de retard pour les clients
sales_overdue_count = len(sales[sales['status'] == 'Overdue'])
overdue_rate_sales = sales_overdue_count / len(sales) if len(sales) > 0 else 0

# Calculer le taux de retard pour les fournisseurs
purchase_overdue_count = len(purchase[purchase['status'] == 'Overdue'])
overdue_rate_purchase = purchase_overdue_count / len(purchase) if len(purchase) > 0 else 0
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `status` : Statut de la facture ('Overdue', 'Paid', 'Open') - colonne présente
            - ✅ Calcul : (Nombre de factures Overdue) / (Total factures)
            - ⚠️ **Important :** Utilise le statut réel des factures dans les données
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Factures Clients:**")
                st.metric("Total factures", len(sales))
                st.metric("Factures en retard", sales_overdue_count)
                st.metric("Taux de retard", f"{overdue_rate_sales*100:.2f}%")
            
            with col2:
                st.markdown("**Factures Fournisseurs:**")
                st.metric("Total factures", len(purchase))
                st.metric("Factures en retard", purchase_overdue_count)
                st.metric("Taux de retard", f"{overdue_rate_purchase*100:.2f}%")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi mesurer les retards de paiement ?**
            - ✅ Indicateur de santé financière et de gestion de trésorerie
            - ✅ Permet d'ajuster les prévisions de cash flow (encaissements/décaissements retardés)
            - ✅ Aide à identifier les risques de liquidité
            
            **Méthode de calcul :**
            - Compte simplement le nombre de factures avec status='Overdue'
            - Taux = (factures Overdue) / (total factures)
            - ⚠️ **Note :** Ne distingue pas le degré de retard (1 jour vs 100 jours)
            
            **Application au forecast :**
            - Les retards peuvent être utilisés pour ajuster les délais de paiement prévus
            - Exemple : Si 10% des factures sont en retard, ajuster DSO/DPO en conséquence
            - ⚠️ **Limitation :** Assume que le comportement futur sera similaire au passé
            
            **Fiabilité :**
            - 🟢 **Élevée** : Basée sur données réelles de statut des factures
            - ⚠️ **Recommandation :** Analyser aussi la distribution des retards (moyenne, médiane)
            """)
        
        elif variable == "Volatilité FX":
            st.markdown("### 💱 Calcul de la Volatilité FX")
            
            # Récupérer les taux de change
            fx_rates = get_real_exchange_rates()
            
            # Calculer l'exposition FX depuis les transactions historiques
            bank_usd = bank[bank['currency'] == 'USD']
            bank_jpy = bank[bank['currency'] == 'JPY']
            
            exposure_usd = bank_usd['amount'].sum() if len(bank_usd) > 0 else 0
            exposure_jpy = bank_jpy['amount'].sum() if len(bank_jpy) > 0 else 0
            
            # Estimation de la volatilité FX (basée sur standards de marché)
            # Note: Sans données historiques de taux de change, on utilise des estimations standard
            fx_volatility_usd = 0.10  # ~10% volatilité annuelle USD/EUR (standard marché)
            fx_volatility_jpy = 0.12  # ~12% volatilité annuelle JPY/EUR (standard marché)
            
            # Nature de la valeur
            st.markdown("""
            <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin-bottom: 20px; color: #856404;">
            <strong>📌 NATURE DE LA VALEUR :</strong><br>
            🔄 <strong>ESTIMÉE</strong> depuis standards de marché (pas de données historiques de taux)<br>
            📊 <strong>Source :</strong> Volatilités standard marché FX (USD/EUR ~10%, JPY/EUR ~12%)<br>
            🎯 <strong>Fiabilité :</strong> Moyenne (estimations basées sur standards marché, pas données réelles)<br>
            ⚠️ <strong>Limitation :</strong> Volatilités estimées, pas calculées depuis données historiques de taux
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
            st.markdown("**Formule mathématique:**")
            st.latex(r"Volatilité\ FX = Écart-type\ relatif\ des\ variations\ de\ taux\ de\ change")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python:**")
            st.code("""
# Récupérer les taux de change actuels
fx_rates = get_real_exchange_rates()

# Calculer l'exposition FX
exposure_usd = bank[bank['currency'] == 'USD']['amount'].sum()
exposure_jpy = bank[bank['currency'] == 'JPY']['amount'].sum()

# Estimation de volatilité (sans données historiques de taux)
# NOTE: Utilise des valeurs standard marché
fx_volatility_usd = 0.10  # ~10% volatilité annuelle USD/EUR
fx_volatility_jpy = 0.12  # ~12% volatilité annuelle JPY/EUR
            """, language='python')
            
            st.markdown("**Colonnes utilisées (vérification):**")
            st.info("""
            - ✅ `currency` : Devise de la transaction (EUR, USD, JPY) - colonne présente
            - ✅ `amount` : Montant de la transaction - colonne présente
            - ✅ Calcul : Exposition FX = somme des montants par devise
            - ⚠️ **Important :** Volatilités estimées (pas de données historiques de taux de change)
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Exposition USD:**")
                st.metric("Montant total USD", f"{exposure_usd:,.2f} USD")
                st.metric("Équivalent EUR", f"{exposure_usd * fx_rates.get('USD', 0.92):,.2f} EUR")
                st.metric("Volatilité estimée", f"{fx_volatility_usd*100:.1f}%")
            
            with col2:
                st.markdown("**Exposition JPY:**")
                st.metric("Montant total JPY", f"{exposure_jpy:,.2f} JPY")
                st.metric("Équivalent EUR", f"{exposure_jpy * fx_rates.get('JPY', 0.0065):,.2f} EUR")
                st.metric("Volatilité estimée", f"{fx_volatility_jpy*100:.1f}%")
            
            st.markdown("**Taux de change actuels:**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("USD/EUR", f"{fx_rates.get('USD', 0.92):.4f}")
            with col2:
                st.metric("JPY/EUR", f"{fx_rates.get('JPY', 0.0065):.6f}")
            
            st.markdown("**Justification méthodologique:**")
            st.info("""
            **Pourquoi mesurer la volatilité FX ?**
            - ✅ Permet d'estimer le risque de change sur les encaissements/décaissements en devises étrangères
            - ✅ Aide à dimensionner les besoins de couverture (hedging)
            - ✅ Permet de calculer des scénarios de stress (variations de taux)
            
            **Méthode d'estimation :**
            - ⚠️ **Limitation :** Pas de données historiques de taux de change dans les fichiers fournis
            - ✅ **Solution :** Utilise des volatilités standard marché (estimations conservatrices)
            - 📊 **USD/EUR :** ~10% volatilité annuelle (standard marché 2024)
            - 📊 **JPY/EUR :** ~12% volatilité annuelle (standard marché 2024)
            
            **Application au forecast :**
            - La volatilité est utilisée pour simuler des variations de taux de change
            - Scénarios : Base, Optimiste (+5%), Pessimiste (-5%)
            - ⚠️ **Note :** Les variations sont appliquées aux encaissements/décaissements en devises étrangères
            
            **Fiabilité :**
            - 🟡 **Moyenne** : Estimations basées sur standards marché, pas données réelles
            - ⚠️ **Recommandation :** Si données historiques de taux disponibles, calculer volatilité réelle
            
            **Amélioration possible :**
            - Si données historiques de taux disponibles : calculer volatilité réelle (écart-type des variations)
            - Analyser corrélations entre devises
            - Utiliser modèles GARCH pour volatilité dynamique
            """)
        
        elif variable == "Solde Initial":
            st.markdown("### 💰 Calcul du Solde Initial")
            
            start_date_str = st.text_input("Date de début du forecast (YYYY-MM-DD):", value="2025-01-01")
            try:
                start_date = pd.to_datetime(start_date_str).date()
                
                bank_until_start = bank[bank['date'].dt.date < start_date]
                
                if len(bank_until_start) > 0:
                    initial_balance_eur = bank_until_start[bank_until_start['currency'] == 'EUR']['amount'].sum()
                    initial_balance_usd = bank_until_start[bank_until_start['currency'] == 'USD']['amount'].sum()
                    initial_balance_jpy = bank_until_start[bank_until_start['currency'] == 'JPY']['amount'].sum()
                    
                    fx_rates = get_real_exchange_rates()
                    initial_balance = initial_balance_eur + (initial_balance_usd * fx_rates.get('USD', 0.92)) + (initial_balance_jpy * fx_rates.get('JPY', 0.0065))
                    
                    st.markdown('<div class="calculation-box">', unsafe_allow_html=True)
                    st.markdown("**Formule mathématique:**")
                    st.latex(r"Solde\ Initial = \sum_{i=1}^{n} Transaction_i\ (jusqu'à\ la\ date\ de\ début)")
                    
                    st.markdown("**Implémentation Python:**")
                    st.code("""
# Filtrer les transactions jusqu'à la date de début
bank_until_start = bank[bank['date'].dt.date < start_date]

# Calculer le solde par devise
initial_balance_eur = bank_until_start[bank_until_start['currency'] == 'EUR']['amount'].sum()
initial_balance_usd = bank_until_start[bank_until_start['currency'] == 'USD']['amount'].sum()
initial_balance_jpy = bank_until_start[bank_until_start['currency'] == 'JPY']['amount'].sum()

# Convertir en EUR équivalent
fx_rates = get_real_exchange_rates()
initial_balance = initial_balance_eur + (initial_balance_usd * fx_rates['USD']) + (initial_balance_jpy * fx_rates['JPY'])
                    """, language='python')
                    
                    st.markdown("**Colonnes utilisées:**")
                    st.info("""
                    - `date` : Date de la transaction
                    - `currency` : Devise de la transaction (EUR, USD, JPY)
                    - `amount` : Montant de la transaction
                    - Calcul : Somme de toutes les transactions jusqu'à la date de début, par devise puis conversion en EUR
                    """)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("EUR", f"{initial_balance_eur:,.2f}")
                    with col2:
                        st.metric("USD", f"{initial_balance_usd:,.2f}")
                    with col3:
                        st.metric("JPY", f"{initial_balance_jpy:,.2f}")
                    with col4:
                        st.metric("Total EUR", f"{initial_balance:,.2f}")
                    
                    st.markdown("**Justification:**")
                    st.info("""
                    Le solde initial est la somme de toutes les transactions jusqu'à la date de début du forecast.
                    Calculé séparément par devise puis converti en EUR équivalent.
                    """)
                else:
                    st.warning("Aucune transaction avant cette date")
            except:
                st.error("Format de date invalide")
        
        elif variable == "Forecast Quotidien":
            st.markdown("### 📅 Calcul du Forecast Quotidien")
            
            st.markdown("""
            **Méthode de calcul jour par jour:**
            
            Pour chaque jour du forecast, on calcule:
            """)
            
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.markdown("""
            **Encaissements du jour =**
            - Base historique (moyenne ajustée selon jour de la semaine)
            + Factures clients avec payment_date = ce jour
            + Ajustements (inflation, volatilité, retards, impayés, FX)
            """)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.markdown("""
            **Décaissements du jour =**
            - Base historique (moyenne ajustée selon jour de la semaine)
            + Factures fournisseurs avec payment_date = ce jour
            + Paiements récurrents (intérêts, salaires, frais bancaires)
            + Ajustements (inflation, volatilité, retards, FX)
            """)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown('<div class="formula-box">', unsafe_allow_html=True)
            st.markdown("""
            **Cash Flow Net = Encaissements - Décaissements**
            
            **Cumul = Cumul précédent + Cash Flow Net**
            """)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("**Implémentation Python (simplifiée):**")
            st.code("""
# Pour chaque jour du forecast
for day in range(forecast_days_count):
    forecast_date = start_date + timedelta(days=day)
    
    # Base historique ajustée selon jour de la semaine
    day_name = forecast_date.strftime('%A')
    base_credit = weekly_credit_pattern.get(day_name, avg_daily_credit)
    base_debit = weekly_debit_pattern.get(day_name, avg_daily_debit)
    
    # Factures du jour
    sales_day = sales_open[sales_open['payment_date'] == forecast_date]['amount_eur'].sum()
    purchase_day = purchase_open[purchase_open['payment_date'] == forecast_date]['amount_eur'].sum()
    
    # Encaissements = base + factures + ajustements
    credit_forecast = base_credit + sales_day
    credit_forecast *= (1 + inflation_adjustment)  # Inflation
    credit_forecast *= (1 + volume_variation)     # Volatilité
    
    # Décaissements = base + factures + récurrents + ajustements
    debit_forecast = base_debit + purchase_day
    if is_recurring_payment_day:
        debit_forecast += monthly_interest  # Paiements récurrents
    debit_forecast *= (1 + inflation_adjustment)  # Inflation
    debit_forecast *= (1 + volume_variation)     # Volatilité
    
    # Cash flow net et cumul
    net_forecast = credit_forecast - debit_forecast
    cumul += net_forecast
            """, language='python')
            
            st.markdown("**Colonnes utilisées:**")
            st.info("""
            - `date` : Date de la transaction (pour patterns hebdomadaires)
            - `type` : 'credit' ou 'debit' (pour moyennes historiques)
            - `amount_eur` : Montant en EUR
            - `payment_date` : Date de paiement prévue (pour factures ouvertes)
            - `category` : Pour identifier les paiements récurrents
            - `currency` : Pour gestion multi-devises
            """)
            
            st.markdown("**Justification:**")
            st.info("""
            Le forecast quotidien combine:
            1. **Moyennes historiques** (baseline prévisible) - ajustées selon jour de la semaine
            2. **Factures ouvertes** (paiements réels attendus) - basées sur DSO/DPO calculés
            3. **Paiements récurrents** (intérêts, salaires) - ajoutés explicitement aux dates appropriées
            4. **Ajustements** (inflation, volatilité, retards, impayés, FX) - facteurs d'impact calculés
            
            Cette approche garantit une prévision réaliste basée sur les données historiques
            tout en intégrant les facteurs d'impact identifiés. Méthode Directe recommandée pour court terme.
            """)
        
        elif variable == "📅 Données Historiques 2024 (Tous les Jours)":
            st.markdown("### 📅 Analyse Détaillée des Données Historiques 2024")
            
            st.markdown("""
            **Cette section affiche TOUS les jours de 2024 avec les transactions détaillées.**
            Vous pouvez filtrer par mois, trimestre, jour de la semaine, ou type de transaction.
            """)
            
            # Préparer les données quotidiennes de 2024
            bank['year'] = bank['date'].dt.year
            bank['month'] = bank['date'].dt.month
            bank['month_name'] = bank['date'].dt.strftime('%B')
            bank['quarter'] = bank['date'].dt.quarter
            bank['day_of_week'] = bank['date'].dt.day_name()
            bank['day'] = bank['date'].dt.day
            
            # Agréger par jour (encaissements - décaissements)
            # Calculer séparément les crédits et débits pour chaque jour
            daily_credits = bank[bank['type'] == 'credit'].groupby('date')['amount_eur'].sum().reset_index()
            daily_credits.columns = ['Date', 'Credits']
            daily_debits = bank[bank['type'] == 'debit'].groupby('date')['amount_eur'].sum().reset_index()
            daily_debits.columns = ['Date', 'Debits']
            
            # Fusionner et calculer le cash flow net (peut être négatif)
            daily_data = pd.merge(daily_credits, daily_debits, on='Date', how='outer', fill_value=0)
            daily_data['Cash_Flow_Net'] = daily_data['Credits'] - daily_data['Debits']  # Peut être négatif
            daily_data['Nb_Transactions'] = bank.groupby('date').size().reset_index(name='count')['count']
            daily_data = daily_data[['Date', 'Cash_Flow_Net', 'Nb_Transactions']].copy()
            
            # Ajouter les colonnes de filtrage
            daily_data['Mois'] = pd.to_datetime(daily_data['Date']).dt.strftime('%B')
            daily_data['Trimestre'] = 'T' + pd.to_datetime(daily_data['Date']).dt.quarter.astype(str)
            daily_data['Jour_Semaine'] = pd.to_datetime(daily_data['Date']).dt.day_name()
            daily_data['Année'] = pd.to_datetime(daily_data['Date']).dt.year
            
            # Filtres
            st.markdown("#### 🔍 Filtres")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                selected_month = st.selectbox(
                    "Mois:",
                    options=['Tous'] + sorted(daily_data['Mois'].unique().tolist()),
                    key='filter_month'
                )
            
            with col2:
                selected_quarter = st.selectbox(
                    "Trimestre:",
                    options=['Tous'] + sorted(daily_data['Trimestre'].unique().tolist()),
                    key='filter_quarter'
                )
            
            with col3:
                selected_day = st.selectbox(
                    "Jour de la semaine:",
                    options=['Tous'] + sorted(daily_data['Jour_Semaine'].unique().tolist()),
                    key='filter_day'
                )
            
            with col4:
                min_date = daily_data['Date'].min()
                max_date = daily_data['Date'].max()
                date_range = st.date_input(
                    "Période:",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key='filter_date_range'
                )
            
            # Appliquer les filtres
            filtered_data = daily_data.copy()
            
            if selected_month != 'Tous':
                filtered_data = filtered_data[filtered_data['Mois'] == selected_month]
            
            if selected_quarter != 'Tous':
                filtered_data = filtered_data[filtered_data['Trimestre'] == selected_quarter]
            
            if selected_day != 'Tous':
                filtered_data = filtered_data[filtered_data['Jour_Semaine'] == selected_day]
            
            if isinstance(date_range, tuple) and len(date_range) == 2:
                if date_range[0] and date_range[1]:
                    filtered_data = filtered_data[
                        (filtered_data['Date'] >= pd.to_datetime(date_range[0])) &
                        (filtered_data['Date'] <= pd.to_datetime(date_range[1]))
                    ]
            
            # Statistiques filtrées
            st.markdown("#### 📊 Statistiques (Données Filtrées)")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Nombre de jours", len(filtered_data))
            with col2:
                st.metric("Cash Flow Net Total", f"{filtered_data['Cash_Flow_Net'].sum():,.2f} EUR")
            with col3:
                st.metric("Moyenne quotidienne", f"{filtered_data['Cash_Flow_Net'].mean():,.2f} EUR")
            with col4:
                st.metric("Total transactions", f"{filtered_data['Nb_Transactions'].sum():,}")
            
            # Graphique
            st.markdown("#### 📈 Évolution Quotidienne")
            fig = px.line(
                filtered_data,
                x='Date',
                y='Cash_Flow_Net',
                title=f"Cash Flow Net Quotidien - {selected_month if selected_month != 'Tous' else 'Tous les mois'}",
                labels={'Cash_Flow_Net': 'Cash Flow Net (EUR)', 'Date': 'Date'}
            )
            fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Seuil zéro")
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, width='stretch')
            
            # Tableau détaillé
            st.markdown("#### 📋 Détail Quotidien (Tous les Jours)")
            st.dataframe(
                filtered_data[['Date', 'Mois', 'Trimestre', 'Jour_Semaine', 'Cash_Flow_Net', 'Nb_Transactions']].sort_values('Date'),
                width='stretch',
                height=400
            )
            
            # Statistiques par mois
            st.markdown("#### 📅 Statistiques par Mois")
            monthly_stats = filtered_data.groupby('Mois').agg({
                'Cash_Flow_Net': ['sum', 'mean', 'count'],
                'Nb_Transactions': 'sum'
            }).reset_index()
            monthly_stats.columns = ['Mois', 'Total_CF', 'Moyenne_CF', 'Nb_Jours', 'Nb_Transactions']
            st.dataframe(monthly_stats, width='stretch')
            
            # Statistiques par trimestre
            st.markdown("#### 📊 Statistiques par Trimestre")
            quarterly_stats = filtered_data.groupby('Trimestre').agg({
                'Cash_Flow_Net': ['sum', 'mean', 'count'],
                'Nb_Transactions': 'sum'
            }).reset_index()
            quarterly_stats.columns = ['Trimestre', 'Total_CF', 'Moyenne_CF', 'Nb_Jours', 'Nb_Transactions']
            st.dataframe(quarterly_stats, width='stretch')
    
    elif section == "📈 Visualisations":
        st.markdown('<div class="section-header">📈 Visualisations Interactives</div>', unsafe_allow_html=True)
        
        # Graphique 1: Évolution temporelle
        st.markdown("### 📅 Évolution Temporelle des Flux")
        
        bank_daily = bank.groupby('date').agg({
            'amount_eur': lambda x: bank.loc[x.index[bank.loc[x.index, 'type']=='credit'], 'amount_eur'].sum() - 
                                bank.loc[x.index[bank.loc[x.index, 'type']=='debit'], 'amount_eur'].sum()
        }).reset_index()
        bank_daily.columns = ['date', 'net_cash_flow']
        
        fig = px.line(bank_daily, x='date', y='net_cash_flow', title="Cash Flow Net Quotidien (Historique)",
                      labels={'net_cash_flow': 'Cash Flow Net (EUR)', 'date': 'Date'})
        fig.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig, width='stretch')
        
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
        st.plotly_chart(fig, width='stretch')
        
        # Graphique 3: Distribution par catégorie
        st.markdown("### 📊 Distribution par Catégorie")
        
        category_flows = bank.groupby('category')['amount_eur'].sum().sort_values(ascending=False)
        
        fig = px.bar(x=category_flows.index, y=category_flows.values, title="Flux par Catégorie",
                     labels={'x': 'Catégorie', 'y': 'Montant Total (EUR)'})
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, width='stretch')
    
    elif section == "⚙️ Paramètres & Facteurs":
        st.markdown('<div class="section-header">⚙️ Paramètres & Facteurs d\'Impact</div>', unsafe_allow_html=True)
        
        st.markdown("### 📋 Tous les Facteurs d'Impact Calculés")
        
        # Calculer tous les facteurs
        bank_recurring = bank[bank['category'].isin(['Supplier Payment', 'Payroll', 'Loan Interest'])].copy()
        bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')
        monthly_recurring = bank_recurring.groupby('month')['amount'].sum().sort_index()
        
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
        
        overdue_rate_sales = len(sales[sales['status']=='Overdue']) / len(sales) if len(sales) > 0 else 0
        overdue_rate_purchase = len(purchase[purchase['status']=='Overdue']) / len(purchase) if len(purchase) > 0 else 0
        
        # Utiliser sales_paid_valid et purchase_paid_valid pour l'écart-type (seules les factures avec dates valides)
        dso_std = sales_paid_valid['days_to_pay'].std() if len(sales_paid_valid) > 0 and 'days_to_pay' in sales_paid_valid.columns else 0
        dpo_std = purchase_paid_valid['days_to_pay'].std() if len(purchase_paid_valid) > 0 and 'days_to_pay' in purchase_paid_valid.columns else 0
        
        avg_daily_credit = bank[bank['type']=='credit']['amount_eur'].mean()
        avg_daily_debit = bank[bank['type']=='debit']['amount_eur'].mean()
        std_daily_credit = bank[bank['type']=='credit']['amount_eur'].std()
        std_daily_debit = bank[bank['type']=='debit']['amount_eur'].std()
        volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
        volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
        
        fx_rates = get_real_exchange_rates()
        
        # Afficher dans des colonnes
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
            inflation_source = "Calculée (données historiques)" if len(monthly_recurring) >= 6 else "Par défaut (2% zone euro)"
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
    
    elif section == "🎯 Lancer Forecast":
        st.markdown('<div class="section-header">🎯 Lancer le Forecast</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 📅 Forecast des 3 Premiers Mois de 2025
        
        Ce forecast utilise les données historiques de 2024 pour projeter les flux de trésorerie
        de **janvier, février et mars 2025** (jusqu'au 31 mars 2025 maximum).
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            # FORCER le 1er janvier 2025 comme date de début
            start_date = st.date_input(
                "📅 Date de début du forecast:", 
                value=datetime(2025, 1, 1).date(),
                min_value=datetime(2025, 1, 1).date(),
                max_value=datetime(2025, 3, 31).date(),
                help="Le forecast commence obligatoirement au 1er janvier 2025 pour couvrir les 3 premiers mois"
            )
            # S'assurer que c'est bien le 1er janvier
            if start_date != datetime(2025, 1, 1).date():
                st.warning("⚠️ Le forecast doit commencer au 1er janvier 2025 pour couvrir les 3 premiers mois complets")
                start_date = datetime(2025, 1, 1).date()
                st.info(f"✅ Date corrigée: {start_date.strftime('%Y-%m-%d')}")
        
        with col2:
            # Permettre de choisir la date de fin du forecast
            end_date_input = st.date_input(
                "📅 Date de fin du forecast:", 
                value=datetime(2025, 3, 31).date(),
                min_value=datetime(2025, 1, 1).date(),
                max_value=datetime(2025, 3, 31).date(),
                help="Choisissez jusqu'à quelle date vous voulez faire le forecast (maximum: 31 mars 2025)"
            )
            # S'assurer que la date de fin est après la date de début
            if end_date_input < start_date:
                st.warning("⚠️ La date de fin doit être après la date de début")
                end_date_input = datetime(2025, 3, 31).date()
                st.info(f"✅ Date corrigée: {end_date_input.strftime('%Y-%m-%d')}")
            
            # Calculer le nombre de jours
            forecast_days = (end_date_input - start_date).days + 1
            st.info(f"""
            **Période sélectionnée:**
            - Début: {start_date.strftime('%Y-%m-%d')}
            - Fin: {end_date_input.strftime('%Y-%m-%d')}
            - Durée: {forecast_days} jour{'s' if forecast_days > 1 else ''}
            - Maximum possible: 90 jours (jusqu'au 31 mars 2025)
            """)
        
        # Initialiser session_state pour stocker les résultats du forecast
        if 'forecast_results' not in st.session_state:
            st.session_state.forecast_results = None
        
        if st.button("🚀 Lancer le Forecast", type="primary", width='stretch'):
            with st.spinner("⏳ Calcul du forecast en cours..."):
                # Calculer tous les paramètres nécessaires
                fx_rates = get_real_exchange_rates()
                
                # DSO/DPO (utiliser les variables déjà calculées au début)
                # sales_paid et purchase_paid sont déjà calculés avec days_to_pay au début du dashboard
                # Utiliser les valeurs déjà calculées
                if len(sales_paid_valid) > 0:
                    dso_mean = sales_paid_valid['days_to_pay'].mean()
                else:
                    dso_mean = 0
                
                if len(purchase_paid_valid) > 0:
                    dpo_mean = purchase_paid_valid['days_to_pay'].mean()
                else:
                    dpo_mean = 0
                
                # Moyennes et volatilités
                avg_daily_credit = bank[bank['type']=='credit']['amount_eur'].mean()
                avg_daily_debit = bank[bank['type']=='debit']['amount_eur'].mean()
                std_daily_credit = bank[bank['type']=='credit']['amount_eur'].std()
                std_daily_debit = bank[bank['type']=='debit']['amount_eur'].std()
                
                # Patterns hebdomadaires
                bank['day_of_week'] = bank['date'].dt.day_name()
                weekly_credit_pattern = bank[bank['type']=='credit'].groupby('day_of_week')['amount_eur'].mean().to_dict()
                weekly_debit_pattern = bank[bank['type']=='debit'].groupby('day_of_week')['amount_eur'].mean().to_dict()
                
                # Inflation
                bank_recurring = bank[bank['category'].isin(['Supplier Payment', 'Payroll', 'Loan Interest'])].copy()
                bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')
                # IMPORTANT: Utiliser amount_eur (déjà converti en EUR) au lieu de amount
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
                
                # Volatilité
                volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
                volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0
                
                # Utiliser la date de fin choisie par l'utilisateur (ou MAX_FORECAST_DATE si plus petite)
                effective_end_date = min(end_date_input, MAX_FORECAST_DATE)
                
                # Exécuter le forecast avec la date de fin choisie
                forecast_results = run_forecast_complete(
                    bank, sales, purchase, start_date, fx_rates, dso_mean, dpo_mean,
                    avg_daily_credit, avg_daily_debit, std_daily_credit, std_daily_debit,
                    weekly_credit_pattern, weekly_debit_pattern, inflation_rate,
                    volume_volatility_credit, volume_volatility_debit, effective_end_date
                )
                
                # Stocker dans session_state
                st.session_state.forecast_results = forecast_results
                
                # Afficher les résultats
                st.success(f"✅ Forecast calculé pour {st.session_state.forecast_results['forecast_days_count']} jours (du {st.session_state.forecast_results['start_date'].strftime('%Y-%m-%d')} au {st.session_state.forecast_results['end_date'].strftime('%Y-%m-%d')})")
        
        # Afficher les résultats seulement si le forecast a été lancé ET qu'on est dans la section "Lancer Forecast"
        # IMPORTANT: Cette condition garantit que les résultats ne s'affichent QUE dans cette section
        if st.session_state.forecast_results is not None and section == "🎯 Lancer Forecast":
            forecast_results = st.session_state.forecast_results
            
            # Résumé
            st.markdown("### 📊 Résumé du Forecast")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Solde Initial (Cash)", f"{forecast_results['initial_balance']:,.2f} EUR")
                st.caption(f"Solde Net: {forecast_results.get('initial_balance_net', forecast_results['initial_balance'] - DEBT_PRINCIPAL):,.2f} EUR")
            with col2:
                st.metric("Solde Final (Cash)", f"{forecast_results['final_balance']:,.2f} EUR")
                st.caption(f"Solde Net: {forecast_results.get('final_balance_net', forecast_results['final_balance'] - DEBT_PRINCIPAL):,.2f} EUR")
            with col3:
                variation = forecast_results['final_balance'] - forecast_results['initial_balance']
                st.metric("Variation", f"{variation:+,.2f} EUR", delta=f"{variation/abs(forecast_results['initial_balance'])*100:.1f}%" if forecast_results['initial_balance'] != 0 else None)
            with col4:
                st.metric("Jours Critiques", len(forecast_results['negative_days']))
            
            # Afficher la dette et les intérêts
            st.info(f"""
            **💰 Information sur la Dette:**
            - Dette principale: **{DEBT_PRINCIPAL:,.0f} EUR**
            - Intérêts mensuels: **{DEBT_MONTHLY_INTEREST:,.2f} EUR/mois** (taux {DEBT_INTEREST_RATE*100:.2f}%)
            - Solde net initial (Cash - Dette): **{forecast_results.get('initial_balance_net', forecast_results['initial_balance'] - DEBT_PRINCIPAL):,.2f} EUR**
            - Solde net final (Cash - Dette): **{forecast_results.get('final_balance_net', forecast_results['final_balance'] - DEBT_PRINCIPAL):,.2f} EUR**
            
            ⚠️ **Note:** Le forecast utilise le **cash disponible** (solde initial). La dette de 20M EUR est un passif qui n'affecte pas directement le cash flow, mais ses **intérêts mensuels sont déduits** dans les décaissements récurrents (le 1er de chaque mois).
            """)
            
            # Graphiques
            st.markdown("### 📈 Visualisations du Forecast")
            
            # Graphique 1: Évolution du cumul
            fig1 = px.line(
                forecast_results['forecast_df'], 
                x='Date', 
                y='Cumul_Total_EUR',
                title="Évolution du Cumul de Trésorerie (Janvier-Mars 2025)",
                labels={'Cumul_Total_EUR': 'Cumul (EUR)', 'Date': 'Date'}
            )
            fig1.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Seuil zéro")
            fig1.update_xaxes(tickangle=45)
            st.plotly_chart(fig1, width='stretch')
            
            # Graphique 2: Cash flow net quotidien
            fig2 = px.bar(
                forecast_results['forecast_df'],
                x='Date',
                y='Cash_Flow_Net',
                title="Cash Flow Net Quotidien",
                labels={'Cash_Flow_Net': 'Cash Flow Net (EUR)', 'Date': 'Date'},
                color='Cash_Flow_Net',
                color_continuous_scale=['red', 'white', 'green']
            )
            fig2.add_hline(y=0, line_dash="dash", line_color="black")
            fig2.update_xaxes(tickangle=45)
            st.plotly_chart(fig2, width='stretch')
            
            # Graphique 3: Par mois
            forecast_by_month = forecast_results['forecast_df'].groupby('Mois').agg({
                'Encaissements': 'sum',
                'Décaissements': 'sum',
                'Cash_Flow_Net': 'sum'
            }).reset_index()
            
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(name='Encaissements', x=forecast_by_month['Mois'], y=forecast_by_month['Encaissements'], marker_color='green'))
            fig3.add_trace(go.Bar(name='Décaissements', x=forecast_by_month['Mois'], y=forecast_by_month['Décaissements'], marker_color='red'))
            fig3.update_layout(
                title="Flux par Mois (Janvier-Mars 2025)",
                barmode='group',
                xaxis_title="Mois",
                yaxis_title="Montant (EUR)"
            )
            st.plotly_chart(fig3, width='stretch')
            
            # Tableau détaillé
            st.markdown("### 📋 Détail Quotidien (Tous les Jours)")
            st.dataframe(
                forecast_results['forecast_df'],
                width='stretch',
                height=600
            )
            
            # Analyses de risques
            st.markdown("### ⚠️ Analyse des Risques")
            
            # Vérifier la cohérence : si le worst_day a un cumul négatif, il devrait y avoir des jours en Warning ou Critical
            worst_day_balance = forecast_results['worst_day']['Cumul_Total_EUR'] if isinstance(forecast_results['worst_day']['Cumul_Total_EUR'], (int, float)) else float(str(forecast_results['worst_day']['Cumul_Total_EUR']).replace(',', ''))
            
            # Vérifier les jours négatifs basés sur le SOLDE NET (plus réaliste)
            if 'Cumul_Net_EUR' in forecast_results['forecast_df'].columns:
                negative_days_net = forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Net_EUR'] < 0]
                worst_day_net = forecast_results['forecast_df'].loc[forecast_results['forecast_df']['Cumul_Net_EUR'].idxmin()]
                worst_day_balance_net = worst_day_net['Cumul_Net_EUR']
                
                if len(negative_days_net) > 0:
                    first_negative_date = pd.to_datetime(negative_days_net.iloc[0]['Date'])
                    st.error(f"🚨 **SITUATION CRITIQUE** (basée sur Solde Net): {len(negative_days_net)} jours avec solde net négatif")
                    st.warning(f"⚠️ **PREMIER JOUR CRITIQUE**: {first_negative_date.strftime('%Y-%m-%d')}")
                    st.error(f"📉 **JOUR LE PLUS BAS** (Solde Net): {worst_day_net['Date']} (solde net: {worst_day_balance_net:,.2f} EUR)")
                    st.info(f"   💧 Cash disponible ce jour: {worst_day_net['Cumul_Total_EUR']:,.2f} EUR")
                else:
                    st.success("✅ Aucun jour avec solde net négatif détecté")
            else:
                # Fallback sur l'ancienne méthode si Cumul_Net_EUR n'existe pas
                if len(forecast_results['negative_days']) > 0:
                    st.error(f"🚨 **SITUATION CRITIQUE**: {len(forecast_results['negative_days'])} jours avec cumul négatif")
                    st.warning(f"⚠️ **PREMIER JOUR CRITIQUE**: {forecast_results['negative_days'][0].strftime('%Y-%m-%d')}")
                    st.error(f"📉 **JOUR LE PLUS BAS**: {forecast_results['worst_day']['Date']} (solde: {worst_day_balance:,.2f} EUR)")
                else:
                    st.success("✅ Aucun jour avec cumul négatif détecté")
            
            # Afficher la répartition avec vérification de cohérence
            total_days = forecast_results['risk_zones']['Safe'] + forecast_results['risk_zones']['Warning'] + forecast_results['risk_zones']['Critical']
            if total_days != forecast_results['forecast_days_count']:
                st.warning(f"⚠️ **INCOHÉRENCE**: Total des jours ({total_days}) ne correspond pas au nombre de jours forecast ({forecast_results['forecast_days_count']})")
            
            # Vérifier les valeurs réelles dans le DataFrame pour debug
            if len(forecast_results['forecast_df']) > 0:
                min_cumul = forecast_results['forecast_df']['Cumul_Total_EUR'].min()
                max_cumul = forecast_results['forecast_df']['Cumul_Total_EUR'].max()
                days_negative = len(forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Total_EUR'] < 0])
                days_critical = len(forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Total_EUR'] < -100000])
                days_warning = len(forecast_results['forecast_df'][(forecast_results['forecast_df']['Cumul_Total_EUR'] < 0) & (forecast_results['forecast_df']['Cumul_Total_EUR'] >= -100000)])
                
                # Afficher les statistiques réelles pour vérification
                st.markdown("**📊 Vérification des valeurs réelles dans le DataFrame:**")
                st.markdown(f"""
                - Cumul minimum: **{min_cumul:,.2f} EUR**
                - Cumul maximum: **{max_cumul:,.2f} EUR**
                - Jours avec cumul < 0: **{days_negative} jours**
                - Jours avec cumul < -100k: **{days_critical} jours**
                - Jours avec cumul entre -100k et 0: **{days_warning} jours**
                """)
                
                # Comparer avec les risk_zones calculés
                if days_negative != (forecast_results['risk_zones']['Warning'] + forecast_results['risk_zones']['Critical']):
                    st.error(f"⚠️ **INCOHÉRENCE DÉTECTÉE**: Le DataFrame contient {days_negative} jours négatifs, mais risk_zones indique {forecast_results['risk_zones']['Warning'] + forecast_results['risk_zones']['Critical']} jours (Warning + Critical)")
                if days_critical != forecast_results['risk_zones']['Critical']:
                    st.error(f"⚠️ **INCOHÉRENCE DÉTECTÉE**: Le DataFrame contient {days_critical} jours en Critical, mais risk_zones indique {forecast_results['risk_zones']['Critical']} jours")
                if days_warning != forecast_results['risk_zones']['Warning']:
                    st.error(f"⚠️ **INCOHÉRENCE DÉTECTÉE**: Le DataFrame contient {days_warning} jours en Warning, mais risk_zones indique {forecast_results['risk_zones']['Warning']} jours")
            
            # Calculer les zones de risque basées sur le SOLDE NET (cash - dette)
            if 'Cumul_Net_EUR' in forecast_results['forecast_df'].columns:
                days_net_critical = len(forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Net_EUR'] < -100000])
                days_net_warning = len(forecast_results['forecast_df'][(forecast_results['forecast_df']['Cumul_Net_EUR'] < 0) & (forecast_results['forecast_df']['Cumul_Net_EUR'] >= -100000)])
                days_net_safe = len(forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Net_EUR'] >= 0])
                min_cumul_net = forecast_results['forecast_df']['Cumul_Net_EUR'].min()
            else:
                days_net_critical = days_net_warning = days_net_safe = 0
                min_cumul_net = forecast_results.get('initial_balance_net', forecast_results['initial_balance'] - DEBT_PRINCIPAL)
            
            # Afficher l'analyse principale basée sur le SOLDE NET (plus réaliste avec la dette)
            # IMPORTANT: Les risk_zones sont maintenant calculés sur le solde net, pas sur le cash disponible
            st.error(f"""
            **🚨 ANALYSE PRINCIPALE - ZONES DE RISQUE (basées sur SOLDE NET = Cash - Dette de {DEBT_PRINCIPAL:,.0f} EUR):**
            
            - 🟢 Safe (Solde Net >= 0): {forecast_results['risk_zones']['Safe']} jours
            - 🟡 Warning (Solde Net < 0 mais >= -100k): {forecast_results['risk_zones']['Warning']} jours
            - 🔴 Critical (Solde Net < -100k): {forecast_results['risk_zones']['Critical']} jours
            
            **Solde Net Minimum**: {min_cumul_net:,.2f} EUR
            
            **Seuils (Solde Net):**
            - 🟢 Safe: Solde Net >= 0 EUR
            - 🟡 Warning: Solde Net < 0 EUR mais >= -100,000 EUR
            - 🔴 Critical: Solde Net < -100,000 EUR
            
            ⚠️ **IMPORTANT**: Cette analyse tient compte de la dette de 20M EUR. 
            Même si le cash disponible reste positif (~6-8M EUR), le solde net est très négatif (~-13.6M EUR), 
            indiquant une **situation financière CRITIQUE**.
            """)
            
            # Afficher l'analyse complémentaire basée sur le CASH DISPONIBLE (information de liquidité)
            st.info(f"""
            **💧 ANALYSE COMPLÉMENTAIRE - LIQUIDITÉ DISPONIBLE (Cash Disponible uniquement):**
            
            - 🟢 Safe (Cash >= 0): {len(forecast_results['forecast_df'][forecast_results['forecast_df']['Cumul_Total_EUR'] >= 0])} jours
            - 🟡 Warning (Cash < 0 mais >= -100k): {days_warning_cash if 'days_warning_cash' in locals() else 0} jours
            - 🔴 Critical (Cash < -100k): {days_critical_cash if 'days_critical_cash' in locals() else 0} jours
            
            **Cash Disponible Minimum**: {min_cumul:,.2f} EUR
            **Cash Disponible Maximum**: {max_cumul:,.2f} EUR
            
            💡 **Note**: Cette analyse montre la liquidité disponible (cash en banque), 
            mais ne reflète pas la situation financière réelle car elle ignore la dette de 20M EUR.
            """)
            
            # Télécharger CSV
            csv = forecast_results['forecast_df'].to_csv(index=False)
            st.download_button(
                label="📥 Télécharger le Forecast (CSV)",
                data=csv,
                file_name=f"forecast_{start_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
                
            st.markdown("---")
            
            # ========================================================================
            # ANALYSE PAR DATE SPÉCIFIQUE AVEC RECOMMANDATIONS
            # ========================================================================
            st.markdown("### 🎯 Analyse par Date Spécifique")
            
            st.markdown("""
            **Sélectionnez une date pour analyser la situation de trésorerie à ce moment précis
            et recevoir des recommandations personnalisées.**
            """)
            
            # Sélecteur de date
            selected_date = st.date_input(
                "📅 Choisir une date à analyser:",
                value=start_date,
                min_value=start_date,
                max_value=forecast_results['end_date']
            )
            
            # Trouver les données pour cette date
            selected_day_data = forecast_results['forecast_df'][forecast_results['forecast_df']['Date'] == selected_date.strftime('%Y-%m-%d')]
            
            # Récupérer avg_daily_credit et avg_daily_debit depuis les données du forecast ou les recalculer
            # Ces valeurs sont nécessaires pour les recommandations
            if 'avg_daily_credit' not in locals() or 'avg_daily_debit' not in locals():
                # Recalculer depuis les données bancaires
                avg_daily_credit = bank[bank['type']=='credit']['amount_eur'].mean() if len(bank[bank['type']=='credit']) > 0 else 0
                avg_daily_debit = bank[bank['type']=='debit']['amount_eur'].mean() if len(bank[bank['type']=='debit']) > 0 else 0
            
            if len(selected_day_data) > 0:
                selected_day = selected_day_data.iloc[0]
                selected_cumul = selected_day['Cumul_Total_EUR']
                selected_net = selected_day['Cash_Flow_Net']
                
                # Récupérer les valeurs par devise
                selected_cumul_eur = selected_day.get('Cumul_EUR', selected_cumul * 0.86)  # Fallback si colonne absente
                selected_cumul_usd = selected_day.get('Cumul_USD', 0)
                selected_cumul_jpy = selected_day.get('Cumul_JPY', 0)
                selected_net_eur = selected_day.get('Cash_Flow_Net_EUR', selected_net * 0.86)
                selected_net_usd = selected_day.get('Cash_Flow_Net_USD', 0)
                selected_net_jpy = selected_day.get('Cash_Flow_Net_JPY', 0)
                selected_credit_eur = selected_day.get('Encaissements_EUR', selected_day['Encaissements'] * 0.86)
                selected_credit_usd = selected_day.get('Encaissements_USD', 0)
                selected_credit_jpy = selected_day.get('Encaissements_JPY', 0)
                selected_debit_eur = selected_day.get('Décaissements_EUR', selected_day['Décaissements'] * 0.86)
                selected_debit_usd = selected_day.get('Décaissements_USD', 0)
                selected_debit_jpy = selected_day.get('Décaissements_JPY', 0)
                
                # Récupérer les taux de change pour les conversions
                fx_rates_current = get_real_exchange_rates()
                usd_rate_display = fx_rates_current.get('USD', 0.92)
                jpy_rate_display = fx_rates_current.get('JPY', 0.0065)
                
                # Analyser les jours autour (7 jours avant et après, si disponibles)
                # IMPORTANT: forecast_results['forecast_df'] contient déjà uniquement les jours jusqu'à la date de fin choisie
                selected_idx = forecast_results['forecast_df'][forecast_results['forecast_df']['Date'] == selected_date.strftime('%Y-%m-%d')].index[0]
                # window_start : 7 jours avant (ou 0 si on est au début du forecast)
                window_start = max(0, selected_idx - 7)
                # window_end : date sélectionnée + 7 jours après, mais pas au-delà de la fin du forecast
                # Iloc exclut le dernier, donc +8 pour inclure jusqu'à selected_idx + 7
                # Mais on s'arrête à la longueur réelle du DataFrame (qui respecte déjà la date de fin choisie)
                max_available_idx = len(forecast_results['forecast_df']) - 1
                window_end = min(max_available_idx + 1, selected_idx + 8)  # +1 car iloc exclut le dernier
                # Extraire la fenêtre (inclut window_start jusqu'à window_end-1, donc inclut bien selected_idx)
                window_data = forecast_results['forecast_df'].iloc[window_start:window_end].copy()
                
                # Vérification supplémentaire : s'assurer qu'on ne dépasse pas la date de fin du forecast
                end_date_str = forecast_results['end_date'].strftime('%Y-%m-%d')
                window_data = window_data[window_data['Date'] <= end_date_str].copy()
                
                # Vérifier que la date sélectionnée est bien dans window_data
                if selected_date.strftime('%Y-%m-%d') not in window_data['Date'].values:
                    # Si la date n'est pas trouvée, l'ajouter manuellement
                    selected_row = forecast_results['forecast_df'][forecast_results['forecast_df']['Date'] == selected_date.strftime('%Y-%m-%d')].iloc[0:1]
                    window_data = pd.concat([window_data, selected_row]).drop_duplicates(subset=['Date'], keep='first').sort_values('Date').reset_index(drop=True)
                
                # Calculer le nombre réel de jours avant et après pour l'affichage
                # Trouver l'index de la date sélectionnée dans window_data
                selected_idx_in_window = window_data[window_data['Date'] == selected_date.strftime('%Y-%m-%d')].index[0]
                days_before_count = selected_idx_in_window  # Nombre de jours avant (index 0 à selected_idx_in_window - 1)
                days_after_count = len(window_data) - selected_idx_in_window - 1  # Nombre de jours après (selected_idx_in_window + 1 à la fin)
                
                # Calculer tendance (utiliser l'index dans window_data, pas l'index original)
                days_before = window_data[window_data.index < selected_idx_in_window]
                days_after = window_data[window_data.index > selected_idx_in_window]
                
                trend_before = days_before['Cumul_Total_EUR'].diff().mean() if len(days_before) > 1 else 0
                trend_after = days_after['Cumul_Total_EUR'].diff().mean() if len(days_after) > 1 else 0
                
                # Afficher métriques du jour (avec détails par devise)
                st.markdown(f"#### 📊 Situation au {selected_date.strftime('%d %B %Y')}")
                
                # Métriques principales (Total EUR)
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Cumul Trésorerie", f"{selected_cumul:,.2f} EUR", 
                             delta=f"{selected_cumul - forecast_results['initial_balance']:+,.2f} EUR" if forecast_results['initial_balance'] != 0 else None)
                with col2:
                    st.metric("Cash Flow Net", f"{selected_net:,.2f} EUR", 
                             delta="Positif" if selected_net > 0 else "Négatif")
                with col3:
                    st.metric("Encaissements", f"{selected_day['Encaissements']:,.2f} EUR")
                with col4:
                    st.metric("Décaissements", f"{selected_day['Décaissements']:,.2f} EUR")
                
                # Détails par devise
                st.markdown("##### 💱 Détails par Devise")
                col_eur, col_usd, col_jpy = st.columns(3)
                
                with col_eur:
                    st.markdown("**🇪🇺 EUR**")
                    st.metric("Cumul", f"{selected_cumul_eur:,.2f} EUR")
                    st.metric("Cash Flow Net", f"{selected_net_eur:,.2f} EUR")
                    st.metric("Encaissements", f"{selected_credit_eur:,.2f} EUR")
                    st.metric("Décaissements", f"{selected_debit_eur:,.2f} EUR")
                
                with col_usd:
                    st.markdown("**🇺🇸 USD**")
                    st.metric("Cumul", f"{selected_cumul_usd:,.2f} USD", 
                             help=f"Équivalent: {selected_cumul_usd * usd_rate_display:,.2f} EUR")
                    st.metric("Cash Flow Net", f"{selected_net_usd:,.2f} USD",
                             help=f"Équivalent: {selected_net_usd * usd_rate_display:,.2f} EUR")
                    st.metric("Encaissements", f"{selected_credit_usd:,.2f} USD",
                             help=f"Équivalent: {selected_credit_usd * usd_rate_display:,.2f} EUR")
                    st.metric("Décaissements", f"{selected_debit_usd:,.2f} USD",
                             help=f"Équivalent: {selected_debit_usd * usd_rate_display:,.2f} EUR")
                
                with col_jpy:
                    st.markdown("**🇯🇵 JPY**")
                    st.metric("Cumul", f"{selected_cumul_jpy:,.2f} JPY",
                             help=f"Équivalent: {selected_cumul_jpy * jpy_rate_display:,.2f} EUR")
                    st.metric("Cash Flow Net", f"{selected_net_jpy:,.2f} JPY",
                             help=f"Équivalent: {selected_net_jpy * jpy_rate_display:,.2f} EUR")
                    st.metric("Encaissements", f"{selected_credit_jpy:,.2f} JPY",
                             help=f"Équivalent: {selected_credit_jpy * jpy_rate_display:,.2f} EUR")
                    st.metric("Décaissements", f"{selected_debit_jpy:,.2f} JPY",
                             help=f"Équivalent: {selected_debit_jpy * jpy_rate_display:,.2f} EUR")
                
                # Graphique de contexte (15 jours autour)
                st.markdown("#### 📈 Contexte (15 jours autour)")
                # Convertir Date en datetime Python natif pour éviter les problèmes avec pandas Timestamp
                window_data_plot = window_data.copy()
                window_data_plot['Date_dt'] = pd.to_datetime(window_data_plot['Date']).apply(lambda x: x.to_pydatetime() if hasattr(x, 'to_pydatetime') else x)
                
                fig_context = px.line(
                    window_data_plot,
                    x='Date_dt',
                    y='Cumul_Total_EUR',
                    title=f"Évolution autour du {selected_date.strftime('%d %B %Y')}",
                    labels={'Cumul_Total_EUR': 'Cumul (EUR)', 'Date_dt': 'Date'}
                )
                # Utiliser add_shape au lieu de add_vline pour éviter les problèmes de type avec pandas Timestamp
                # Convertir la date sélectionnée en datetime Python natif compatible avec Plotly
                # Plotly attend un datetime ou une string ISO format
                selected_date_dt = pd.to_datetime(selected_date)
                # Convertir en string ISO pour éviter les problèmes de type
                selected_date_str = selected_date_dt.strftime('%Y-%m-%d')
                y_min = float(window_data_plot['Cumul_Total_EUR'].min())
                y_max = float(window_data_plot['Cumul_Total_EUR'].max())
                
                # Ajouter la ligne verticale en utilisant la date comme string ou timestamp
                # Utiliser directement la valeur de Date_dt correspondante pour éviter les problèmes de conversion
                selected_date_value = window_data_plot[window_data_plot['Date'] == selected_date.strftime('%Y-%m-%d')]['Date_dt'].iloc[0] if len(window_data_plot[window_data_plot['Date'] == selected_date.strftime('%Y-%m-%d')]) > 0 else selected_date_dt
                
                fig_context.add_shape(
                    type="line",
                    x0=selected_date_value,
                    x1=selected_date_value,
                    y0=y_min,
                    y1=y_max,
                    line=dict(color="red", width=2, dash="dash"),
                    xref="x",
                    yref="y"
                )
                # Ajouter une annotation pour la date
                fig_context.add_annotation(
                    x=selected_date_value,
                    y=y_max,
                    text=f"Date sélectionnée: {selected_date.strftime('%d/%m')}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor="red",
                    bgcolor="white",
                    bordercolor="red",
                    borderwidth=1,
                    xref="x",
                    yref="y"
                )
                fig_context.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_context.update_xaxes(tickangle=45)
                st.plotly_chart(fig_context, width='stretch')
                
                # Recommandations personnalisées avec logique détaillée et crédible
                st.markdown("#### 💡 Recommandations Personnalisées (avec Calculs et Justifications)")
                
                # IMPORTANT: Calculer les métriques pour la période complète jusqu'à la fin du forecast
                end_date = forecast_results['end_date']
                days_until_end = (end_date - selected_date).days
                
                # Analyser la période restante du forecast
                remaining_forecast = forecast_results['forecast_df'][forecast_results['forecast_df']['Date'] > selected_date.strftime('%Y-%m-%d')].copy()
                if len(remaining_forecast) > 0:
                    # Tendance jusqu'à la fin
                    final_balance = forecast_results['final_balance']
                    projected_change = final_balance - selected_cumul
                    avg_daily_change_remaining = projected_change / days_until_end if days_until_end > 0 else 0
                    
                    # Trouver le jour le plus bas dans la période restante
                    if 'Cumul_Total_EUR' in remaining_forecast.columns:
                        worst_remaining = remaining_forecast.loc[remaining_forecast['Cumul_Total_EUR'].idxmin()]
                        worst_remaining_balance = worst_remaining['Cumul_Total_EUR']
                        worst_remaining_date = worst_remaining['Date']
                        days_until_worst_remaining = (pd.to_datetime(worst_remaining_date) - pd.to_datetime(selected_date.strftime('%Y-%m-%d'))).days
                    else:
                        worst_remaining_balance = final_balance
                        worst_remaining_date = end_date.strftime('%Y-%m-%d')
                        days_until_worst_remaining = days_until_end
                    
                    # Moyennes sur la période restante
                    avg_credit_remaining = remaining_forecast['Encaissements'].mean() if len(remaining_forecast) > 0 else avg_daily_credit
                    avg_debit_remaining = remaining_forecast['Décaissements'].mean() if len(remaining_forecast) > 0 else avg_daily_debit
                    avg_cash_flow_remaining = avg_credit_remaining - avg_debit_remaining
                else:
                    days_until_end = 0
                    final_balance = selected_cumul
                    projected_change = 0
                    avg_daily_change_remaining = 0
                    worst_remaining_balance = selected_cumul
                    worst_remaining_date = selected_date.strftime('%Y-%m-%d')
                    days_until_worst_remaining = 0
                    avg_credit_remaining = selected_day['Encaissements']
                    avg_debit_remaining = selected_day['Décaissements']
                    avg_cash_flow_remaining = selected_day['Encaissements'] - selected_day['Décaissements']
                
                # Calculer des métriques pour les recommandations (dans les 3 devises)
                # Totaux en EUR équivalent
                cash_flow_gap = selected_day['Décaissements'] - selected_day['Encaissements']
                cash_flow_ratio = selected_day['Décaissements'] / selected_day['Encaissements'] if selected_day['Encaissements'] > 0 else float('inf')
                encaissement_vs_avg = (selected_day['Encaissements'] / avg_daily_credit - 1) * 100 if avg_daily_credit > 0 else 0
                decaissement_vs_avg = (selected_day['Décaissements'] / avg_daily_debit - 1) * 100 if avg_daily_debit > 0 else 0
                
                # Par devise
                cash_flow_gap_eur = selected_debit_eur - selected_credit_eur
                cash_flow_gap_usd = selected_debit_usd - selected_credit_usd
                cash_flow_gap_jpy = selected_debit_jpy - selected_credit_jpy
                
                # Calculer les moyennes historiques par devise
                if len(bank) > 0:
                    avg_daily_credit_eur = bank[(bank['type']=='credit') & (bank['currency']=='EUR')]['amount'].mean() if len(bank[(bank['type']=='credit') & (bank['currency']=='EUR')]) > 0 else avg_daily_credit * 0.86
                    avg_daily_credit_usd = bank[(bank['type']=='credit') & (bank['currency']=='USD')]['amount'].mean() if len(bank[(bank['type']=='credit') & (bank['currency']=='USD')]) > 0 else avg_daily_credit * 0.04 / usd_rate_display
                    avg_daily_credit_jpy = bank[(bank['type']=='credit') & (bank['currency']=='JPY')]['amount'].mean() if len(bank[(bank['type']=='credit') & (bank['currency']=='JPY')]) > 0 else avg_daily_credit * 0.14 / jpy_rate_display
                    
                    avg_daily_debit_eur = bank[(bank['type']=='debit') & (bank['currency']=='EUR')]['amount'].mean() if len(bank[(bank['type']=='debit') & (bank['currency']=='EUR')]) > 0 else avg_daily_debit * 0.86
                    avg_daily_debit_usd = bank[(bank['type']=='debit') & (bank['currency']=='USD')]['amount'].mean() if len(bank[(bank['type']=='debit') & (bank['currency']=='USD')]) > 0 else avg_daily_debit * 0.04 / usd_rate_display
                    avg_daily_debit_jpy = bank[(bank['type']=='debit') & (bank['currency']=='JPY')]['amount'].mean() if len(bank[(bank['type']=='debit') & (bank['currency']=='JPY')]) > 0 else avg_daily_debit * 0.14 / jpy_rate_display
                else:
                    avg_daily_credit_eur = avg_daily_credit * 0.86
                    avg_daily_credit_usd = avg_daily_credit * 0.04 / usd_rate_display
                    avg_daily_credit_jpy = avg_daily_credit * 0.14 / jpy_rate_display
                    avg_daily_debit_eur = avg_daily_debit * 0.86
                    avg_daily_debit_usd = avg_daily_debit * 0.04 / usd_rate_display
                    avg_daily_debit_jpy = avg_daily_debit * 0.14 / jpy_rate_display
                
                if selected_cumul < 0:
                    # Situation critique
                    st.error(f"🚨 **SITUATION CRITIQUE** - Cumul négatif: {selected_cumul:,.2f} EUR")
                    
                    # Trouver le jour le plus bas dans la fenêtre
                    worst_in_window = window_data.loc[window_data['Cumul_Total_EUR'].idxmin()]
                    worst_balance = worst_in_window['Cumul_Total_EUR']
                    days_until_worst = (pd.to_datetime(worst_in_window['Date']) - pd.to_datetime(selected_date.strftime('%Y-%m-%d'))).days
                    deficit_amount = abs(selected_cumul)
                    
                    st.markdown("""
                    <div style="background-color: #ffebee; padding: 20px; border-radius: 10px; border-left: 5px solid #d32f2f; color: #721c24;">
                    <h4>⚠️ ACTIONS IMMÉDIATES (à appliquer AVANT le {})</h4>
                    """.format(selected_date.strftime('%d %B')), unsafe_allow_html=True)
                    
                    recommendations_critical = []
                    
                    # ANALYSE QUANTIFIÉE DE LA SITUATION (dans les 3 devises)
                    recommendations_critical.append("**📊 ANALYSE DE LA SITUATION (Multi-Devises):**")
                    recommendations_critical.append(f"• Déficit actuel (Total EUR): **{deficit_amount:,.2f} EUR**")
                    recommendations_critical.append(f"  - EUR: {selected_cumul_eur:,.2f} EUR")
                    recommendations_critical.append(f"  - USD: {selected_cumul_usd:,.2f} USD ({selected_cumul_usd * usd_rate_display:,.2f} EUR)")
                    recommendations_critical.append(f"  - JPY: {selected_cumul_jpy:,.2f} JPY ({selected_cumul_jpy * jpy_rate_display:,.2f} EUR)")
                    recommendations_critical.append(f"• Jour le plus bas prévu: **{worst_in_window['Date']}** (solde: {worst_balance:,.2f} EUR)")
                    recommendations_critical.append(f"• Délai avant le point le plus bas: **{days_until_worst} jours**")
                    recommendations_critical.append(f"• Écart quotidien moyen (Total EUR): **{cash_flow_gap:,.2f} EUR/jour**")
                    recommendations_critical.append(f"  - EUR: {cash_flow_gap_eur:,.2f} EUR/jour")
                    recommendations_critical.append(f"  - USD: {cash_flow_gap_usd:,.2f} USD/jour ({cash_flow_gap_usd * usd_rate_display:,.2f} EUR/jour)")
                    recommendations_critical.append(f"  - JPY: {cash_flow_gap_jpy:,.2f} JPY/jour ({cash_flow_gap_jpy * jpy_rate_display:,.2f} EUR/jour)")
                    
                    # Actions selon le temps restant avec calculs
                    if days_until_worst > 0:
                        urgent_days = min(days_until_worst, 7)
                        recommendations_critical.append(f"\n⏰ **URGENT (dans les {urgent_days} prochains jours):**")
                        
                        # Calcul du besoin de financement
                        if days_until_worst <= 7:
                            estimated_need = abs(worst_balance) + (cash_flow_gap * days_until_worst)
                        else:
                            estimated_need = abs(selected_cumul) + (cash_flow_gap * 7)
                        
                        recommendations_critical.append(f"**1. Ligne de crédit / Découvert:**")
                        recommendations_critical.append(f"   • Besoin estimé: **{estimated_need:,.0f} EUR**")
                        recommendations_critical.append(f"   • Coût estimé: {estimated_need * 0.06 / 12:,.0f} EUR/mois (taux 6% annuel)")
                        recommendations_critical.append(f"   • Action: Négocier immédiatement avec la banque")
                        
                        # Calcul de l'impact de l'accélération des encaissements (par devise)
                        if selected_day['Encaissements'] < avg_daily_credit:
                            potential_improvement = (avg_daily_credit - selected_day['Encaissements']) * urgent_days
                            # Par devise
                            potential_eur = (avg_daily_credit_eur - selected_credit_eur) * urgent_days if selected_credit_eur < avg_daily_credit_eur else 0
                            potential_usd = (avg_daily_credit_usd - selected_credit_usd) * urgent_days if selected_credit_usd < avg_daily_credit_usd else 0
                            potential_jpy = (avg_daily_credit_jpy - selected_credit_jpy) * urgent_days if selected_credit_jpy < avg_daily_credit_jpy else 0
                            
                            recommendations_critical.append(f"\n**2. Accélération des encaissements (Multi-Devises):**")
                            recommendations_critical.append(f"   • Potentiel total: **{potential_improvement:,.0f} EUR** sur {urgent_days} jours")
                            recommendations_critical.append(f"     - EUR: {potential_eur:,.0f} EUR")
                            recommendations_critical.append(f"     - USD: {potential_usd:,.0f} USD ({potential_usd * usd_rate_display:,.0f} EUR)")
                            recommendations_critical.append(f"     - JPY: {potential_jpy:,.0f} JPY ({potential_jpy * jpy_rate_display:,.0f} EUR)")
                            recommendations_critical.append(f"   • Méthode: Relances téléphoniques quotidiennes + escomptes 2% pour paiement anticipé")
                            recommendations_critical.append(f"   • Coût escomptes: {potential_improvement * 0.02:,.0f} EUR (2% du montant)")
                            recommendations_critical.append(f"   • Gain net: {potential_improvement * 0.98:,.0f} EUR")
                        
                        # Calcul de l'impact du report des paiements (par devise)
                        if selected_day['Décaissements'] > avg_daily_debit:
                            deferrable_amount = (selected_day['Décaissements'] - avg_daily_debit) * 0.3  # 30% reportables
                            # Par devise
                            deferrable_eur = (selected_debit_eur - avg_daily_debit_eur) * 0.3 if selected_debit_eur > avg_daily_debit_eur else 0
                            deferrable_usd = (selected_debit_usd - avg_daily_debit_usd) * 0.3 if selected_debit_usd > avg_daily_debit_usd else 0
                            deferrable_jpy = (selected_debit_jpy - avg_daily_debit_jpy) * 0.3 if selected_debit_jpy > avg_daily_debit_jpy else 0
                            
                            recommendations_critical.append(f"\n**3. Report des paiements non urgents (Multi-Devises):**")
                            recommendations_critical.append(f"   • Montant reportable total: **{deferrable_amount:,.0f} EUR** (30% des décaissements excédentaires)")
                            recommendations_critical.append(f"     - EUR: {deferrable_eur:,.0f} EUR")
                            recommendations_critical.append(f"     - USD: {deferrable_usd:,.0f} USD ({deferrable_usd * usd_rate_display:,.0f} EUR)")
                            recommendations_critical.append(f"     - JPY: {deferrable_jpy:,.0f} JPY ({deferrable_jpy * jpy_rate_display:,.0f} EUR)")
                            recommendations_critical.append(f"   • Impact: Libération immédiate de trésorerie")
                    
                    if days_until_worst > 7:
                        recommendations_critical.append(f"\n📅 **AVANT le {worst_in_window['Date']} (actions préventives):**")
                        
                        # Calcul de l'impact de la réduction des dépenses
                        if selected_day['Décaissements'] > avg_daily_debit * 1.1:
                            excess_debit = selected_day['Décaissements'] - avg_daily_debit
                            reducible_amount = excess_debit * 0.2  # 20% réductible
                            recommendations_critical.append(f"**1. Réduction des dépenses non essentielles:**")
                            recommendations_critical.append(f"   • Dépenses excédentaires: {excess_debit:,.0f} EUR/jour")
                            recommendations_critical.append(f"   • Potentiel de réduction: **{reducible_amount:,.0f} EUR/jour** (20% des dépenses excédentaires)")
                            recommendations_critical.append(f"   • Impact sur {days_until_worst} jours: {reducible_amount * days_until_worst:,.0f} EUR")
                        
                        # Calcul de l'impact de l'extension DPO
                        if dpo_mean < 60:  # Si DPO est inférieur à 60 jours
                            dpo_extension = min(10, 60 - dpo_mean)  # Extension de 10 jours max
                            avg_daily_purchase = selected_day['Décaissements'] if selected_day['Décaissements'] > 0 else avg_daily_debit * 0.5
                            dpo_benefit = avg_daily_purchase * dpo_extension
                            recommendations_critical.append(f"\n**2. Extension des délais fournisseurs (DPO):**")
                            recommendations_critical.append(f"   • DPO actuel: {dpo_mean:.1f} jours")
                            recommendations_critical.append(f"   • Extension possible: +{dpo_extension} jours")
                            recommendations_critical.append(f"   • Libération de trésorerie: **{dpo_benefit:,.0f} EUR**")
                            recommendations_critical.append(f"   • Action: Négocier avec les 5 principaux fournisseurs")
                    
                    # Analyser les encaissements/décaissements avec calculs
                    if cash_flow_ratio > 1.5:
                        recommendations_critical.append(f"\n💰 **OPTIMISATION DES DÉCAISSEMENTS (Ratio: {cash_flow_ratio:.2f}x):**")
                        recommendations_critical.append(f"   • Les décaissements sont **{int((cash_flow_ratio - 1) * 100)}%** supérieurs aux encaissements")
                        recommendations_critical.append(f"   • Écart quotidien: **{cash_flow_gap:,.2f} EUR**")
                        recommendations_critical.append(f"   • Priorité: Identifier les paiements reportables (30% estimé = {cash_flow_gap * 0.3:,.0f} EUR/jour)")
                    
                    if encaissement_vs_avg < -30:
                        recommendations_critical.append(f"\n📈 **AMÉLIORATION DES ENCAISSEMENTS ({encaissement_vs_avg:.1f}% vs moyenne):**")
                        recommendations_critical.append(f"   • Encaissements actuels: {selected_day['Encaissements']:,.2f} EUR")
                        recommendations_critical.append(f"   • Moyenne historique: {avg_daily_credit:,.2f} EUR")
                        recommendations_critical.append(f"   • Écart: **{avg_daily_credit - selected_day['Encaissements']:,.2f} EUR/jour**")
                        recommendations_critical.append(f"   • Action: Relances actives + escomptes 2% pour paiement sous 10 jours")
                        recommendations_critical.append(f"   • Impact estimé: Récupération de 50% de l'écart = {(avg_daily_credit - selected_day['Encaissements']) * 0.5:,.0f} EUR/jour")
                    
                    st.markdown("\n".join(recommendations_critical))
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                elif selected_cumul < 50000:
                    # Situation d'alerte - Seuil: < 50,000 EUR (justification: réserve minimale de sécurité)
                    st.warning(f"⚠️ **SITUATION D'ALERTE** - Cumul faible: {selected_cumul:,.2f} EUR")
                    
                    st.markdown("""
                    <div style="background-color: #fff3e0; padding: 20px; border-radius: 10px; border-left: 5px solid #ff9800; color: #856404;">
                    <h4>📋 ACTIONS PRÉVENTIVES (Seuil d'alerte: < 50,000 EUR)</h4>
                    """, unsafe_allow_html=True)
                    
                    recommendations_warning = []
                    
                    # ANALYSE QUANTIFIÉE (Multi-Devises)
                    buffer_needed = 50000 - selected_cumul
                    recommendations_warning.append("**📊 ANALYSE DE LA SITUATION (Multi-Devises):**")
                    recommendations_warning.append(f"• Solde actuel (Total EUR): **{selected_cumul:,.2f} EUR**")
                    recommendations_warning.append(f"  - EUR: {selected_cumul_eur:,.2f} EUR")
                    recommendations_warning.append(f"  - USD: {selected_cumul_usd:,.2f} USD ({selected_cumul_usd * usd_rate_display:,.2f} EUR)")
                    recommendations_warning.append(f"  - JPY: {selected_cumul_jpy:,.2f} JPY ({selected_cumul_jpy * jpy_rate_display:,.2f} EUR)")
                    recommendations_warning.append(f"• Seuil d'alerte: 50,000 EUR (réserve minimale recommandée)")
                    recommendations_warning.append(f"• Écart au seuil: **{buffer_needed:,.2f} EUR**")
                    recommendations_warning.append(f"• Ratio sécurité: {selected_cumul / 50000 * 100:.1f}% du seuil minimum")
                    
                    # Calcul du besoin de financement préventif
                    if trend_after < -1000:
                        days_to_zero = abs(selected_cumul / trend_after) if trend_after < 0 else 999
                        estimated_deficit = abs(trend_after) * 30  # Sur 30 jours
                        recommendations_warning.append(f"\n📉 **TENDANCE NÉGATIVE DÉTECTÉE:**")
                        recommendations_warning.append(f"   • Tendance: {trend_after:,.0f} EUR/jour")
                        recommendations_warning.append(f"   • Projection 30 jours: Déficit estimé de **{estimated_deficit:,.0f} EUR**")
                        recommendations_warning.append(f"   • Temps estimé avant seuil critique: {days_to_zero:.0f} jours")
                    
                    recommendations_warning.append(f"\n**1. Ligne de crédit de précaution:**")
                    recommendations_warning.append(f"   • Montant recommandé: **{max(buffer_needed, 100000):,.0f} EUR** (minimum 100k pour flexibilité)")
                    recommendations_warning.append(f"   • Coût estimé: {max(buffer_needed, 100000) * 0.05 / 12:,.0f} EUR/mois (taux 5% annuel, non utilisée)")
                    recommendations_warning.append(f"   • Avantage: Disponibilité immédiate sans coût si non utilisée")
                    
                    # Optimisation DPO avec calcul
                    if dpo_mean < 50:
                        dpo_improvement = min(10, 50 - dpo_mean)
                        avg_monthly_purchase = avg_daily_debit * 30
                        dpo_benefit = (avg_monthly_purchase / 30) * dpo_improvement
                        recommendations_warning.append(f"\n**2. Optimisation des délais fournisseurs (DPO):**")
                        recommendations_warning.append(f"   • DPO actuel: {dpo_mean:.1f} jours")
                        recommendations_warning.append(f"   • Amélioration possible: +{dpo_improvement} jours")
                        recommendations_warning.append(f"   • Libération de trésorerie: **{dpo_benefit:,.0f} EUR**")
                        recommendations_warning.append(f"   • ROI: Négociation gratuite, impact immédiat")
                    
                    # Amélioration DSO avec calcul
                    if dso_mean > 40:
                        dso_improvement = min(5, dso_mean - 40)
                        avg_monthly_sales = avg_daily_credit * 30
                        dso_benefit = (avg_monthly_sales / 30) * dso_improvement
                        recommendations_warning.append(f"\n**3. Accélération du recouvrement (DSO):**")
                        recommendations_warning.append(f"   • DSO actuel: {dso_mean:.1f} jours")
                        recommendations_warning.append(f"   • Réduction possible: -{dso_improvement} jours")
                        recommendations_warning.append(f"   • Libération de trésorerie: **{dso_benefit:,.0f} EUR**")
                        recommendations_warning.append(f"   • Action: Relances proactives + escomptes 1.5% pour paiement anticipé")
                        recommendations_warning.append(f"   • Coût escomptes: {dso_benefit * 0.015:,.0f} EUR")
                        recommendations_warning.append(f"   • Gain net: {dso_benefit * 0.985:,.0f} EUR")
                    
                    st.markdown("\n".join(recommendations_warning))
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                else:
                    # Situation positive - Seuil: >= 50,000 EUR
                    st.success(f"✅ **SITUATION POSITIVE** - Cumul: {selected_cumul:,.2f} EUR")
                    
                    st.markdown("""
                    <div style="background-color: #e8f5e9; padding: 20px; border-radius: 10px; border-left: 5px solid #4caf50; color: #155724;">
                    <h4>🚀 OPPORTUNITÉS D'AMÉLIORATION</h4>
                    """, unsafe_allow_html=True)
                    
                    recommendations_positive = []
                    
                    # ANALYSE QUANTIFIÉE
                    excess_cash = selected_cumul - 50000  # Excédent au-dessus du seuil de sécurité
                    recommendations_positive.append("**📊 ANALYSE DE LA SITUATION:**")
                    recommendations_positive.append(f"• Solde actuel: **{selected_cumul:,.2f} EUR**")
                    recommendations_positive.append(f"• Excédent disponible: **{excess_cash:,.2f} EUR** (au-dessus du seuil de 50k)")
                    recommendations_positive.append(f"• Ratio de sécurité: {selected_cumul / 50000 * 100:.1f}% du seuil minimum")
                    
                    # IMPORTANT: Analyser la période jusqu'à la fin du forecast
                    if days_until_end > 0:
                        recommendations_positive.append(f"\n📅 **ANALYSE DE LA PÉRIODE RESTANTE (jusqu'au {end_date.strftime('%d %B %Y')}):**")
                        recommendations_positive.append(f"   • Jours restants: **{days_until_end} jours**")
                        recommendations_positive.append(f"   • Solde final prévu: **{final_balance:,.2f} EUR**")
                        recommendations_positive.append(f"   • Variation prévue: **{projected_change:+,.2f} EUR** ({projected_change/selected_cumul*100:+.1f}%)")
                        recommendations_positive.append(f"   • Variation quotidienne moyenne: **{avg_daily_change_remaining:+,.2f} EUR/jour**")
                        
                        # Analyser la tendance
                        if avg_daily_change_remaining < -1000:
                            recommendations_positive.append(f"   ⚠️ **TENDANCE NÉGATIVE**: Le solde va diminuer de {abs(projected_change):,.0f} EUR d'ici la fin du forecast")
                            recommendations_positive.append(f"   • Action recommandée: Prendre des mesures préventives maintenant")
                        elif avg_daily_change_remaining > 1000:
                            recommendations_positive.append(f"   ✅ **TENDANCE POSITIVE**: Le solde va augmenter de {projected_change:,.0f} EUR d'ici la fin du forecast")
                        else:
                            recommendations_positive.append(f"   ➡️ **TENDANCE STABLE**: Le solde reste relativement stable")
                        
                        # Analyser le jour le plus bas dans la période restante
                        if worst_remaining_balance < selected_cumul:
                            recommendations_positive.append(f"   ⚠️ **POINT BAS PRÉVU**: {worst_remaining_date} (solde: {worst_remaining_balance:,.2f} EUR)")
                            recommendations_positive.append(f"   • Délai: {days_until_worst_remaining} jours")
                            if worst_remaining_balance < 0:
                                recommendations_positive.append(f"   🚨 **ALERTE**: Le solde deviendra négatif avant la fin du forecast !")
                                recommendations_positive.append(f"   • Action URGENTE: Mettre en place des mesures de financement")
                            elif worst_remaining_balance < 50000:
                                recommendations_positive.append(f"   ⚠️ **ALERTE**: Le solde passera sous le seuil de sécurité (50k EUR)")
                                recommendations_positive.append(f"   • Action: Prévoir une ligne de crédit de précaution")
                    
                    if selected_net > 0:
                        recommendations_positive.append(f"\n✅ **CASH FLOW NET POSITIF:** {selected_net:,.2f} EUR/jour")
                        recommendations_positive.append(f"   • Projection 30 jours: +{selected_net * 30:,.0f} EUR")
                        recommendations_positive.append(f"   • Action: Maintenir cette dynamique")
                    
                    if trend_after > 1000:
                        projected_improvement = trend_after * 30
                        recommendations_positive.append(f"\n📈 **TENDANCE POSITIVE:** {trend_after:,.0f} EUR/jour")
                        recommendations_positive.append(f"   • Projection 30 jours: +{projected_improvement:,.0f} EUR")
                        recommendations_positive.append(f"   • Opportunité: Investir ou rembourser dettes")
                    
                    # Optimisations avec calculs ROI (Multi-Devises)
                    if encaissement_vs_avg < 20:  # Si en dessous de 20% de la moyenne
                        improvement_potential = (avg_daily_credit * 1.2 - selected_day['Encaissements']) * 30
                        # Par devise
                        improvement_eur = (avg_daily_credit_eur * 1.2 - selected_credit_eur) * 30 if selected_credit_eur < avg_daily_credit_eur * 1.2 else 0
                        improvement_usd = (avg_daily_credit_usd * 1.2 - selected_credit_usd) * 30 if selected_credit_usd < avg_daily_credit_usd * 1.2 else 0
                        improvement_jpy = (avg_daily_credit_jpy * 1.2 - selected_credit_jpy) * 30 if selected_credit_jpy < avg_daily_credit_jpy * 1.2 else 0
                        
                        recommendations_positive.append(f"\n💰 **OPTIMISATION DES ENCAISSEMENTS ({encaissement_vs_avg:.1f}% vs moyenne - Multi-Devises):**")
                        recommendations_positive.append(f"   • Potentiel total: **{improvement_potential:,.0f} EUR** sur 30 jours")
                        recommendations_positive.append(f"     - EUR: {improvement_eur:,.0f} EUR")
                        recommendations_positive.append(f"     - USD: {improvement_usd:,.0f} USD ({improvement_usd * usd_rate_display:,.0f} EUR)")
                        recommendations_positive.append(f"     - JPY: {improvement_jpy:,.0f} JPY ({improvement_jpy * jpy_rate_display:,.0f} EUR)")
                        recommendations_positive.append(f"   • Méthode: Négocier paiements J+15 au lieu de J+{dso_mean:.0f}")
                        recommendations_positive.append(f"   • Coût: Escomptes 1% = {improvement_potential * 0.01:,.0f} EUR")
                        recommendations_positive.append(f"   • Gain net: {improvement_potential * 0.99:,.0f} EUR")
                    
                    if decaissement_vs_avg > 10:
                        reduction_potential = (selected_day['Décaissements'] - avg_daily_debit) * 0.15 * 30  # 15% réductible
                        # Par devise
                        excess_debit_eur = max(0, selected_debit_eur - avg_daily_debit_eur)
                        excess_debit_usd = max(0, selected_debit_usd - avg_daily_debit_usd)
                        excess_debit_jpy = max(0, selected_debit_jpy - avg_daily_debit_jpy)
                        reduction_eur = excess_debit_eur * 0.15 * 30
                        reduction_usd = excess_debit_usd * 0.15 * 30
                        reduction_jpy = excess_debit_jpy * 0.15 * 30
                        
                        recommendations_positive.append(f"\n💸 **OPTIMISATION DES DÉCAISSEMENTS (+{decaissement_vs_avg:.1f}% vs moyenne - Multi-Devises):**")
                        recommendations_positive.append(f"   • Dépenses excédentaires (Total): {selected_day['Décaissements'] - avg_daily_debit:,.2f} EUR/jour")
                        recommendations_positive.append(f"     - EUR: {excess_debit_eur:,.2f} EUR/jour")
                        recommendations_positive.append(f"     - USD: {excess_debit_usd:,.2f} USD/jour ({excess_debit_usd * usd_rate_display:,.2f} EUR/jour)")
                        recommendations_positive.append(f"     - JPY: {excess_debit_jpy:,.2f} JPY/jour ({excess_debit_jpy * jpy_rate_display:,.2f} EUR/jour)")
                        recommendations_positive.append(f"   • Potentiel de réduction total: **{reduction_potential:,.0f} EUR** sur 30 jours (15% réductible)")
                        recommendations_positive.append(f"     - EUR: {reduction_eur:,.0f} EUR")
                        recommendations_positive.append(f"     - USD: {reduction_usd:,.0f} USD ({reduction_usd * usd_rate_display:,.0f} EUR)")
                        recommendations_positive.append(f"     - JPY: {reduction_jpy:,.0f} JPY ({reduction_jpy * jpy_rate_display:,.0f} EUR)")
                        recommendations_positive.append(f"   • Action: Négocier meilleurs termes avec top 10 fournisseurs")
                    
                    # ACTIONS STRATÉGIQUES avec calculs ROI
                    # IMPORTANT: Ajuster les recommandations selon la période restante et la tendance
                    if excess_cash > 100000:
                        # Si la tendance est négative, garder plus de liquidité
                        if avg_daily_change_remaining < -1000 and days_until_end > 30:
                            # Réduire les placements et garder plus de liquidité
                            liquidity_ratio = 0.4  # 40% en liquidité au lieu de 20%
                            investment_ratio = 0.2  # 20% en placements au lieu de 30%
                            debt_ratio = 0.4  # 40% en remboursement dette
                        else:
                            # Allocation normale
                            liquidity_ratio = 0.2
                            investment_ratio = 0.3
                            debt_ratio = 0.5
                        
                        recommendations_positive.append(f"\n🎯 **ACTIONS STRATÉGIQUES (Excédent: {excess_cash:,.0f} EUR):**")
                        if days_until_end > 0:
                            recommendations_positive.append(f"   📅 **Période analysée**: {days_until_end} jours jusqu'au {end_date.strftime('%d %B %Y')}")
                            if avg_daily_change_remaining < -1000:
                                recommendations_positive.append(f"   ⚠️ **Allocation prudente** (tendance négative détectée)")
                        
                        # Remboursement anticipé dette
                        debt_payback_amount = min(excess_cash * debt_ratio, 1_000_000)  # Max 1M
                        interest_savings = debt_payback_amount * DEBT_INTEREST_RATE
                        recommendations_positive.append(f"\n**1. Remboursement anticipé dette:**")
                        recommendations_positive.append(f"   • Montant recommandé: **{debt_payback_amount:,.0f} EUR** ({debt_ratio*100:.0f}% de l'excédent)")
                        recommendations_positive.append(f"   • Économie d'intérêts: **{interest_savings:,.0f} EUR/an** (taux {DEBT_INTEREST_RATE*100:.2f}%)")
                        recommendations_positive.append(f"   • ROI: {DEBT_INTEREST_RATE*100:.2f}% garanti (meilleur que placements)")
                        
                        # Placements (ajustés selon la tendance)
                        investment_amount = excess_cash * investment_ratio
                        term_deposit_return = investment_amount * 0.0075  # 0.75% sur 6 mois
                        money_market_return = investment_amount * 0.004  # 0.4% liquidité quotidienne
                        recommendations_positive.append(f"\n**2. Placements de trésorerie:**")
                        recommendations_positive.append(f"   • Montant recommandé: **{investment_amount:,.0f} EUR** ({investment_ratio*100:.0f}% de l'excédent)")
                        recommendations_positive.append(f"   • Option A - Compte à terme 6 mois: {term_deposit_return:,.0f} EUR (0.75% annuel)")
                        recommendations_positive.append(f"   • Option B - Fonds monétaire: {money_market_return:,.0f} EUR/an (0.4% annuel, liquidité quotidienne)")
                        recommendations_positive.append(f"   • Recommandation: Mix 50/50 pour équilibrer rendement/liquidité")
                        
                        # Réserve de sécurité (ajustée selon la tendance)
                        reserve_amount = excess_cash * liquidity_ratio
                        recommendations_positive.append(f"\n**3. Réserve de sécurité:**")
                        recommendations_positive.append(f"   • Montant recommandé: **{reserve_amount:,.0f} EUR** ({liquidity_ratio*100:.0f}% de l'excédent)")
                        recommendations_positive.append(f"   • Objectif: 3 mois de charges d'exploitation")
                        recommendations_positive.append(f"   • Placement: Fonds monétaire (liquidité immédiate)")
                        if avg_daily_change_remaining < -1000:
                            recommendations_positive.append(f"   ⚠️ **Note**: Réserve augmentée en raison de la tendance négative prévue")
                    
                    st.markdown("\n".join(recommendations_positive))
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # Tableau des jours autour
                # Afficher le nombre réel de jours disponibles
                if days_before_count == 7 and days_after_count == 7:
                    window_title = "#### 📅 Détail des Jours Autour (7 jours avant et après)"
                else:
                    window_title = f"#### 📅 Détail des Jours Autour ({days_before_count} jour{'s' if days_before_count > 1 else ''} avant, {days_after_count} jour{'s' if days_after_count > 1 else ''} après)"
                st.markdown(window_title)
                st.dataframe(
                    window_data[['Date', 'Jour', 'Encaissements', 'Décaissements', 'Cash_Flow_Net', 'Cumul_Total_EUR']],
                    width='stretch'
                )
        else:
            st.info("💡 Cliquez sur '🚀 Lancer le Forecast' pour calculer et afficher les résultats.")
    
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
            st.success("✅ Ce scénario correspond au forecast standard lancé dans la section '🎯 Lancer Forecast'")
        
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
        
        fx_rates_current = get_real_exchange_rates()
        usd_rate_current = fx_rates_current.get('USD', 0.92)
        jpy_rate_current = fx_rates_current.get('JPY', 0.0065)
        
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
        - **Hedging naturel** : Aligner les encaissements et décaissements dans la même devise
        - **Options FX** : Protéger contre les pertes tout en bénéficiant des gains
        """)
        
        # ========================================================================
        # RECOMMANDATIONS INVESTISSEMENT & FINANCEMENT
        # ========================================================================
        st.markdown("### 💡 Recommandations Investissement & Financement")
        
        st.markdown("""
        **Selon les spécifications, il faut optimiser les placements de trésorerie et les stratégies de financement.**
        """)
        
        # Afficher les recommandations basées sur le forecast si disponible
        # IMPORTANT: Vérifier qu'on est bien dans la section "Scénarios & Risques"
        if 'forecast_results' in st.session_state and st.session_state.forecast_results is not None and section == "📊 Scénarios & Risques":
            forecast_results = st.session_state.forecast_results
            final_balance = forecast_results.get('final_balance', 0)
            
            # Récupérer correctement le worst_day avec sa date et son solde
            worst_day = forecast_results.get('worst_day', {})
            if isinstance(worst_day, pd.Series):
                worst_day_date = worst_day.get('Date', 'N/A')
                worst_day_balance = worst_day.get('Cumul_Total_EUR', 0)
                # Si Cumul_Total_EUR n'existe pas, utiliser Cumul_Net_EUR + dette
                if pd.isna(worst_day_balance) or worst_day_balance == 0:
                    worst_day_balance_net = worst_day.get('Cumul_Net_EUR', 0)
                    if not pd.isna(worst_day_balance_net):
                        worst_day_balance = worst_day_balance_net + DEBT_PRINCIPAL
            elif isinstance(worst_day, dict):
                worst_day_date = worst_day.get('Date', 'N/A')
                worst_day_balance = worst_day.get('Cumul_Total_EUR', 0)
                if worst_day_balance == 0:
                    worst_day_balance_net = worst_day.get('Cumul_Net_EUR', 0)
                    if worst_day_balance_net != 0:
                        worst_day_balance = worst_day_balance_net + DEBT_PRINCIPAL
            else:
                worst_day_date = 'N/A'
                worst_day_balance = 0
            
            # Convertir en float si nécessaire
            if isinstance(worst_day_balance, str):
                try:
                    worst_day_balance = float(str(worst_day_balance).replace(',', ''))
                except:
                    worst_day_balance = 0
            worst_day_balance = float(worst_day_balance) if not pd.isna(worst_day_balance) else 0
            
            # Vérifier aussi dans le DataFrame pour trouver le vrai minimum
            if len(forecast_results.get('forecast_df', pd.DataFrame())) > 0:
                forecast_df = forecast_results['forecast_df']
                if 'Cumul_Total_EUR' in forecast_df.columns:
                    actual_min_idx = forecast_df['Cumul_Total_EUR'].idxmin()
                    actual_min_row = forecast_df.loc[actual_min_idx]
                    actual_min_balance = actual_min_row['Cumul_Total_EUR']
                    actual_min_date = actual_min_row['Date']
                    
                    # Utiliser les valeurs réelles du DataFrame si elles sont différentes
                    if abs(actual_min_balance - worst_day_balance) > 0.01:
                        worst_day_balance = actual_min_balance
                        worst_day_date = actual_min_date
            
            st.markdown("#### 📊 Situation Actuelle (Basée sur Forecast)")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Solde Final Forecast", f"{final_balance:,.2f} EUR")
            with col2:
                st.metric("Jour le Plus Bas", f"{worst_day_balance:,.2f} EUR", help=f"Date: {worst_day_date}")
            
            if final_balance > 1_000_000:
                st.success("""
                **💰 EXCÉDENT DE TRÉSORERIE DÉTECTÉ**
                
                **Recommandations de Placement:**
                1. **Comptes à terme** : 0.5-1% sur 3-6 mois (liquidité + rendement)
                2. **Fonds monétaires** : 0.3-0.5% (liquidité quotidienne)
                3. **Rachat d'actions** : Si politique de l'entreprise le permet
                4. **Remboursement anticipé dette** : Économiser les intérêts (4.7% actuel)
                
                **💡 Calcul:** Rembourser €1M de dette = économie de **€47,000/an** en intérêts
                """)
            elif final_balance < 0 or worst_day_balance < -100_000:
                worst_day_display = f"{worst_day_date} ({worst_day_balance:,.0f} EUR)" if worst_day_date != 'N/A' else f"{worst_day_balance:,.0f} EUR"
                st.error(f"""
                **🚨 DÉFICIT DE TRÉSORERIE DÉTECTÉ**
                
                **Recommandations de Financement:**
                1. **Ligne de crédit** : Négocier une facilité de caisse (taux ~5-6%)
                2. **Affacturage** : Céder les créances clients (coût ~1-3% du montant)
                3. **Découvert bancaire** : Solution d'urgence (taux élevé, éviter si possible)
                4. **Négociation fournisseurs** : Étendre les délais de paiement (DPO)
                5. **Accélération recouvrement** : Relances clients pour réduire DSO
                
                **⚠️ Priorité:** Agir AVANT le jour le plus bas: {worst_day_display}
                """)
            else:
                st.info("""
                **✅ SITUATION ÉQUILIBRÉE**
                
                **Recommandations:**
                1. **Maintenir une réserve** : 2-3 mois de charges d'exploitation
                2. **Surveiller les risques** : Taux d'intérêt et FX
                3. **Optimiser le BFR** : Réduire DSO, optimiser DPO
                4. **Préparer les scénarios** : Avoir un plan pour chaque scénario
                """)
        else:
            st.warning("💡 Lancez d'abord le forecast dans la section '🎯 Lancer Forecast' pour des recommandations personnalisées")
        
        st.markdown("""
        **📚 Références & Documentation:**
        - J.P. Morgan (2024) : Best practices en gestion de trésorerie
        - Roy et al. (2025) : Modèles de forecast avancés
        - Fitranita et al. (2024) : Optimisation placements/financements
        """)
    
    # Footer commun à toutes les sections - UNIQUEMENT à la fin de toutes les sections
    # IMPORTANT: Ce footer ne doit s'afficher qu'une seule fois, après toutes les sections
    # Toutes les sections se terminent par un elif, donc le footer s'affiche toujours une seule fois
    st.markdown("---")
    st.markdown("""
    <div id="dashboard-footer" style='text-align: center; color: #666; padding: 2rem; background-color: #f8f9fa; border-top: 2px solid #dee2e6; margin-top: 2rem;'>
        <p style='margin: 0.5rem 0;'><strong>Dashboard Professionnel - Cash Flow Forecasting</strong></p>
        <p style='margin: 0.5rem 0; font-size: 0.9em;'>Méthode Directe | DSO/DPO | Multi-Devises | Analyse de Risques</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Arrêter ici si on est en mode Streamlit
    sys.exit(0)

# ============================================================================
# MODE SCRIPT - FORECAST COMPLET
# ============================================================================

# Si on arrive ici, on est en mode script (pas Streamlit)
# Vérifier qu'on a bien l'argument --script
if "--script" not in sys.argv:
    print("="*70)
    print("⚠️  MODE SCRIPT")
    print("="*70)
    print("Pour exécuter le forecast complet, utilisez:")
    print(f"   python {Path(__file__).name} --script")
    print("\nOu lancez le dashboard (par défaut):")
    print(f"   python {Path(__file__).name}")
    sys.exit(0)

print("="*70)
print("CASH FORECASTING ANALYSIS - CAPSTONE TREASURY FORECAST")
print("="*70)

# Demander la date à l'utilisateur
while True:
    date_input = input("\n📅 Entrez la date de départ pour le forecast (format: YYYY-MM-DD, ex: 2025-01-01): ").strip()
    try:
        start_forecast = datetime.strptime(date_input, '%Y-%m-%d')
        start_forecast_date = start_forecast.date()
        
        if start_forecast_date > MAX_FORECAST_DATE:
            print(f"❌ La date de départ ne peut pas être après le {MAX_FORECAST_DATE.strftime('%Y-%m-%d')}")
            continue
        
        days_until_limit = (MAX_FORECAST_DATE - start_forecast_date).days + 1
        
        if days_until_limit <= 0:
            print(f"❌ La date de départ doit être avant ou égale au {MAX_FORECAST_DATE.strftime('%Y-%m-%d')}")
            continue
        
        forecast_days_count = min(90, days_until_limit)
        end_forecast_date = start_forecast_date + timedelta(days=forecast_days_count - 1)
        
        print(f"✅ Date sélectionnée: {start_forecast_date.strftime('%Y-%m-%d')}")
        print(f"📅 Forecast jusqu'au: {end_forecast_date.strftime('%Y-%m-%d')} ({forecast_days_count} jours)")
        if end_forecast_date >= MAX_FORECAST_DATE:
            print(f"   ⚠️  Limite atteinte: Les données historiques 2024 permettent des projections jusqu'au {MAX_FORECAST_DATE.strftime('%Y-%m-%d')} maximum")
        break
    except ValueError:
        print("❌ Format invalide! Utilisez YYYY-MM-DD (ex: 2025-01-01)")

# Créer le dossier bdd/[date]
date_str = start_forecast.strftime('%Y-%m-%d')
csv_output_dir = bdd_dir / date_str
csv_output_dir.mkdir(parents=True, exist_ok=True)
print(f"📁 Dossier de sortie CSV: {csv_output_dir}")

# Charger les données
print("\n" + "="*70)
print("1. CHARGEMENT ET NETTOYAGE DES TRANSACTIONS BANCAIRES")
print("="*70)

bank = pd.read_csv(data_dir/'bank_transactions.csv', parse_dates=['date'])
sales = pd.read_csv(data_dir/'sales_invoices.csv', parse_dates=['issue_date','due_date','payment_date'])
purchase = pd.read_csv(data_dir/'purchase_invoices.csv', parse_dates=['issue_date','due_date','payment_date'])

print(f"   ✓ Transactions bancaires: {len(bank)} lignes")
print(f"   ✓ Factures clients: {len(sales)} lignes")
print(f"   ✓ Factures fournisseurs: {len(purchase)} lignes")

# Nettoyage
bank['month'] = bank['date'].dt.to_period('M')
bank['day_of_week'] = bank['date'].dt.day_name()
bank['week'] = bank['date'].dt.isocalendar().week
bank['day'] = bank['date'].dt.day

# Calcul DSO/DPO
sales_paid = sales[sales['status']=='Paid'].copy()
if len(sales_paid) > 0:
    sales_paid['days_to_pay'] = (sales_paid['payment_date'] - sales_paid['issue_date']).dt.days
    dso_mean = sales_paid['days_to_pay'].mean()
    dso_median = sales_paid['days_to_pay'].median()
else:
    dso_mean = 0
    dso_median = 0

purchase_paid = purchase[purchase['status']=='Paid'].copy()
if len(purchase_paid) > 0:
    purchase_paid['days_to_pay'] = (purchase_paid['payment_date'] - purchase_paid['issue_date']).dt.days
    dpo_mean = purchase_paid['days_to_pay'].mean()
    dpo_median = purchase_paid['days_to_pay'].median()
else:
    dpo_mean = 0
    dpo_median = 0

print(f"\n   ✓ DSO moyen: {dso_mean:.1f} jours (médiane: {dso_median:.1f})")
print(f"   ✓ DPO moyen: {dpo_mean:.1f} jours (médiane: {dpo_median:.1f})")

# Récupérer les taux de change
fx_rates = get_real_exchange_rates()
# IMPORTANT: Convertir toutes les transactions en EUR pour les calculs
bank['amount_eur'] = bank.apply(
    lambda x: convert_to_eur(x['amount'], x.get('currency', 'EUR'), fx_rates, x['date']), 
    axis=1
)

# Classification
print("\n" + "="*70)
print("2. CLASSIFICATION RÉCURRENT vs NON-RÉCURRENT")
print("="*70)

category_classification = {
    'Payroll': 'recurring',
    'Supplier Payment': 'recurring',
    'Loan Interest': 'recurring',
    'Bank Fee': 'recurring',
    'Tax Payment': 'recurring',
    'Transfer to Payroll': 'recurring'
}

bank['flow_type'] = bank['category'].map(category_classification).fillna('non-recurring')
bank['is_recurring'] = bank['flow_type'] == 'recurring'

recurring_flows = bank[bank['is_recurring']].copy()
non_recurring_flows = bank[~bank['is_recurring']].copy()

print(f"\n   📊 Classification par type:")
print(f"   ✓ Récurrent: {len(recurring_flows)} transactions ({len(recurring_flows)/len(bank)*100:.1f}%)")
print(f"   ✓ Non-récurrent: {len(non_recurring_flows)} transactions ({len(non_recurring_flows)/len(bank)*100:.1f}%)")

# Saisonnalité
print("\n" + "="*70)
print("3. DÉTECTION DE SAISONNALITÉ ET PATTERNS")
print("="*70)

weekly_pattern = bank.groupby(['day_of_week', 'type'])['amount'].sum().unstack(fill_value=0)
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
weekly_pattern = weekly_pattern.reindex(day_order, fill_value=0)

print(f"\n   📅 Pattern hebdomadaire (moyenne par jour):")
for day in day_order:
    if day in weekly_pattern.index:
        credit = weekly_pattern.loc[day, 'credit'] if 'credit' in weekly_pattern.columns else 0
        debit = weekly_pattern.loc[day, 'debit'] if 'debit' in weekly_pattern.columns else 0
        print(f"      {day}: Crédits {credit:,.2f} EUR | Débits {debit:,.2f} EUR")

# Moyennes historiques
avg_daily_credit = bank[bank['type']=='credit']['amount_eur'].mean()
avg_daily_debit = bank[bank['type']=='debit']['amount_eur'].mean()
std_daily_credit = bank[bank['type']=='credit']['amount_eur'].std()
std_daily_debit = bank[bank['type']=='debit']['amount_eur'].std()

# Patterns hebdomadaires pour ajuster
bank['day_of_week'] = bank['date'].dt.day_name()
weekly_credit_pattern = bank[bank['type']=='credit'].groupby('day_of_week')['amount_eur'].mean()
weekly_debit_pattern = bank[bank['type']=='debit'].groupby('day_of_week')['amount_eur'].mean()

# Facteurs d'impact
print("\n" + "="*70)
print("4.1. FACTEURS D'IMPACT SUR LE FORECAST")
print("="*70)

# Inflation
bank_recurring = bank[bank['category'].isin(['Supplier Payment', 'Payroll', 'Loan Interest'])].copy()
bank_recurring['month'] = bank_recurring['date'].dt.to_period('M')
monthly_recurring = bank_recurring.groupby('month')['amount'].sum().sort_index()

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

print(f"\n   📈 Inflation: {inflation_rate*100:.2f}% annuel")

# Volatilité
volume_volatility_credit = std_daily_credit / avg_daily_credit if avg_daily_credit > 0 else 0
volume_volatility_debit = std_daily_debit / avg_daily_debit if avg_daily_debit > 0 else 0

print(f"   📊 Volatilité volumes: ±{volume_volatility_credit*100:.1f}% encaissements, ±{volume_volatility_debit*100:.1f}% décaissements")

# Factures ouvertes
sales_open = sales[sales['status'].isin(['Open','Overdue'])].copy()
sales_open['expected_payment'] = sales_open['due_date'] + pd.Timedelta(days=int(dso_mean))
sales_open['payment_date'] = sales_open['expected_payment'].dt.date
sales_open['amount_eur'] = sales_open.apply(
    lambda x: convert_to_eur(x['amount'], x['currency'], fx_rates, x['payment_date']), axis=1
)

purchase_open = purchase[purchase['status'].isin(['Open','Overdue'])].copy()
purchase_open['expected_payment'] = purchase_open['due_date'] + pd.Timedelta(days=int(dpo_mean))
purchase_open['payment_date'] = purchase_open['expected_payment'].dt.date
purchase_open['amount_eur'] = purchase_open.apply(
    lambda x: convert_to_eur(x['amount'], x['currency'], fx_rates, x['payment_date']), axis=1
)

print(f"   💱 Factures clients ouvertes: {len(sales_open)} (montant total: {sales_open['amount_eur'].sum():,.2f} EUR)")
print(f"   💱 Factures fournisseurs ouvertes: {len(purchase_open)} (montant total: {purchase_open['amount_eur'].sum():,.2f} EUR)")

# Solde initial
bank_until_start = bank[bank['date'].dt.date < start_forecast_date]
if len(bank_until_start) > 0:
    initial_balance_eur = bank_until_start[bank_until_start['currency'] == 'EUR']['amount'].sum()
    initial_balance_usd = bank_until_start[bank_until_start['currency'] == 'USD']['amount'].sum()
    initial_balance_jpy = bank_until_start[bank_until_start['currency'] == 'JPY']['amount'].sum()
    initial_balance = initial_balance_eur + (initial_balance_usd * fx_rates.get('USD', 0.92)) + (initial_balance_jpy * fx_rates.get('JPY', 0.0065))
    print(f"\n   📈 SOLDE INITIAL:")
    print(f"      EUR: {initial_balance_eur:,.2f} EUR")
    print(f"      USD: {initial_balance_usd:,.2f} USD")
    print(f"      JPY: {initial_balance_jpy:,.2f} JPY")
    print(f"      Total en EUR: {initial_balance:,.2f} EUR")
else:
    initial_balance = 0
    initial_balance_eur = 0
    initial_balance_usd = 0
    initial_balance_jpy = 0

# Forecast quotidien (version simplifiée pour le fichier unique)
print("\n" + "="*70)
print(f"4. FORECAST BASELINE - {forecast_days_count} JOURS (QUOTIDIEN)")
print("="*70)

forecast_days = []
cumul = initial_balance
cumul_eur = initial_balance_eur
cumul_usd = initial_balance_usd
cumul_jpy = initial_balance_jpy

for day in range(forecast_days_count):
    forecast_date = start_forecast_date + timedelta(days=day)
    day_name = forecast_date.strftime('%A')
    
    if day_name in weekly_credit_pattern.index:
        base_credit = weekly_credit_pattern[day_name]
    else:
        base_credit = avg_daily_credit
    
    if day_name in weekly_debit_pattern.index:
        base_debit = weekly_debit_pattern[day_name]
    else:
        base_debit = avg_daily_debit
    
    # Factures du jour
    sales_day = sales_open[sales_open['payment_date'] == forecast_date]['amount_eur'].sum()
    purchase_day = purchase_open[purchase_open['payment_date'] == forecast_date]['amount_eur'].sum()
    
    credit_forecast = base_credit + sales_day
    debit_forecast = base_debit + purchase_day
    
    # Ajustements
    inflation_adjustment = 1 + (inflation_rate * day / 365)
    debit_forecast *= inflation_adjustment
    
    # Volatilité
    np.random.seed(100 + day)
    volume_adjustment_credit = 1 + np.random.normal(0, volume_volatility_credit * 0.3)
    volume_adjustment_debit = 1 + np.random.normal(0, volume_volatility_debit * 0.3)
    credit_forecast *= max(0.5, volume_adjustment_credit)
    debit_forecast *= max(0.5, volume_adjustment_debit)
    
    # Cash flow net
    net_forecast = credit_forecast - debit_forecast
    cumul += net_forecast
    
    forecast_days.append({
        'Date': forecast_date.strftime('%Y-%m-%d'),
        'Jour': day_name,
        'Encaissements': round(credit_forecast, 2),
        'Décaissements': round(debit_forecast, 2),
        'Cash_Flow_Net': round(net_forecast, 2),
        'Cumul': round(cumul, 2)
    })

forecast_daily_df = pd.DataFrame(forecast_days)

# Sauvegarder
forecast_daily_df.to_csv(csv_output_dir / 'forecast_daily_90days.csv', index=False)
print(f"\n✅ Forecast sauvegardé dans: {csv_output_dir / 'forecast_daily_90days.csv'}")

# Résumé
print("\n" + "="*70)
print("RÉSUMÉ DU FORECAST")
print("="*70)
print(f"   📅 Période: {start_forecast_date.strftime('%Y-%m-%d')} à {end_forecast_date.strftime('%Y-%m-%d')}")
print(f"   💰 Solde initial: {initial_balance:,.2f} EUR")
print(f"   💰 Solde final: {cumul:,.2f} EUR")
print(f"   📊 Variation: {cumul - initial_balance:+,.2f} EUR")
print("="*70)
print("\n💡 Pour voir le dashboard interactif avec tous les détails:")
print("   streamlit run cash_forecast_complete.py")

