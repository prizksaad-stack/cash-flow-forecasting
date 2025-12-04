#!/bin/bash
# Script d'installation des dépendances Python
# Utilise .venv si disponible, sinon installe globalement

echo "Installation des dépendances Python..."

if [ -d "../.venv" ]; then
    echo "Utilisation de .venv..."
    ../.venv/bin/pip install pandas matplotlib openpyxl numpy requests
else
    echo "Installation globale (peut nécessiter sudo)..."
    python3 -m pip install --user pandas matplotlib openpyxl numpy requests
fi

echo "✓ Dépendances installées"

