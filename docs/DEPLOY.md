# 🚀 Guide de Déploiement

## Déploiement sur Streamlit Cloud

### Étape 1: Préparer le Repository GitHub

1. **Créer un nouveau repository sur GitHub**
   ```bash
   # Sur GitHub, créez un nouveau repository nommé "cash-flow-forecasting"
   ```

2. **Initialiser Git dans le projet**
   ```bash
   cd deliverables_improved/Python
   git init
   git add .
   git commit -m "Initial commit - Version améliorée"
   ```

3. **Connecter au repository GitHub**
   ```bash
   git remote add origin https://github.com/VOTRE-USERNAME/cash-flow-forecasting.git
   git branch -M main
   git push -u origin main
   ```

### Étape 2: Déployer sur Streamlit Cloud

1. **Aller sur Streamlit Cloud**
   - Visitez [share.streamlit.io](https://share.streamlit.io)
   - Connectez-vous avec votre compte GitHub

2. **Nouvelle App**
   - Cliquez sur "New app"
   - Sélectionnez votre repository: `VOTRE-USERNAME/cash-flow-forecasting`
   - Sélectionnez la branche: `main`
   - **Chemin du fichier principal**: `Python/streamlit_app.py`
   - Cliquez sur "Deploy"

3. **Configuration (optionnel)**
   - Si vous avez des secrets (API keys, etc.), ajoutez-les dans les paramètres de l'app

### Étape 3: Vérifier le Déploiement

- Streamlit Cloud va automatiquement:
  - Installer les dépendances depuis `requirements.txt`
  - Lancer `streamlit_app.py`
  - Créer une URL publique pour votre app

## Structure Requise pour Streamlit Cloud

```
cash-flow-forecasting/
├── Python/
│   ├── streamlit_app.py    # ⚠️ Point d'entrée principal
│   ├── requirements.txt    # ⚠️ Dépendances
│   ├── .streamlit/
│   │   └── config.toml     # Configuration Streamlit
│   └── src/                # Code source
└── README.md
```

## Fichiers Importants

- ✅ `streamlit_app.py` - Point d'entrée pour Streamlit Cloud
- ✅ `requirements.txt` - Dépendances Python
- ✅ `.streamlit/config.toml` - Configuration Streamlit
- ✅ `.gitignore` - Fichiers à exclure de Git

## Notes Importantes

1. **Données CSV**: 
   - Les fichiers CSV doivent être dans le repository ou
   - Utiliser Streamlit Secrets pour les données sensibles
   - Ou charger depuis une URL externe

2. **Chemins de fichiers**:
   - Utilisez des chemins relatifs
   - Le répertoire de travail est la racine du repository

3. **Dépendances**:
   - Toutes les dépendances doivent être dans `requirements.txt`
   - Streamlit Cloud installe automatiquement

## Dépannage

### Erreur: "Module not found"
- Vérifiez que tous les imports sont corrects
- Vérifiez que `requirements.txt` contient toutes les dépendances

### Erreur: "File not found"
- Vérifiez les chemins relatifs
- Les fichiers doivent être dans le repository

### L'app ne se charge pas
- Vérifiez les logs dans Streamlit Cloud
- Vérifiez que `streamlit_app.py` existe et est correct

## Mise à Jour

Pour mettre à jour l'app:
```bash
git add .
git commit -m "Update app"
git push
```

Streamlit Cloud redéploiera automatiquement!

