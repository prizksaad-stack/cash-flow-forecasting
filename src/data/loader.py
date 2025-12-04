"""
Data loading module for Cash Flow Forecasting

This module handles loading CSV files and basic data validation.
"""
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
import warnings

warnings.filterwarnings('ignore')


class DataLoader:
    """
    Handles loading of CSV data files for cash flow forecasting.
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize the DataLoader.
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
    
    def load_bank_transactions(self) -> pd.DataFrame:
        """
        Load bank transactions CSV file.
        
        Returns:
            DataFrame with bank transactions
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file cannot be parsed
        """
        file_path = self.data_dir / 'bank_transactions.csv'
        
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        try:
            df = pd.read_csv(file_path, parse_dates=['date'])
            return df
        except Exception as e:
            raise ValueError(f"Erreur lors du chargement de {file_path}: {e}")
    
    def load_sales_invoices(self) -> pd.DataFrame:
        """
        Load sales invoices CSV file.
        
        Returns:
            DataFrame with sales invoices
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file cannot be parsed
        """
        file_path = self.data_dir / 'sales_invoices.csv'
        
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        try:
            df = pd.read_csv(
                file_path,
                parse_dates=['issue_date', 'due_date', 'payment_date']
            )
            return df
        except Exception as e:
            raise ValueError(f"Erreur lors du chargement de {file_path}: {e}")
    
    def load_purchase_invoices(self) -> pd.DataFrame:
        """
        Load purchase invoices CSV file.
        
        Returns:
            DataFrame with purchase invoices
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file cannot be parsed
        """
        file_path = self.data_dir / 'purchase_invoices.csv'
        
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        try:
            df = pd.read_csv(
                file_path,
                parse_dates=['issue_date', 'due_date', 'payment_date']
            )
            return df
        except Exception as e:
            raise ValueError(f"Erreur lors du chargement de {file_path}: {e}")
    
    def load_all(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Load all required CSV files.
        
        Returns:
            Tuple of (bank_transactions, sales_invoices, purchase_invoices)
            
        Raises:
            FileNotFoundError: If any file doesn't exist
            ValueError: If any file cannot be parsed
        """
        bank = self.load_bank_transactions()
        sales = self.load_sales_invoices()
        purchase = self.load_purchase_invoices()
        
        return bank, sales, purchase


def load_all_data(data_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Convenience function to load all data files.
    
    Args:
        data_dir: Directory containing CSV files
        
    Returns:
        Tuple of (bank_transactions, sales_invoices, purchase_invoices)
    """
    loader = DataLoader(data_dir)
    return loader.load_all()

