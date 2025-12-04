#!/bin/bash
# Script pour créer le repository GitHub et pousser le code automatiquement

set -e  # Arrêter en cas d'erreur

echo "🚀 Déploiement automatique vers GitHub"
echo "========================================"
echo ""

# Vérifier si Git est installé
if ! command -v git &> /dev/null; then
    echo "❌ Git n'est pas installé. Veuillez installer Git d'abord."
    exit 1
fi

# Vérifier si gh CLI est installé (GitHub CLI)
if ! command -v gh &> /dev/null; then
    echo "⚠️  GitHub CLI (gh) n'est pas installé."
    echo "📦 Installation recommandée: brew install gh"
    echo ""
    echo "Alternative: Utilisez votre token GitHub manuellement"
    echo ""
    read -p "Voulez-vous continuer avec Git seulement? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    USE_GH_CLI=false
else
    USE_GH_CLI=true
    echo "✅ GitHub CLI détecté"
fi

# Initialiser Git si nécessaire
if [ ! -d ".git" ]; then
    echo "📦 Initialisation du repository Git..."
    git init
    git add .
    git commit -m "Initial commit - Cash Flow Forecasting v2.0 (Architecture modulaire)"
    echo "✅ Repository Git initialisé"
else
    echo "✅ Repository Git existe déjà"
    # Vérifier s'il y a des changements non commités
    if ! git diff-index --quiet HEAD --; then
        echo "📝 Ajout des changements..."
        git add .
        git commit -m "Update - Cash Flow Forecasting v2.0"
    fi
fi

# Nom du repository
REPO_NAME="cash-flow-forecasting"
echo ""
echo "📋 Nom du repository: $REPO_NAME"
read -p "Voulez-vous utiliser un autre nom? (appuyez sur Entrée pour garder $REPO_NAME): " CUSTOM_NAME
if [ ! -z "$CUSTOM_NAME" ]; then
    REPO_NAME="$CUSTOM_NAME"
fi

# Vérifier si le remote existe déjà
if git remote get-url origin &> /dev/null; then
    echo "⚠️  Un remote 'origin' existe déjà"
    CURRENT_URL=$(git remote get-url origin)
    echo "   URL actuelle: $CURRENT_URL"
    read -p "Voulez-vous le remplacer? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git remote remove origin
    else
        echo "✅ Utilisation du remote existant"
        echo "💡 Pour pousser: git push -u origin main"
        exit 0
    fi
fi

# Méthode 1: Utiliser GitHub CLI (si disponible)
if [ "$USE_GH_CLI" = true ]; then
    echo ""
    echo "🔐 Vérification de l'authentification GitHub..."
    if gh auth status &> /dev/null; then
        echo "✅ Authentifié avec GitHub CLI"
        
        # Créer le repository
        echo ""
        echo "📦 Création du repository sur GitHub..."
        gh repo create "$REPO_NAME" --public --source=. --remote=origin --push
        
        echo ""
        echo "✅ Repository créé et code poussé avec succès!"
        echo "🌐 URL: https://github.com/$(gh api user --jq .login)/$REPO_NAME"
        
    else
        echo "❌ Non authentifié avec GitHub CLI"
        echo "💡 Authentifiez-vous avec: gh auth login"
        USE_GH_CLI=false
    fi
fi

# Méthode 2: Utiliser token GitHub manuellement
if [ "$USE_GH_CLI" = false ]; then
    echo ""
    echo "🔑 Configuration avec token GitHub"
    echo "=================================="
    echo ""
    echo "Pour créer le repository, vous avez besoin d'un token GitHub:"
    echo "1. Allez sur: https://github.com/settings/tokens"
    echo "2. Créez un token avec les permissions 'repo'"
    echo "3. Copiez le token"
    echo ""
    read -p "Entrez votre token GitHub (ou appuyez sur Entrée pour le faire manuellement): " GITHUB_TOKEN
    
    if [ ! -z "$GITHUB_TOKEN" ]; then
        # Obtenir le nom d'utilisateur
        echo "🔍 Récupération du nom d'utilisateur..."
        USERNAME=$(curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | grep -o '"login":"[^"]*' | cut -d'"' -f4)
        
        if [ -z "$USERNAME" ]; then
            echo "❌ Token invalide ou erreur d'authentification"
            exit 1
        fi
        
        echo "✅ Authentifié en tant que: $USERNAME"
        
        # Créer le repository via API
        echo ""
        echo "📦 Création du repository sur GitHub..."
        RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Authorization: token $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/user/repos \
            -d "{\"name\":\"$REPO_NAME\",\"description\":\"Cash Flow Forecasting System - Version Améliorée\",\"private\":false}")
        
        HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
        BODY=$(echo "$RESPONSE" | sed '$d')
        
        if [ "$HTTP_CODE" = "201" ] || [ "$HTTP_CODE" = "422" ]; then
            if [ "$HTTP_CODE" = "422" ]; then
                echo "⚠️  Le repository existe peut-être déjà, continuation..."
            else
                echo "✅ Repository créé avec succès!"
            fi
            
            # Ajouter le remote et pousser
            echo ""
            echo "📤 Ajout du remote et push du code..."
            git remote add origin "https://$GITHUB_TOKEN@github.com/$USERNAME/$REPO_NAME.git"
            git branch -M main
            git push -u origin main
            
            # Retirer le token de l'URL pour sécurité
            git remote set-url origin "https://github.com/$USERNAME/$REPO_NAME.git"
            
            echo ""
            echo "✅ Code poussé avec succès!"
            echo "🌐 URL: https://github.com/$USERNAME/$REPO_NAME"
        else
            echo "❌ Erreur lors de la création du repository"
            echo "Code HTTP: $HTTP_CODE"
            echo "Réponse: $BODY"
            exit 1
        fi
    else
        echo ""
        echo "📋 Instructions manuelles:"
        echo "=========================="
        echo ""
        echo "1. Créez le repository sur GitHub.com:"
        echo "   https://github.com/new"
        echo "   Nom: $REPO_NAME"
        echo ""
        echo "2. Puis exécutez:"
        echo "   git remote add origin https://github.com/VOTRE-USERNAME/$REPO_NAME.git"
        echo "   git branch -M main"
        echo "   git push -u origin main"
        echo ""
    fi
fi

echo ""
echo "🎉 Déploiement terminé!"
echo ""
echo "📚 Prochaines étapes:"
echo "1. Déployez sur Streamlit Cloud: https://share.streamlit.io"
echo "2. Chemin du fichier: Python/streamlit_app.py"
echo "3. Consultez DEPLOY.md pour plus de détails"

