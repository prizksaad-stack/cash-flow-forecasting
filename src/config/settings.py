"""
Configuration settings for Cash Flow Forecasting System

This module contains all configuration constants and settings used throughout
the cash flow forecasting application.
"""
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass


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

# Date maximale pour le forecast
MAX_FORECAST_DATE = datetime(2025, 3, 31).date()


@dataclass
class Config:
    """
    Configuration class for the Cash Flow Forecasting system.
    
    Attributes:
        root_dir: Root directory of the project (deliverables/)
        data_dir: Directory containing CSV data files
        output_dir: Directory for output files
        bdd_dir: Directory for forecast results (bdd/)
        max_forecast_date: Maximum date for forecasting
        debt_principal: Principal amount of debt in EUR
        debt_interest_rate: Annual interest rate for debt
        debt_monthly_interest: Monthly interest payment in EUR
    """
    root_dir: Path
    data_dir: Path
    output_dir: Path
    bdd_dir: Path
    max_forecast_date: datetime.date
    debt_principal: float = DEBT_PRINCIPAL
    debt_interest_rate: float = DEBT_INTEREST_RATE
    debt_monthly_interest: float = DEBT_MONTHLY_INTEREST
    
    @classmethod
    def from_script_path(cls, script_path: Path) -> 'Config':
        """
        Create a Config instance from a script path.
        
        Args:
            script_path: Path to the main script file
            
        Returns:
            Config instance with paths relative to script location
        """
        root_dir = script_path.parent.parent  # deliverables/
        return cls(
            root_dir=root_dir,
            data_dir=root_dir,  # deliverables/ (where CSV files are)
            output_dir=script_path.parent,  # deliverables/Python/
            bdd_dir=root_dir / 'bdd',  # bdd/ in deliverables/
            max_forecast_date=MAX_FORECAST_DATE
        )
    
    def ensure_directories(self) -> None:
        """Create output directories if they don't exist."""
        self.bdd_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


# Global config instance (will be initialized when needed)
_config: Config | None = None


def get_config(script_path: Path | None = None) -> Config:
    """
    Get or create the global configuration instance.
    
    Args:
        script_path: Optional path to script. If None, uses __file__ from caller
        
    Returns:
        Config instance
    """
    global _config
    
    if _config is None:
        if script_path is None:
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_file = frame.f_back.f_globals.get('__file__')
                if caller_file:
                    script_path = Path(caller_file).absolute()
                else:
                    # Fallback: assume we're in deliverables/Python/
                    script_path = Path(__file__).parent.parent.parent / 'cash_forecast_complete.py'
            else:
                script_path = Path(__file__).parent.parent.parent / 'cash_forecast_complete.py'
        
        _config = Config.from_script_path(Path(script_path).absolute())
        _config.ensure_directories()
    
    return _config

