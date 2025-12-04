# 🚀 Guide de Déploiement sur Streamlit Cloud

## 📋 Prérequis

- ✅ Repository GitHub: `prizksaad-stack/cash-flow-forecasting`
- ✅ Code poussé sur GitHub
- ✅ Compte Streamlit Cloud (gratuit)

## 🎯 Étapes de Déploiement

### Étape 1: Accéder à Streamlit Cloud

1. Allez sur **[share.streamlit.io](https://share.streamlit.io)**
2. Cliquez sur **"Sign in"** en haut à droite
3. Connectez-vous avec votre compte **GitHub**

### Étape 2: Créer une Nouvelle App

1. Une fois connecté, cliquez sur **"New app"** (bouton en haut à droite)
2. Vous arrivez sur la page "Deploy an app"

### Étape 3: Configurer l'App

Remplissez le formulaire avec ces informations:

#### Repository
- **Repository**: `prizksaad-stack/cash-flow-forecasting`
  - Vous pouvez aussi cliquer sur "Paste GitHub URL" et coller: 
    `https://github.com/prizksaad-stack/cash-flow-forecasting`

#### Branch
- **Branch**: `main`

#### Main file path
- **Main file path**: `streamlit_app.py`
  - ⚠️ **IMPORTANT**: Le fichier est à la racine, pas dans un dossier Python/
  - ✅ Utilisez: `streamlit_app.py`
  - ❌ PAS: `Python/streamlit_app.py`

#### App URL (optionnel)
- Laissez le nom généré automatiquement ou choisissez un nom personnalisé
- Exemple: `cash-flow-forecasting` (si disponible)
- L'URL finale sera: `https://cash-flow-forecasting.streamlit.app`

### Étape 4: Déployer

1. Cliquez sur le bouton **"Deploy"** en bas
2. Streamlit Cloud va:
   - Cloner votre repository
   - Installer les dépendances depuis `requirements.txt`
   - Lancer `streamlit_app.py`
   - Créer votre app publique

### Étape 5: Attendre le Déploiement

- Le déploiement prend généralement **1-3 minutes**
- Vous verrez les logs en temps réel
- Une fois terminé, vous verrez **"Your app is live!"**

## ✅ Vérification

Une fois déployé, vous pouvez:
- ✅ Accéder à votre app via l'URL fournie
- ✅ Partager l'URL avec d'autres personnes
- ✅ Voir les logs dans l'onglet "Logs"
- ✅ Gérer l'app dans "Settings"

## 🔧 Configuration Avancée (Optionnel)

### Secrets (si nécessaire)

Si vous avez des données sensibles (API keys, tokens):

1. Allez dans **"Settings"** de votre app
2. Section **"Secrets"**
3. Ajoutez vos secrets au format TOML:

```toml
[secrets]
api_key = "votre_cle_api"
```

### Variables d'Environnement

Dans "Settings" → "Advanced settings", vous pouvez ajouter des variables d'environnement.

## 🐛 Dépannage

### Erreur: "This file does not exist"

**Solution**: Vérifiez que le chemin est `streamlit_app.py` (pas `Python/streamlit_app.py`)

### Erreur: "Module not found"

**Solution**: Vérifiez que `requirements.txt` contient toutes les dépendances

### L'app ne se charge pas

**Solution**: 
1. Vérifiez les logs dans l'onglet "Logs"
2. Vérifiez que `streamlit_app.py` existe bien dans le repository
3. Vérifiez que les imports sont corrects

### Erreur de chemin pour les données CSV

**Solution**: Les fichiers CSV doivent être dans le repository ou accessibles via une URL

## 📝 Notes Importantes

1. **Fichier principal**: `streamlit_app.py` doit être à la racine du repository
2. **Dépendances**: Toutes les dépendances doivent être dans `requirements.txt`
3. **Données**: Les fichiers CSV doivent être dans le repository ou accessibles
4. **Mises à jour**: Chaque push sur `main` redéploie automatiquement l'app

## 🔄 Mise à Jour

Pour mettre à jour l'app:
1. Faites vos modifications localement
2. Commitez et poussez vers GitHub:
   ```bash
   git add .
   git commit -m "Update app"
   git push origin main
   ```
3. Streamlit Cloud redéploiera automatiquement!

## 📚 Ressources

- [Documentation Streamlit Cloud](https://docs.streamlit.io/streamlit-community-cloud)
- [Guide de déploiement officiel](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app)

---

**🎉 Votre app sera disponible publiquement sur une URL comme:**
`https://cash-flow-forecasting.streamlit.app`

