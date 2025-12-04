#!/bin/bash
# Script d'initialisation Git pour le projet

echo "🚀 Initialisation du repository Git..."
echo ""

# Vérifier si Git est installé
if ! command -v git &> /dev/null; then
    echo "❌ Git n'est pas installé. Veuillez installer Git d'abord."
    exit 1
fi

# Vérifier si déjà un repo Git
if [ -d ".git" ]; then
    echo "⚠️  Un repository Git existe déjà."
    read -p "Voulez-vous continuer? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Initialiser Git
echo "📦 Initialisation du repository..."
git init

# Ajouter tous les fichiers
echo "📝 Ajout des fichiers..."
git add .

# Premier commit
echo "💾 Création du premier commit..."
git commit -m "Initial commit - Cash Flow Forecasting v2.0 (Architecture modulaire)"

echo ""
echo "✅ Repository Git initialisé!"
echo ""
echo "📋 Prochaines étapes:"
echo "1. Créez un nouveau repository sur GitHub"
echo "2. Exécutez:"
echo "   git remote add origin https://github.com/VOTRE-USERNAME/cash-flow-forecasting.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "📖 Consultez GITHUB_SETUP.md pour plus de détails"

