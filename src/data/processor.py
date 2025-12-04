"""
Data processing module for Cash Flow Forecasting

This module handles calculation of metrics like DSO, DPO, and data enrichment.
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

from ..utils.currency import convert_to_eur


class DataProcessor:
    """
    Handles data processing and metric calculations for cash flow forecasting.
    """
    
    def __init__(self, fx_rates: Dict[str, float]):
        """
        Initialize the DataProcessor.
        
        Args:
            fx_rates: Dictionary of exchange rates
        """
        self.fx_rates = fx_rates
    
    def add_eur_conversion(self, df: pd.DataFrame, amount_col: str = 'amount', 
                          currency_col: str = 'currency', date_col: Optional[str] = None) -> pd.DataFrame:
        """
        Add EUR conversion column to a DataFrame.
        
        Args:
            df: DataFrame to process
            amount_col: Name of the amount column
            currency_col: Name of the currency column
            date_col: Optional date column for future time-based FX rates
            
        Returns:
            DataFrame with added 'amount_eur' column
        """
        df = df.copy()
        df['amount_eur'] = df.apply(
            lambda x: convert_to_eur(
                x.get(amount_col, 0),
                x.get(currency_col, 'EUR'),
                self.fx_rates,
                x.get(date_col) if date_col else None
            ),
            axis=1
        )
        return df
    
    def calculate_dso(self, sales: pd.DataFrame) -> Tuple[float, pd.DataFrame]:
        """
        Calculate Days Sales Outstanding (DSO) from sales invoices.
        
        Args:
            sales: DataFrame with sales invoices
            
        Returns:
            Tuple of (dso_mean, sales_paid_valid)
        """
        sales_paid = sales[sales['status'] == 'Paid'].copy()
        
        if len(sales_paid) == 0:
            return 0.0, pd.DataFrame()
        
        # Calculate days_to_pay only for invoices with valid dates
        sales_paid['has_valid_dates'] = (
            sales_paid['payment_date'].notna() & 
            sales_paid['issue_date'].notna()
        )
        
        sales_paid.loc[sales_paid['has_valid_dates'], 'days_to_pay'] = (
            sales_paid.loc[sales_paid['has_valid_dates'], 'payment_date'] - 
            sales_paid.loc[sales_paid['has_valid_dates'], 'issue_date']
        ).dt.days
        
        sales_paid_valid = sales_paid[sales_paid['has_valid_dates']].copy()
        
        if len(sales_paid_valid) > 0:
            dso_mean = sales_paid_valid['days_to_pay'].mean()
        else:
            dso_mean = 0.0
        
        return dso_mean, sales_paid_valid
    
    def calculate_dpo(self, purchase: pd.DataFrame) -> Tuple[float, pd.DataFrame]:
        """
        Calculate Days Payable Outstanding (DPO) from purchase invoices.
        
        Args:
            purchase: DataFrame with purchase invoices
            
        Returns:
            Tuple of (dpo_mean, purchase_paid_valid)
        """
        purchase_paid = purchase[purchase['status'] == 'Paid'].copy()
        
        if len(purchase_paid) == 0:
            return 0.0, pd.DataFrame()
        
        # Calculate days_to_pay only for invoices with valid dates
        purchase_paid['has_valid_dates'] = (
            purchase_paid['payment_date'].notna() & 
            purchase_paid['issue_date'].notna()
        )
        
        purchase_paid.loc[purchase_paid['has_valid_dates'], 'days_to_pay'] = (
            purchase_paid.loc[purchase_paid['has_valid_dates'], 'payment_date'] - 
            purchase_paid.loc[purchase_paid['has_valid_dates'], 'issue_date']
        ).dt.days
        
        purchase_paid_valid = purchase_paid[purchase_paid['has_valid_dates']].copy()
        
        if len(purchase_paid_valid) > 0:
            dpo_mean = purchase_paid_valid['days_to_pay'].mean()
        else:
            dpo_mean = 0.0
        
        return dpo_mean, purchase_paid_valid
    
    def calculate_daily_statistics(self, bank: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate daily statistics from bank transactions.
        
        Args:
            bank: DataFrame with bank transactions
            
        Returns:
            Dictionary with statistics (avg_daily_credit, avg_daily_debit, etc.)
        """
        if len(bank) == 0:
            return {
                'avg_daily_credit': 0.0,
                'avg_daily_debit': 0.0,
                'std_daily_credit': 0.0,
                'std_daily_debit': 0.0
            }
        
        # Ensure amount_eur exists
        if 'amount_eur' not in bank.columns:
            bank = self.add_eur_conversion(bank, date_col='date')
        
        # Calculate daily totals
        bank['date_only'] = bank['date'].dt.date
        daily_totals = bank.groupby(['date_only', 'type']).agg({
            'amount_eur': 'sum'
        }).reset_index()
        
        # Separate credits and debits
        daily_credits = daily_totals[daily_totals['type'] == 'credit']['amount_eur']
        daily_debits = daily_totals[daily_totals['type'] == 'debit']['amount_eur']
        
        return {
            'avg_daily_credit': daily_credits.mean() if len(daily_credits) > 0 else 0.0,
            'avg_daily_debit': daily_debits.mean() if len(daily_debits) > 0 else 0.0,
            'std_daily_credit': daily_credits.std() if len(daily_credits) > 0 else 0.0,
            'std_daily_debit': daily_debits.std() if len(daily_debits) > 0 else 0.0
        }
    
    def calculate_weekly_patterns(self, bank: pd.DataFrame) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Calculate weekly patterns for credits and debits.
        
        Args:
            bank: DataFrame with bank transactions
            
        Returns:
            Tuple of (weekly_credit_pattern, weekly_debit_pattern)
        """
        if len(bank) == 0:
            return {}, {}
        
        # Ensure amount_eur exists
        if 'amount_eur' not in bank.columns:
            bank = self.add_eur_conversion(bank, date_col='date')
        
        bank['day_name'] = bank['date'].dt.strftime('%A')
        bank['date_only'] = bank['date'].dt.date
        
        # Calculate daily totals by day of week
        daily_totals = bank.groupby(['date_only', 'day_name', 'type']).agg({
            'amount_eur': 'sum'
        }).reset_index()
        
        # Calculate averages by day of week
        weekly_credit = daily_totals[daily_totals['type'] == 'credit'].groupby('day_name')['amount_eur'].mean()
        weekly_debit = daily_totals[daily_totals['type'] == 'debit'].groupby('day_name')['amount_eur'].mean()
        
        return weekly_credit.to_dict(), weekly_debit.to_dict()


def calculate_metrics(
    bank: pd.DataFrame,
    sales: pd.DataFrame,
    purchase: pd.DataFrame,
    fx_rates: Dict[str, float]
) -> Dict[str, any]:
    """
    Calculate all metrics needed for forecasting.
    
    Args:
        bank: Bank transactions DataFrame
        sales: Sales invoices DataFrame
        purchase: Purchase invoices DataFrame
        fx_rates: Exchange rates dictionary
        
    Returns:
        Dictionary with all calculated metrics
    """
    processor = DataProcessor(fx_rates)
    
    # Add EUR conversion to bank
    bank = processor.add_eur_conversion(bank, date_col='date')
    
    # Calculate DSO and DPO
    dso_mean, sales_paid_valid = processor.calculate_dso(sales)
    dpo_mean, purchase_paid_valid = processor.calculate_dpo(purchase)
    
    # Calculate daily statistics
    daily_stats = processor.calculate_daily_statistics(bank)
    
    # Calculate weekly patterns
    weekly_credit_pattern, weekly_debit_pattern = processor.calculate_weekly_patterns(bank)
    
    return {
        'dso_mean': dso_mean,
        'dpo_mean': dpo_mean,
        'sales_paid_valid': sales_paid_valid,
        'purchase_paid_valid': purchase_paid_valid,
        'avg_daily_credit': daily_stats['avg_daily_credit'],
        'avg_daily_debit': daily_stats['avg_daily_debit'],
        'std_daily_credit': daily_stats['std_daily_credit'],
        'std_daily_debit': daily_stats['std_daily_debit'],
        'weekly_credit_pattern': weekly_credit_pattern,
        'weekly_debit_pattern': weekly_debit_pattern,
        'bank': bank  # Return enriched bank DataFrame
    }

