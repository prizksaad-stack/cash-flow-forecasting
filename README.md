# 📊 Cash Flow Forecasting - Version Améliorée

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-name.streamlit.app)

Système de prévision de trésorerie avec architecture modulaire et dashboard interactif.

## 🎯 Fonctionnalités

- ✅ **Forecast quotidien** sur 90 jours
- ✅ **Gestion multi-devises** (EUR, USD, JPY)
- ✅ **Détection de risques** automatique
- ✅ **Dashboard interactif** avec Streamlit
- ✅ **Architecture modulaire** et maintenable
- ✅ **Calculs académiques** (DSO, DPO, Direct Method)

## 🚀 Déploiement Rapide

### Sur Streamlit Cloud

1. Forkez ce repository
2. Allez sur [Streamlit Cloud](https://streamlit.io/cloud)
3. Connectez votre compte GitHub
4. Sélectionnez ce repository
5. Configurez le chemin: `Python/streamlit_app.py`
6. Déployez!

### Localement

```bash
# Cloner le repository
git clone https://github.com/votre-username/cash-flow-forecasting.git
cd cash-flow-forecasting/Python

# Installer les dépendances
pip install -r requirements.txt

# Lancer le dashboard
streamlit run streamlit_app.py
```

## 📁 Structure du Projet

```
Python/
├── streamlit_app.py      # Point d'entrée pour Streamlit Cloud
├── main.py               # Point d'entrée local
├── requirements.txt      # Dépendances Python
├── src/                 # Code source modulaire
│   ├── config/         # Configuration
│   ├── data/           # Chargement et traitement des données
│   ├── forecast/       # Moteur de prévision
│   ├── utils/          # Utilitaires
│   └── dashboard/      # Interface Streamlit
└── README.md
```

## 📋 Prérequis

- Python 3.8+
- Les fichiers CSV de données dans le répertoire parent:
  - `bank_transactions.csv`
  - `sales_invoices.csv`
  - `purchase_invoices.csv`

## 🔧 Configuration

Les paramètres sont dans `src/config/settings.py`:
- Dette: €20M à taux variable (Euribor 3M + 1.2%)
- Date maximale de forecast: 31 mars 2025
- Chemins des fichiers

## 📊 Utilisation

### Mode Dashboard (Recommandé)

```bash
streamlit run streamlit_app.py
```

### Mode Script

```bash
python main.py --script
```

## 🧪 Tests

```bash
# Vérifier les imports
python3 -c "import sys; sys.path.insert(0, 'src'); from config import get_config; print('OK')"
```

## 📚 Documentation

- [README_IMPROVED.md](README_IMPROVED.md) - Documentation détaillée
- [CHANGELOG.md](CHANGELOG.md) - Liste des améliorations

## 🤝 Contribution

Les contributions sont les bienvenues! N'hésitez pas à ouvrir une issue ou une pull request.

## 📝 Licence

Ce projet est un projet académique.

## 👤 Auteur

Projet développé dans le cadre d'un capstone.

## 🙏 Remerciements

- Streamlit pour le framework de dashboard
- Pandas et NumPy pour le traitement de données
- Plotly pour les visualisations interactives

