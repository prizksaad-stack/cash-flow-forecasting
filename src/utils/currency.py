"""
Currency conversion utilities for Cash Flow Forecasting
"""
import requests
from typing import Dict, Optional
import warnings

# Fallback exchange rates (2024 averages)
FALLBACK_RATES = {
    'USD': 0.92,
    'JPY': 0.0065,
    'EUR': 1.0
}


def get_real_exchange_rates(verbose: bool = True) -> Dict[str, float]:
    """
    Récupère les taux de change réels via API.
    
    Args:
        verbose: Si True, affiche les messages de progression
        
    Returns:
        Dictionnaire des taux de change { 'USD': 0.92, 'JPY': 0.0065, 'EUR': 1.0 }
    """
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
            if verbose:
                print(f"   🔄 Tentative de récupération des taux via {api['name']}...")
            response = requests.get(api['url'], timeout=5)
            response.raise_for_status()
            data = response.json()
            rates = api['parser'](data)
            
            # Correction pour JPY si nécessaire
            if 'JPY' in rates and rates['JPY'] > 1:
                rates['JPY'] = 1.0 / rates['JPY']
            
            fx_rates.update(rates)
            if verbose:
                print(f"   ✅ Taux récupérés avec succès via {api['name']}")
            return fx_rates
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Erreur avec {api['name']}: {str(e)[:50]}")
            continue
    
    if verbose:
        print("   ⚠️  Utilisation de taux de secours (moyennes 2024)")
    return FALLBACK_RATES.copy()


def convert_to_eur(
    amount: float,
    currency: Optional[str],
    fx_rates: Dict[str, float],
    date: Optional[str] = None
) -> float:
    """
    Convertit un montant en EUR selon la devise.
    
    Args:
        amount: Montant à convertir
        currency: Devise source ('EUR', 'USD', 'JPY')
        fx_rates: Dictionnaire des taux de change { 'USD': 0.92, 'JPY': 0.0065, 'EUR': 1.0 }
        date: Date optionnelle (non utilisée actuellement, pour extension future)
    
    Returns:
        Montant converti en EUR
    """
    import pandas as pd
    
    # Gestion des cas limites
    if amount is None or pd.isna(amount):
        return 0.0
    
    if currency == 'EUR' or currency is None:
        return float(amount)
    elif currency in fx_rates and fx_rates[currency] is not None:
        rate = fx_rates[currency]
        # Vérifier que le taux est valide (positif et raisonnable)
        if 0 < rate < 1000:  # Protection contre valeurs aberrantes
            return float(amount * rate)
        else:
            # Taux invalide, utiliser valeur par défaut
            return float(amount * FALLBACK_RATES.get(currency, 1.0))
    else:
        # Devise non reconnue, retourner tel quel (assumé EUR)
        return float(amount)

