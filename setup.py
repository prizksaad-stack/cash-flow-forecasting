"""
Setup script for Cash Flow Forecasting package
"""
from setuptools import setup, find_packages

setup(
    name="cash-flow-forecasting",
    version="2.0.0",
    description="Cash Flow Forecasting System with Modular Architecture",
    author="Capstone Project",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "streamlit>=1.28.0",
        "plotly>=5.17.0",
        "matplotlib>=3.7.0",
        "requests>=2.31.0",
    ],
    python_requires=">=3.8",
)

