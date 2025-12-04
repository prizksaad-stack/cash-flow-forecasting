#!/bin/bash
# Script simplifié pour créer le repo GitHub avec votre token

set -e

REPO_NAME="cash-flow-forecasting"
echo "🚀 Création du repository GitHub: $REPO_NAME"
echo ""

# Demander le token si pas dans l'environnement
if [ -z "$GITHUB_TOKEN" ]; then
    echo "🔑 Entrez votre token GitHub:"
    echo "   (Créez-en un sur: https://github.com/settings/tokens)"
    read -s GITHUB_TOKEN
    echo ""
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Token requis"
    exit 1
fi

# Obtenir le username
echo "🔍 Récupération de votre nom d'utilisateur GitHub..."
USERNAME=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | grep -o '"login":"[^"]*' | cut -d'"' -f4)

if [ -z "$USERNAME" ]; then
    echo "❌ Token invalide"
    exit 1
fi

echo "✅ Authentifié en tant que: $USERNAME"
echo ""

# Créer le repository
echo "📦 Création du repository sur GitHub..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"Cash Flow Forecasting System - Version Améliorée\",\"private\":false}")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "201" ]; then
    echo "✅ Repository créé avec succès!"
elif [ "$HTTP_CODE" = "422" ]; then
    echo "⚠️  Le repository existe peut-être déjà, continuation..."
else
    echo "❌ Erreur: Code HTTP $HTTP_CODE"
    echo "$RESPONSE" | sed '$d'
    exit 1
fi

# Configurer Git et pousser
echo ""
echo "📤 Configuration de Git et push du code..."

# Vérifier si Git est initialisé
if [ ! -d ".git" ]; then
    git init
    git add .
    git commit -m "Initial commit - Cash Flow Forecasting v2.0"
fi

# Ajouter le remote
git remote remove origin 2>/dev/null || true
git remote add origin "https://$GITHUB_TOKEN@github.com/$USERNAME/$REPO_NAME.git"
git branch -M main

# Pousser
echo "📤 Push du code..."
git push -u origin main

# Retirer le token de l'URL pour sécurité
git remote set-url origin "https://github.com/$USERNAME/$REPO_NAME.git"

echo ""
echo "✅ Déploiement terminé!"
echo "🌐 Repository: https://github.com/$USERNAME/$REPO_NAME"
echo ""
echo "📚 Prochaine étape: Déployez sur Streamlit Cloud"
echo "   1. Allez sur https://share.streamlit.io"
echo "   2. Sélectionnez votre repository"
echo "   3. Chemin: Python/streamlit_app.py"

