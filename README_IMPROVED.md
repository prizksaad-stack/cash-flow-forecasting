# Cash Flow Forecasting - Version Améliorée

## 🎯 Vue d'ensemble

Cette version améliorée du système de prévision de trésorerie a été complètement refactorisée avec une architecture modulaire propre et maintenable.

## 📁 Structure du Projet

```
deliverables_improved/Python/
├── main.py                 # Point d'entrée principal
├── src/                    # Code source modulaire
│   ├── config/            # Configuration et paramètres
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── data/              # Chargement et traitement des données
│   │   ├── __init__.py
│   │   ├── loader.py      # Chargement des CSV
│   │   └── processor.py   # Calcul des métriques (DSO, DPO, etc.)
│   ├── forecast/          # Moteur de prévision
│   │   ├── __init__.py
│   │   └── engine.py      # Logique de forecast
│   ├── utils/             # Utilitaires
│   │   ├── __init__.py
│   │   ├── currency.py    # Conversion de devises
│   │   └── validation.py  # Validation des données
│   └── dashboard/         # Interface Streamlit (à créer)
│       └── app.py
├── requirements.txt
└── README_IMPROVED.md
```

## ✨ Améliorations Principales

### 1. Architecture Modulaire
- **Séparation des responsabilités**: Chaque module a une responsabilité claire
- **Réutilisabilité**: Les modules peuvent être utilisés indépendamment
- **Testabilité**: Chaque module peut être testé séparément

### 2. Gestion des Erreurs
- Validation des données d'entrée
- Gestion robuste des cas limites
- Messages d'erreur clairs et informatifs

### 3. Configuration Centralisée
- Tous les paramètres dans `config/settings.py`
- Facilite les modifications et la maintenance

### 4. Code Plus Propre
- Docstrings complètes
- Type hints pour meilleure lisibilité
- Conventions de nommage cohérentes

## 🚀 Installation

```bash
cd deliverables_improved/Python
pip install -r requirements.txt
```

## 📋 Utilisation

### Mode Dashboard (Interactif)

```bash
python main.py
```

Ou manuellement:

```bash
streamlit run main.py
```

### Mode Script (Forecast Complet)

```bash
python main.py --script
```

## 🔧 Modules

### Config (`src/config/`)
Gère toute la configuration du système:
- Chemins des fichiers
- Paramètres de dette (€20M)
- Dates limites
- Taux d'intérêt

### Data (`src/data/`)
Chargement et traitement des données:
- `loader.py`: Charge les fichiers CSV
- `processor.py`: Calcule DSO, DPO, statistiques quotidiennes, patterns hebdomadaires

### Forecast (`src/forecast/`)
Moteur de prévision:
- `engine.py`: Logique principale de forecast
- Gestion multi-devises (EUR, USD, JPY)
- Calcul des risques
- Détection des jours critiques

### Utils (`src/utils/`)
Utilitaires partagés:
- `currency.py`: Conversion de devises avec API
- `validation.py`: Validation des données et paramètres

## 📝 Notes

- **Version améliorée**: Cette version est une refactorisation complète du code original
- **Compatibilité**: Les résultats devraient être identiques au code original
- **Performance**: Code optimisé et plus efficace
- **Maintenance**: Plus facile à maintenir et étendre

## 🔄 Migration depuis l'Ancienne Version

L'ancienne version (`cash_forecast_complete.py`) reste disponible dans le dossier `deliverables/Python/`.

Pour utiliser la nouvelle version:
1. Utilisez `deliverables_improved/Python/main.py` au lieu de `cash_forecast_complete.py`
2. La structure des données reste la même
3. Les formats de sortie sont compatibles

## 🐛 Dépannage

### Erreur d'import
Assurez-vous que vous êtes dans le bon répertoire:
```bash
cd deliverables_improved/Python
```

### Fichiers CSV non trouvés
Vérifiez que les fichiers CSV sont dans `deliverables_improved/`:
- `bank_transactions.csv`
- `sales_invoices.csv`
- `purchase_invoices.csv`

## 📚 Documentation

Pour plus de détails sur chaque module, consultez les docstrings dans les fichiers source.

## 🎓 Prochaines Étapes

- [ ] Compléter le module dashboard
- [ ] Ajouter des tests unitaires
- [ ] Optimiser les performances
- [ ] Ajouter plus de documentation

