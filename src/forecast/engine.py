"""
Forecast engine for Cash Flow Forecasting

This module contains the main forecasting logic.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from ..config import get_config, DEBT_PRINCIPAL, DEBT_MONTHLY_INTEREST
from ..utils.currency import convert_to_eur


class ForecastEngine:
    """
    Main engine for cash flow forecasting.
    """
    
    def __init__(
        self,
        bank: pd.DataFrame,
        sales: pd.DataFrame,
        purchase: pd.DataFrame,
        fx_rates: Dict[str, float],
        config: Optional[object] = None
    ):
        """
        Initialize the forecast engine.
        
        Args:
            bank: Bank transactions DataFrame
            sales: Sales invoices DataFrame
            purchase: Purchase invoices DataFrame
            fx_rates: Exchange rates dictionary
            config: Optional configuration object
        """
        self.bank = bank.copy()
        self.sales = sales.copy()
        self.purchase = purchase.copy()
        self.fx_rates = fx_rates
        self.config = config or get_config()
        
        # Extract exchange rates
        self.usd_rate = fx_rates.get('USD', 0.92)
        self.jpy_rate = fx_rates.get('JPY', 0.0065)
    
    def prepare_open_invoices(
        self,
        invoices: pd.DataFrame,
        days_offset: int,
        invoice_type: str = 'sales'
    ) -> pd.DataFrame:
        """
        Prepare open invoices with expected payment dates.
        
        Args:
            invoices: DataFrame with invoices
            days_offset: Days to add to due_date (DSO or DPO)
            invoice_type: 'sales' or 'purchase'
            
        Returns:
            DataFrame with payment dates and EUR amounts
        """
        open_invoices = invoices[invoices['status'].isin(['Open', 'Overdue'])].copy()
        
        if len(open_invoices) == 0:
            return pd.DataFrame(columns=['payment_date', 'amount_eur', 'currency', 'amount'])
        
        # Filter only invoices with valid due_date
        valid_invoices = open_invoices[open_invoices['due_date'].notna()].copy()
        
        if len(valid_invoices) == 0:
            return pd.DataFrame(columns=['payment_date', 'amount_eur', 'currency', 'amount'])
        
        # Calculate expected payment date
        days = int(round(days_offset)) if days_offset is not None and not pd.isna(days_offset) else 0
        valid_invoices['expected_payment'] = valid_invoices['due_date'] + pd.Timedelta(days=days)
        valid_invoices['payment_date'] = valid_invoices['expected_payment'].dt.date
        
        # Ensure currency column exists
        if 'currency' not in valid_invoices.columns:
            valid_invoices['currency'] = 'EUR'
        
        # Convert to EUR
        valid_invoices['amount_eur'] = valid_invoices.apply(
            lambda x: convert_to_eur(
                x['amount'],
                x.get('currency', 'EUR'),
                self.fx_rates,
                x['payment_date']
            ),
            axis=1
        )
        
        return valid_invoices
    
    def calculate_initial_balance(self, start_date: date) -> Dict[str, float]:
        """
        Calculate initial balance by currency.
        
        Args:
            start_date: Start date for the forecast
            
        Returns:
            Dictionary with balances by currency
        """
        bank_until_start = self.bank[self.bank['date'].dt.date < start_date]
        
        if len(bank_until_start) == 0:
            return {
                'eur': 0.0,
                'usd': 0.0,
                'jpy': 0.0,
                'total_eur': 0.0
            }
        
        # Ensure amount_eur exists
        if 'amount_eur' not in bank_until_start.columns:
            bank_until_start['amount_eur'] = bank_until_start.apply(
                lambda x: convert_to_eur(
                    x.get('amount', 0),
                    x.get('currency', 'EUR'),
                    self.fx_rates,
                    x.get('date')
                ),
                axis=1
            )
        
        # Calculate by currency
        balances = {}
        for currency in ['EUR', 'USD', 'JPY']:
            currency_rows = bank_until_start[bank_until_start['currency'] == currency]
            if len(currency_rows) > 0:
                # Original amounts for tracking
                balances[currency.lower()] = currency_rows['amount'].sum()
                # EUR equivalent
                balances[f'{currency.lower()}_eur'] = currency_rows['amount_eur'].sum()
            else:
                balances[currency.lower()] = 0.0
                balances[f'{currency.lower()}_eur'] = 0.0
        
        balances['total_eur'] = (
            balances.get('eur_eur', 0) +
            balances.get('usd_eur', 0) +
            balances.get('jpy_eur', 0)
        )
        
        return balances
    
    def calculate_recurring_payments(self) -> float:
        """
        Calculate average monthly recurring payments.
        
        Returns:
            Average monthly recurring payment amount in EUR
        """
        recurring_categories = ['Loan Interest', 'Payroll', 'Bank Fee']
        bank_recurring = self.bank[self.bank['category'].isin(recurring_categories)].copy()
        
        if len(bank_recurring) == 0:
            return DEBT_MONTHLY_INTEREST
        
        # Ensure amount_eur exists
        if 'amount_eur' not in bank_recurring.columns:
            bank_recurring['amount_eur'] = bank_recurring.apply(
                lambda x: convert_to_eur(
                    x.get('amount', 0),
                    x.get('currency', 'EUR'),
                    self.fx_rates,
                    x.get('date')
                ),
                axis=1
            )
        
        # Calculate monthly averages
        monthly_sums = bank_recurring.groupby(bank_recurring['date'].dt.to_period('M'))['amount_eur'].sum()
        avg_monthly = monthly_sums.mean() if len(monthly_sums) > 0 else 0.0
        
        # Check if debt interest is already included
        loan_interest = bank_recurring[bank_recurring['category'] == 'Loan Interest']
        if len(loan_interest) > 0:
            num_months = len(bank_recurring['date'].dt.to_period('M').unique())
            avg_loan_interest = loan_interest['amount_eur'].sum() / num_months if num_months > 0 else 0
        else:
            avg_loan_interest = 0
        
        # Ensure debt interest is included
        if avg_loan_interest < DEBT_MONTHLY_INTEREST * 0.5:
            interest_to_add = DEBT_MONTHLY_INTEREST - avg_loan_interest
            avg_monthly += interest_to_add
        
        return max(avg_monthly, DEBT_MONTHLY_INTEREST)
    
    def run_forecast(
        self,
        start_date: date,
        dso_mean: float,
        dpo_mean: float,
        avg_daily_credit: float,
        avg_daily_debit: float,
        std_daily_credit: float,
        std_daily_debit: float,
        weekly_credit_pattern: Dict[str, float],
        weekly_debit_pattern: Dict[str, float],
        inflation_rate: float,
        volume_volatility_credit: float,
        volume_volatility_debit: float,
        max_forecast_date: date
    ) -> Dict:
        """
        Run the complete forecast.
        
        This is a simplified version. The full implementation would be much longer.
        For now, this provides the structure and key logic.
        
        Returns:
            Dictionary with forecast results
        """
        # Calculate forecast period
        days_until_limit = (max_forecast_date - start_date).days + 1
        forecast_days_count = min(90, days_until_limit)
        end_date = start_date + timedelta(days=forecast_days_count - 1)
        
        # Prepare open invoices
        sales_open = self.prepare_open_invoices(self.sales, dso_mean, 'sales')
        purchase_open = self.prepare_open_invoices(self.purchase, dpo_mean, 'purchase')
        
        # Calculate initial balance
        initial_balance = self.calculate_initial_balance(start_date)
        
        # Calculate recurring payments
        avg_monthly_recurring = self.calculate_recurring_payments()
        
        # Initialize forecast
        forecast_days = []
        cumul_total = initial_balance['total_eur']
        cumul_eur = initial_balance.get('eur_eur', 0)
        cumul_usd = initial_balance.get('usd_eur', 0)
        cumul_jpy = initial_balance.get('jpy_eur', 0)
        
        negative_days = []
        risk_zones = {'Safe': 0, 'Warning': 0, 'Critical': 0}
        
        # Forecast loop (simplified - full version would be much longer)
        for day in range(forecast_days_count):
            forecast_date = start_date + timedelta(days=day)
            
            if forecast_date > max_forecast_date:
                break
            
            day_name = forecast_date.strftime('%A')
            
            # Base historical values by day of week
            base_credit = weekly_credit_pattern.get(day_name, avg_daily_credit)
            base_debit = weekly_debit_pattern.get(day_name, avg_daily_debit)
            
            # Get invoices for this day
            sales_day_df = sales_open[sales_open['payment_date'] == forecast_date] if len(sales_open) > 0 else pd.DataFrame()
            purchase_day_df = purchase_open[purchase_open['payment_date'] == forecast_date] if len(purchase_open) > 0 else pd.DataFrame()
            
            # Calculate invoice amounts by currency
            sales_day_eur = sales_day_df[sales_day_df['currency'] == 'EUR']['amount'].sum() if len(sales_day_df) > 0 else 0
            sales_day_usd = sales_day_df[sales_day_df['currency'] == 'USD']['amount'].sum() if len(sales_day_df) > 0 else 0
            sales_day_jpy = sales_day_df[sales_day_df['currency'] == 'JPY']['amount'].sum() if len(sales_day_df) > 0 else 0
            
            purchase_day_eur = purchase_day_df[purchase_day_df['currency'] == 'EUR']['amount'].sum() if len(purchase_day_df) > 0 else 0
            purchase_day_usd = purchase_day_df[purchase_day_df['currency'] == 'USD']['amount'].sum() if len(purchase_day_df) > 0 else 0
            purchase_day_jpy = purchase_day_df[purchase_day_df['currency'] == 'JPY']['amount'].sum() if len(purchase_day_df) > 0 else 0
            
            # Apply adjustments
            inflation_adjustment = 1 + (inflation_rate * day / 365) if inflation_rate else 1.0
            
            np.random.seed(100 + day)
            volume_adj_credit = 1 + np.random.normal(0, volume_volatility_credit * 0.3) if volume_volatility_credit else 1.0
            volume_adj_credit = max(0.5, volume_adj_credit)
            
            volume_adj_debit = 1 + np.random.normal(0, volume_volatility_debit * 0.3) if volume_volatility_debit else 1.0
            volume_adj_debit = max(0.5, volume_adj_debit)
            
            # Calculate credits and debits
            # Simplified: using default proportions (EUR 86%, USD 4%, JPY 14%)
            credit_eur = (base_credit * 0.86 + sales_day_eur) * inflation_adjustment * volume_adj_credit
            credit_usd = (base_credit * 0.04 + sales_day_usd) * inflation_adjustment * volume_adj_credit
            credit_jpy = (base_credit * 0.14 + sales_day_jpy) * inflation_adjustment * volume_adj_credit
            
            # Recurring payments (first day of month)
            recurring_eur = avg_monthly_recurring if forecast_date.day == 1 else 0
            
            debit_eur = (base_debit * 0.86 + purchase_day_eur + recurring_eur) * inflation_adjustment * volume_adj_debit
            debit_usd = (base_debit * 0.04 + purchase_day_usd) * inflation_adjustment * volume_adj_debit
            debit_jpy = (base_debit * 0.14 + purchase_day_jpy) * inflation_adjustment * volume_adj_debit
            
            # Net cash flow
            net_eur = credit_eur - debit_eur
            net_usd = credit_usd - debit_usd
            net_jpy = credit_jpy - debit_jpy
            
            # Update cumuls
            cumul_eur += net_eur
            cumul_usd += net_usd
            cumul_jpy += net_jpy
            cumul_total += net_eur + (net_usd * self.usd_rate) + (net_jpy * self.jpy_rate)
            
            # Risk assessment
            cumul_net = cumul_total - DEBT_PRINCIPAL
            if cumul_net < -100000:
                risk_level = 'Critical'
                risk_zones['Critical'] += 1
            elif cumul_net < 0:
                risk_level = 'Warning'
                risk_zones['Warning'] += 1
            else:
                risk_level = 'Safe'
                risk_zones['Safe'] += 1
            
            if cumul_net < 0:
                negative_days.append(forecast_date)
            
            # Store forecast day
            forecast_days.append({
                'Date': forecast_date.strftime('%Y-%m-%d'),
                'Jour': day_name,
                'Mois': forecast_date.strftime('%B'),
                'Encaissements': round(credit_eur + (credit_usd * self.usd_rate) + (credit_jpy * self.jpy_rate), 2),
                'Décaissements': round(debit_eur + (debit_usd * self.usd_rate) + (debit_jpy * self.jpy_rate), 2),
                'Cash_Flow_Net': round(net_eur + (net_usd * self.usd_rate) + (net_jpy * self.jpy_rate), 2),
                'Cumul_Total_EUR': round(cumul_total, 2),
                'Cumul_Net_EUR': round(cumul_net, 2),
                'Risk_Level_Net': risk_level
            })
        
        forecast_df = pd.DataFrame(forecast_days)
        
        # Find worst day
        if len(forecast_df) > 0:
            worst_idx = forecast_df['Cumul_Net_EUR'].idxmin()
            worst_day = forecast_df.loc[worst_idx]
        else:
            worst_day = pd.Series({'Date': start_date.strftime('%Y-%m-%d'), 'Cumul_Net_EUR': initial_balance['total_eur'] - DEBT_PRINCIPAL})
        
        return {
            'forecast_df': forecast_df,
            'start_date': start_date,
            'end_date': end_date,
            'forecast_days_count': len(forecast_df),
            'initial_balance': initial_balance['total_eur'],
            'initial_balance_net': initial_balance['total_eur'] - DEBT_PRINCIPAL,
            'final_balance': cumul_total,
            'final_balance_net': cumul_total - DEBT_PRINCIPAL,
            'negative_days': negative_days,
            'risk_zones': risk_zones,
            'worst_day': worst_day,
            'sales_open': sales_open,
            'purchase_open': purchase_open
        }


def run_forecast(
    bank: pd.DataFrame,
    sales: pd.DataFrame,
    purchase: pd.DataFrame,
    start_date: date,
    fx_rates: Dict[str, float],
    dso_mean: float,
    dpo_mean: float,
    avg_daily_credit: float,
    avg_daily_debit: float,
    std_daily_credit: float,
    std_daily_debit: float,
    weekly_credit_pattern: Dict[str, float],
    weekly_debit_pattern: Dict[str, float],
    inflation_rate: float,
    volume_volatility_credit: float,
    volume_volatility_debit: float,
    max_forecast_date: date
) -> Dict:
    """
    Convenience function to run forecast.
    """
    engine = ForecastEngine(bank, sales, purchase, fx_rates)
    return engine.run_forecast(
        start_date, dso_mean, dpo_mean,
        avg_daily_credit, avg_daily_debit,
        std_daily_credit, std_daily_debit,
        weekly_credit_pattern, weekly_debit_pattern,
        inflation_rate, volume_volatility_credit, volume_volatility_debit,
        max_forecast_date
    )

