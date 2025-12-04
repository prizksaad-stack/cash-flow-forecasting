# 📦 Configuration GitHub - Guide Rapide

## 🚀 Créer le Repository GitHub

### Option 1: Via l'Interface GitHub (Recommandé)

1. **Aller sur GitHub.com**
   - Connectez-vous à votre compte
   - Cliquez sur le "+" en haut à droite
   - Sélectionnez "New repository"

2. **Configurer le Repository**
   - **Nom**: `cash-flow-forecasting` (ou un nom de votre choix)
   - **Description**: "Cash Flow Forecasting System - Version Améliorée"
   - **Visibilité**: Public (pour Streamlit Cloud gratuit) ou Private
   - **NE PAS** cocher "Initialize with README" (on a déjà un README)
   - Cliquez sur "Create repository"

3. **Copier l'URL du repository**
   - Exemple: `https://github.com/VOTRE-USERNAME/cash-flow-forecasting.git`

### Option 2: Via la Ligne de Commande

```bash
# Aller dans le répertoire Python
cd deliverables_improved/Python

# Initialiser Git (si pas déjà fait)
git init

# Ajouter tous les fichiers
git add .

# Premier commit
git commit -m "Initial commit - Version améliorée avec architecture modulaire"

# Ajouter le remote (remplacez VOTRE-USERNAME)
git remote add origin https://github.com/VOTRE-USERNAME/cash-flow-forecasting.git

# Pousser vers GitHub
git branch -M main
git push -u origin main
```

## 📋 Checklist Avant de Pousser

- [ ] Vérifier que `.gitignore` est présent
- [ ] Vérifier que `requirements.txt` est complet
- [ ] Vérifier que `streamlit_app.py` existe
- [ ] Vérifier que `README.md` est à jour
- [ ] Vérifier que les fichiers CSV ne sont pas dans `.gitignore` (ou les ajouter si nécessaire)

## 🔒 Fichiers Sensibles

Si vous avez des données sensibles:
1. Ajoutez-les à `.gitignore`
2. Utilisez Streamlit Secrets pour les données sensibles en production

## ✅ Vérification

Après avoir poussé, vérifiez sur GitHub:
- [ ] Tous les fichiers sont présents
- [ ] Le README s'affiche correctement
- [ ] La structure des dossiers est correcte

## 🔗 Prochaines Étapes

Une fois le repository créé, suivez le guide `DEPLOY.md` pour déployer sur Streamlit Cloud!

