# ✅ Vérification du Projet

## Tests à Effectuer

### 1. Vérification des Imports

```bash
cd deliverables_improved/Python
python3 -c "
import sys
sys.path.insert(0, 'src')
from config import get_config
from data import load_all_data
from utils import get_real_exchange_rates
print('✅ Tous les imports fonctionnent')
"
```

### 2. Vérification de la Structure

Vérifiez que tous ces fichiers existent:
- [ ] `streamlit_app.py` - Point d'entrée Streamlit
- [ ] `main.py` - Point d'entrée local
- [ ] `requirements.txt` - Dépendances
- [ ] `.gitignore` - Fichiers à ignorer
- [ ] `.streamlit/config.toml` - Config Streamlit
- [ ] `src/config/` - Module config
- [ ] `src/data/` - Module data
- [ ] `src/forecast/` - Module forecast
- [ ] `src/utils/` - Module utils
- [ ] `src/dashboard/` - Module dashboard

### 3. Vérification des Fichiers CSV

Assurez-vous que les fichiers CSV sont accessibles:
- [ ] `../bank_transactions.csv` (parent de Python/)
- [ ] `../sales_invoices.csv`
- [ ] `../purchase_invoices.csv`

### 4. Test Local Streamlit

```bash
cd deliverables_improved/Python
streamlit run streamlit_app.py
```

L'app devrait s'ouvrir dans le navigateur.

### 5. Test Mode Script

```bash
cd deliverables_improved/Python
python3 main.py --script
```

## Erreurs Communes et Solutions

### Erreur: "Module not found"
**Solution**: Vérifiez que `src/` est dans le PYTHONPATH ou utilisez `sys.path.insert(0, 'src')`

### Erreur: "File not found" pour les CSV
**Solution**: Vérifiez que les fichiers CSV sont dans le répertoire parent de `Python/`

### Erreur: Import relatif
**Solution**: Utilisez des imports absolus avec `sys.path.insert(0, 'src')`

## Checklist Avant Déploiement

- [ ] Tous les tests passent
- [ ] Aucune erreur de linting
- [ ] `requirements.txt` est complet
- [ ] `.gitignore` est configuré
- [ ] `README.md` est à jour
- [ ] `streamlit_app.py` fonctionne localement

