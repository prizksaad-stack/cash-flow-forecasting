# 🚀 Démarrage Rapide

## Pour Déployer sur GitHub et Streamlit Cloud

### Étape 1: Initialiser Git (Optionnel - Script Automatique)

```bash
cd deliverables_improved/Python
./init_git.sh
```

Ou manuellement:
```bash
git init
git add .
git commit -m "Initial commit - Version améliorée"
```

### Étape 2: Créer le Repository GitHub

1. Allez sur [GitHub.com](https://github.com)
2. Créez un nouveau repository nommé `cash-flow-forecasting`
3. **NE PAS** initialiser avec README (on en a déjà un)

### Étape 3: Connecter et Pousser

```bash
# Remplacez VOTRE-USERNAME par votre nom d'utilisateur GitHub
git remote add origin https://github.com/VOTRE-USERNAME/cash-flow-forecasting.git
git branch -M main
git push -u origin main
```

### Étape 4: Déployer sur Streamlit Cloud

1. Allez sur [share.streamlit.io](https://share.streamlit.io)
2. Connectez-vous avec GitHub
3. Cliquez sur "New app"
4. Sélectionnez votre repository
5. **Chemin du fichier**: `Python/streamlit_app.py`
6. Cliquez sur "Deploy"

### ✅ C'est tout!

Votre app sera disponible sur une URL comme:
`https://your-app-name.streamlit.app`

## 📚 Documentation Complète

- **GITHUB_SETUP.md** - Guide détaillé pour GitHub
- **DEPLOY.md** - Guide détaillé pour Streamlit Cloud
- **VERIFICATION.md** - Tests et vérifications
- **README.md** - Documentation principale

## 🐛 Problèmes?

Consultez **VERIFICATION.md** pour les solutions aux problèmes courants.

