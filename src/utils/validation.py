"""
Data validation utilities for Cash Flow Forecasting
"""
import pandas as pd
from datetime import datetime, date
from typing import Dict, Any, Tuple, Optional


def validate_data(
    bank: pd.DataFrame,
    sales: pd.DataFrame,
    purchase: pd.DataFrame
) -> Tuple[bool, Optional[str]]:
    """
    Valide les données d'entrée pour le forecast.
    
    Args:
        bank: DataFrame des transactions bancaires
        sales: DataFrame des factures clients
        purchase: DataFrame des factures fournisseurs
        
    Returns:
        Tuple (is_valid, error_message)
    """
    # Vérifier que les DataFrames ne sont pas vides
    if bank.empty:
        return False, "Le DataFrame des transactions bancaires est vide"
    
    if sales.empty:
        return False, "Le DataFrame des factures clients est vide"
    
    if purchase.empty:
        return False, "Le DataFrame des factures fournisseurs est vide"
    
    # Vérifier les colonnes requises pour bank
    required_bank_cols = ['date', 'type', 'amount']
    missing_cols = [col for col in required_bank_cols if col not in bank.columns]
    if missing_cols:
        return False, f"Colonnes manquantes dans bank: {missing_cols}"
    
    # Vérifier les colonnes requises pour sales
    required_sales_cols = ['date', 'amount', 'status']
    missing_cols = [col for col in required_sales_cols if col not in sales.columns]
    if missing_cols:
        return False, f"Colonnes manquantes dans sales: {missing_cols}"
    
    # Vérifier les colonnes requises pour purchase
    required_purchase_cols = ['date', 'amount', 'status']
    missing_cols = [col for col in required_purchase_cols if col not in purchase.columns]
    if missing_cols:
        return False, f"Colonnes manquantes dans purchase: {missing_cols}"
    
    # Vérifier les types de données
    if not pd.api.types.is_datetime64_any_dtype(bank['date']):
        try:
            bank['date'] = pd.to_datetime(bank['date'])
        except:
            return False, "La colonne 'date' de bank ne peut pas être convertie en datetime"
    
    if not pd.api.types.is_numeric_dtype(bank['amount']):
        return False, "La colonne 'amount' de bank doit être numérique"
    
    return True, None


def validate_forecast_params(
    start_date: date,
    max_forecast_date: date,
    dso_mean: Optional[float] = None,
    dpo_mean: Optional[float] = None
) -> Tuple[bool, Optional[str]]:
    """
    Valide les paramètres du forecast.
    
    Args:
        start_date: Date de début du forecast
        max_forecast_date: Date maximale pour le forecast
        dso_mean: DSO moyen (optionnel)
        dpo_mean: DPO moyen (optionnel)
        
    Returns:
        Tuple (is_valid, error_message)
    """
    if start_date >= max_forecast_date:
        return False, f"La date de début ({start_date}) doit être antérieure à la date maximale ({max_forecast_date})"
    
    if dso_mean is not None and (dso_mean < 0 or dso_mean > 365):
        return False, f"DSO doit être entre 0 et 365 jours (reçu: {dso_mean})"
    
    if dpo_mean is not None and (dpo_mean < 0 or dpo_mean > 365):
        return False, f"DPO doit être entre 0 et 365 jours (reçu: {dpo_mean})"
    
    return True, None

