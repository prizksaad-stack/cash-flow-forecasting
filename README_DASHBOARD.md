# 📊 Cash Flow Forecasting - Script Complet

## 🎯 Description

Fichier Python unique qui combine :
- ✅ Script de forecast complet (analyse, calculs, rapports)
- ✅ Dashboard interactif académique (méthodes, visualisations, calculs détaillés)

## 🚀 Installation

### 1. Installer les dépendances

```bash
cd deliverables/Python
../.venv/bin/pip install -r requirements_dashboard.txt
```

**OU** si vous utilisez un environnement virtuel activé:

```bash
pip install streamlit pandas numpy plotly matplotlib requests
```

## 📋 Utilisation

### Mode Dashboard (Interactif)

```bash
cd deliverables/Python
streamlit run cash_forecast_complete.py
```

Le dashboard s'ouvrira automatiquement dans votre navigateur à l'adresse `http://localhost:8501`

### Mode Script (Forecast Complet)

```bash
cd deliverables/Python
python cash_forecast_complete.py
```

Le script demandera une date de départ et générera les fichiers CSV, rapports et graphiques.

## 📑 Sections du Dashboard

### 1. 🏠 Vue d'ensemble
- Métriques principales
- Méthode utilisée (Direct Method)
- Processus en 8 étapes

### 2. 📚 Méthodes Académiques
- **DSO (Days Sales Outstanding)**: Définition, formule, calcul
- **DPO (Days Payable Outstanding)**: Définition, formule, calcul
- **Direct Method**: Principe, avantages, limitations
- **Classification Récurrent vs Non-récurrent**: Justification académique

### 3. 🔢 Calculs Détailés
Analyse approfondie de chaque variable avec:
- Formules mathématiques (LaTeX)
- Calculs détaillés étape par étape
- Justifications académiques
- Visualisations interactives

Variables disponibles:
- DSO (Days Sales Outstanding)
- DPO (Days Payable Outstanding)
- Inflation
- Volatilité des Volumes
- Taux d'Impayés
- Retards de Paiement
- Volatilité FX
- Solde Initial
- Forecast Quotidien

### 4. 📈 Visualisations
- Évolution temporelle des flux
- Pattern hebdomadaire
- Distribution par catégorie

### 5. ⚙️ Paramètres & Facteurs
Tous les facteurs d'impact calculés:
- Taux de change (USD, JPY)
- Inflation
- Retards de paiement
- Volatilité des volumes

### 6. 🎯 Recommandations
Affichage des recommandations générées par le script principal

## 🎨 Caractéristiques

- ✅ **Design moderne** avec CSS personnalisé
- ✅ **Visualisations interactives** avec Plotly
- ✅ **Formules mathématiques** en LaTeX
- ✅ **Justifications académiques** pour chaque calcul
- ✅ **Navigation intuitive** via sidebar
- ✅ **Responsive** et adaptatif

## 📝 Notes

- **Fichier unique** : `cash_forecast_complete.py` combine le script et le dashboard
- Le dashboard lit les données depuis les fichiers CSV dans `deliverables/`
- Les résultats du forecast sont lus depuis `deliverables/bdd/[DATE]/`
- Tous les calculs sont expliqués avec formules et justifications
- Le fichier détecte automatiquement le mode (dashboard ou script) selon la commande utilisée

## 🔧 Dépendances

- `streamlit`: Framework pour le dashboard
- `pandas`: Manipulation de données
- `numpy`: Calculs numériques
- `plotly`: Visualisations interactives

## 📚 Références Académiques

Les méthodes présentées suivent les standards académiques de:
- Cash Flow Forecasting (Direct Method)
- Working Capital Management (DSO/DPO)
- Treasury Risk Management
- Multi-currency Cash Management

