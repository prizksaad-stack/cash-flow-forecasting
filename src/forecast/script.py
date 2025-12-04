"""
Script mode for running forecasts without dashboard
"""
from datetime import datetime, date
from pathlib import Path
import pandas as pd

from ..config import get_config, MAX_FORECAST_DATE
from ..data import load_all_data, calculate_metrics
from ..utils import get_real_exchange_rates
from .engine import run_forecast


def run_forecast_script():
    """
    Run forecast in script mode (command line).
    """
    print("=" * 70)
    print("📊 CASH FLOW FORECASTING - MODE SCRIPT")
    print("=" * 70)
    print()
    
    # Get configuration
    config = get_config(Path(__file__).parent.parent.parent / 'main.py')
    
    # Load data
    print("📂 Chargement des données...")
    try:
        bank, sales, purchase = load_all_data(config.data_dir)
        print(f"✅ {len(bank)} transactions, {len(sales)} factures clients, {len(purchase)} factures fournisseurs")
    except Exception as e:
        print(f"❌ Erreur lors du chargement: {e}")
        return
    
    # Get exchange rates
    print("\n💱 Récupération des taux de change...")
    fx_rates = get_real_exchange_rates(verbose=True)
    print(f"✅ Taux: USD={fx_rates.get('USD', 0.92):.4f}, JPY={fx_rates.get('JPY', 0.0065):.6f}")
    
    # Calculate metrics
    print("\n📊 Calcul des métriques...")
    metrics = calculate_metrics(bank, sales, purchase, fx_rates)
    print(f"✅ DSO: {metrics['dso_mean']:.1f} jours, DPO: {metrics['dpo_mean']:.1f} jours")
    
    # Get start date
    print("\n📅 Date de début du forecast:")
    start_date_str = input("   Entrez la date (YYYY-MM-DD) ou appuyez sur Entrée pour aujourd'hui: ").strip()
    
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            print("❌ Format de date invalide, utilisation de la date d'aujourd'hui")
            start_date = date.today()
    else:
        start_date = date.today()
    
    print(f"✅ Date de début: {start_date}")
    
    # Calculate inflation and volatility (simplified - could be improved)
    print("\n📈 Calcul des facteurs d'impact...")
    inflation_rate = 0.02  # 2% annual inflation (default)
    volume_volatility_credit = metrics['std_daily_credit'] / metrics['avg_daily_credit'] if metrics['avg_daily_credit'] > 0 else 0.1
    volume_volatility_debit = metrics['std_daily_debit'] / metrics['avg_daily_debit'] if metrics['avg_daily_debit'] > 0 else 0.1
    
    print(f"✅ Inflation: {inflation_rate*100:.1f}%, Volatilité crédit: {volume_volatility_credit*100:.1f}%, Volatilité débit: {volume_volatility_debit*100:.1f}%")
    
    # Run forecast
    print("\n🔮 Exécution du forecast...")
    try:
        results = run_forecast(
            metrics['bank'],
            sales,
            purchase,
            start_date,
            fx_rates,
            metrics['dso_mean'],
            metrics['dpo_mean'],
            metrics['avg_daily_credit'],
            metrics['avg_daily_debit'],
            metrics['std_daily_credit'],
            metrics['std_daily_debit'],
            metrics['weekly_credit_pattern'],
            metrics['weekly_debit_pattern'],
            inflation_rate,
            volume_volatility_credit,
            volume_volatility_debit,
            MAX_FORECAST_DATE
        )
        
        print(f"✅ Forecast terminé: {results['forecast_days_count']} jours")
        print(f"   Solde initial: {results['initial_balance']:,.2f} EUR")
        print(f"   Solde final: {results['final_balance']:,.2f} EUR")
        print(f"   Jours négatifs: {len(results['negative_days'])}")
        print(f"   Zones de risque: {results['risk_zones']}")
        
        # Save results
        output_dir = config.bdd_dir / start_date.strftime('%Y-%m-%d')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save forecast CSV
        forecast_path = output_dir / 'forecast_daily_90days.csv'
        results['forecast_df'].to_csv(forecast_path, index=False)
        print(f"\n💾 Résultats sauvegardés dans: {forecast_path}")
        
        # Generate report
        report_path = output_dir / 'forecast_report.txt'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"Cash Flow Forecast Report\n")
            f.write(f"{'='*70}\n\n")
            f.write(f"Date de début: {start_date}\n")
            f.write(f"Date de fin: {results['end_date']}\n")
            f.write(f"Nombre de jours: {results['forecast_days_count']}\n\n")
            f.write(f"Solde initial: {results['initial_balance']:,.2f} EUR\n")
            f.write(f"Solde final: {results['final_balance']:,.2f} EUR\n")
            f.write(f"Variation: {results['final_balance'] - results['initial_balance']:,.2f} EUR\n\n")
            f.write(f"Jours négatifs: {len(results['negative_days'])}\n")
            f.write(f"Zones de risque:\n")
            f.write(f"  - Safe: {results['risk_zones']['Safe']} jours\n")
            f.write(f"  - Warning: {results['risk_zones']['Warning']} jours\n")
            f.write(f"  - Critical: {results['risk_zones']['Critical']} jours\n\n")
            f.write(f"Jour le plus bas: {results['worst_day']['Date']} ({results['worst_day']['Cumul_Net_EUR']:,.2f} EUR)\n")
        
        print(f"📄 Rapport généré: {report_path}")
        
    except Exception as e:
        print(f"❌ Erreur lors du forecast: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 70)
    print("✅ Forecast terminé avec succès!")
    print("=" * 70)

