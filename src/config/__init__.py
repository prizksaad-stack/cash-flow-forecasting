"""
Configuration module for Cash Flow Forecasting
"""
from .settings import (
    Config,
    get_config,
    DEBT_PRINCIPAL,
    DEBT_SPREAD,
    EURIBOR_3M_BASE,
    DEBT_INTEREST_RATE,
    DEBT_MONTHLY_INTEREST,
    MAX_FORECAST_DATE
)

__all__ = [
    'Config',
    'get_config',
    'DEBT_PRINCIPAL',
    'DEBT_SPREAD',
    'EURIBOR_3M_BASE',
    'DEBT_INTEREST_RATE',
    'DEBT_MONTHLY_INTEREST',
    'MAX_FORECAST_DATE'
]

