# 📋 Détail du Processus de Forecast - 8 Étapes

Ce document détaille chaque étape du processus de forecast implémenté dans le système de Cash Flow Forecasting.

---

## 1️⃣ Chargement & Nettoyage
**Lecture des CSV, détection d'anomalies, calcul DSO/DPO**

### Ce qui a été fait :

#### **A. Chargement des fichiers CSV**
- **Fichiers chargés** :
  - `bank_transactions.csv` : Transactions bancaires (date, account, currency, type, amount, category, counterparty)
  - `sales_invoices.csv` : Factures clients (issue_date, due_date, payment_date, amount, currency, status)
  - `purchase_invoices.csv` : Factures fournisseurs (issue_date, due_date, payment_date, amount, currency, status)

- **Implémentation** (`src/data/loader.py`) :
  ```python
  - DataLoader.load_bank_transactions() : Charge avec parse_dates=['date']
  - DataLoader.load_sales_invoices() : Charge avec parse_dates=['issue_date', 'due_date', 'payment_date']
  - DataLoader.load_purchase_invoices() : Charge avec parse_dates=['issue_date', 'due_date', 'payment_date']
  ```

#### **B. Nettoyage et validation**
- **Gestion des erreurs** :
  - Vérification de l'existence des fichiers (FileNotFoundError)
  - Gestion des erreurs de parsing (ValueError)
  - Validation des colonnes requises

- **Conversion des devises** :
  - Ajout de la colonne `amount_eur` pour toutes les transactions
  - Utilisation de l'API exchangerate-api.com pour les taux réels
  - Fallback sur taux moyens 2024 si API indisponible (USD: 0.92, JPY: 0.0065)

#### **C. Calcul DSO (Days Sales Outstanding)**
- **Méthode** (`src/data/processor.py`, lignes 54-87) :
  ```python
  1. Filtrer les factures avec status='Paid'
  2. Vérifier que payment_date ET issue_date sont valides (notna)
  3. Calculer days_to_pay = payment_date - issue_date
  4. DSO moyen = moyenne des days_to_pay
  ```

- **Gestion des cas limites** :
  - Ignorer les factures avec dates manquantes
  - Retourner 0.0 si aucune facture payée valide

#### **D. Calcul DPO (Days Payable Outstanding)**
- **Méthode** (`src/data/processor.py`, lignes 89-122) :
  ```python
  1. Filtrer les factures avec status='Paid'
  2. Vérifier que payment_date ET issue_date sont valides (notna)
  3. Calculer days_to_pay = payment_date - issue_date
  4. DPO moyen = moyenne des days_to_pay
  ```

- **Résultat** :
  - DSO et DPO utilisés pour projeter les dates de paiement des factures ouvertes
  - Écart-types calculés pour mesurer la variabilité

---

## 2️⃣ Classification
**Identification des transactions récurrentes vs non-récurrentes**

### Ce qui a été fait :

#### **A. Classification par catégorie**
- **Catégories récurrentes** (prévisibles) :
  ```python
  {
      'Payroll': 'Récurrent',
      'Supplier Payment': 'Récurrent',
      'Loan Interest': 'Récurrent',
      'Bank Fee': 'Récurrent',
      'Tax Payment': 'Récurrent',
      'Transfer to Payroll': 'Récurrent'
  }
  ```

- **Implémentation** :
  - Ajout de la colonne `flow_type` dans le DataFrame `bank`
  - Classification automatique basée sur la colonne `category`
  - Toutes les autres catégories = 'Non-récurrent'

#### **B. Statistiques de classification**
- **Calculs** :
  - Nombre de transactions récurrentes vs non-récurrentes
  - Pourcentage de chaque type
  - Visualisation avec graphique en camembert (Plotly)

#### **C. Utilisation dans le forecast**
- **Paiements récurrents** :
  - Calcul de la moyenne mensuelle des paiements récurrents
  - Ajout automatique le 1er de chaque mois dans le forecast
  - Inclusion des intérêts de la dette €20M (DEBT_MONTHLY_INTEREST)

---

## 3️⃣ Saisonnalité
**Détection des patterns hebdomadaires et mensuels**

### Ce qui a été fait :

#### **A. Patterns hebdomadaires**
- **Méthode** (`src/data/processor.py`, lignes 163-192) :
  ```python
  1. Extraire le jour de la semaine (day_name) : Monday, Tuesday, etc.
  2. Grouper par (date_only, day_name, type)
  3. Calculer la moyenne des montants par jour de la semaine
  4. Séparer crédits et débits
  ```

- **Résultat** :
  - `weekly_credit_pattern` : Dictionnaire {jour: moyenne_encaissements}
  - `weekly_debit_pattern` : Dictionnaire {jour: moyenne_décaissements}

- **Utilisation dans le forecast** :
  - Ajustement quotidien basé sur le jour de la semaine
  - Exemple : Si c'est un lundi, utiliser la moyenne historique des lundis

#### **B. Patterns mensuels**
- **Calcul de l'inflation** :
  ```python
  1. Filtrer les coûts récurrents (Supplier Payment, Payroll, Loan Interest)
  2. Grouper par mois (to_period('M'))
  3. Calculer l'évolution mois par mois
  4. Taux d'inflation annuel = moyenne des taux de croissance × 12
  ```

- **Validation** :
  - Minimum 6 mois de données pour calculer l'inflation
  - Limite à 10% maximum (protection contre valeurs aberrantes)
  - Fallback à 2% (moyenne zone euro) si données insuffisantes

#### **C. Statistiques quotidiennes**
- **Calculs** :
  - `avg_daily_credit` : Moyenne des encaissements quotidiens
  - `avg_daily_debit` : Moyenne des décaissements quotidiens
  - `std_daily_credit` : Écart-type des encaissements
  - `std_daily_debit` : Écart-type des décaissements

---

## 4️⃣ Facteurs d'Impact
**Calcul de l'inflation, volatilité, retards, impayés, FX**

### Ce qui a été fait :

#### **A. Inflation**
- **Calcul** (détaillé dans étape 3) :
  - Basé sur l'évolution des coûts récurrents
  - Taux annuel converti en ajustement quotidien : `1 + (inflation_rate × jour / 365)`

#### **B. Volatilité des volumes**
- **Coefficient de variation** :
  ```python
  volume_volatility_credit = std_daily_credit / avg_daily_credit
  volume_volatility_debit = std_daily_debit / avg_daily_debit
  ```

- **Utilisation** :
  - Ajustement aléatoire basé sur la volatilité historique
  - Simulation de variations : `1 + N(0, volatility × 0.3)`

#### **C. Retards de paiement**
- **Taux de retard** :
  ```python
  overdue_rate_sales = len(sales[sales['status']=='Overdue']) / len(sales)
  overdue_rate_purchase = len(purchase[purchase['status']=='Overdue']) / len(purchase)
  ```

- **Variations DSO/DPO** :
  - Écart-type des délais de paiement
  - Mesure de la dispersion (jours)

#### **D. Taux de change (FX)**
- **Récupération** (`src/utils/currency.py`) :
  - API exchangerate-api.com pour taux réels
  - Fallback sur moyennes 2024 si API indisponible
  - Taux utilisés : USD/EUR, JPY/EUR

- **Conversion** :
  - Toutes les transactions converties en EUR (`amount_eur`)
  - Gestion multi-devises dans le forecast (EUR, USD, JPY séparés)

---

## 5️⃣ Forecast Quotidien
**Calcul jour par jour des encaissements/décaissements**

### Ce qui a été fait :

#### **A. Préparation des factures ouvertes**
- **Méthode** (`src/forecast/engine.py`, lignes 49-97) :
  ```python
  1. Filtrer factures avec status='Open' ou 'Overdue'
  2. Calculer date_paiement_attendue = due_date + DSO (ou DPO)
  3. Convertir montants en EUR
  4. Retourner DataFrame avec payment_date et amount_eur
  ```

#### **B. Boucle de forecast quotidien**
- **Pour chaque jour** (`src/forecast/engine.py`, lignes 247-332) :
  ```python
  1. Calculer date du jour
  2. Base historique selon jour de la semaine (pattern hebdomadaire)
  3. Ajouter factures échues ce jour (encaissements/décaissements)
  4. Appliquer ajustements :
     - Inflation : 1 + (inflation_rate × jour / 365)
     - Volatilité : 1 + N(0, volatility × 0.3)
  5. Paiements récurrents : ajout le 1er de chaque mois
  6. Calculer cash flow net = encaissements - décaissements
  7. Mettre à jour cumuls par devise (EUR, USD, JPY)
  8. Calculer cumul total en EUR
  ```

#### **C. Gestion multi-devises**
- **Séparation par devise** :
  - Encaissements/décaissements calculés séparément pour EUR, USD, JPY
  - Conversion en EUR pour le cumul total
  - Suivi des soldes par devise

#### **D. Ajustements appliqués**
- **Inflation** : Ajustement progressif sur la période
- **Volatilité** : Simulation aléatoire basée sur historique
- **Patterns hebdomadaires** : Ajustement selon jour de la semaine
- **Factures ouvertes** : Ajout des montants réels aux dates attendues

---

## 6️⃣ Multi-Devises
**Gestion séparée EUR, USD, JPY avec conversion**

### Ce qui a été fait :

#### **A. Conversion initiale**
- **Toutes les transactions** :
  - Colonne `amount_eur` ajoutée à toutes les transactions
  - Conversion selon devise : `amount × fx_rate`

#### **B. Forecast par devise**
- **Séparation** :
  ```python
  - Encaissements EUR, USD, JPY calculés séparément
  - Décaissements EUR, USD, JPY calculés séparément
  - Cumuls par devise maintenus séparément
  ```

#### **C. Conversion finale**
- **Cumul total en EUR** :
  ```python
  cumul_total = cumul_eur + (cumul_usd × usd_rate) + (cumul_jpy × jpy_rate)
  ```

#### **D. Gestion des comptes**
- **Comptes par devise** :
  - EUR_Operating, EUR_Payroll (EUR)
  - USD_Sales (USD)
  - JPY_Sales (JPY)
  - Soldes calculés et affichés par compte et devise

---

## 7️⃣ Détection de Risques
**Identification des jours critiques et zones de risque**

### Ce qui a été fait :

#### **A. Calcul du solde net**
- **Formule** :
  ```python
  solde_net = cumul_total - DEBT_PRINCIPAL (€20M)
  ```

#### **B. Classification des zones de risque**
- **Niveaux** :
  ```python
  - Safe : solde_net >= 0
  - Warning : -100,000 <= solde_net < 0
  - Critical : solde_net < -100,000
  ```

#### **C. Identification des jours critiques**
- **Détection** :
  - Liste des dates avec solde négatif (`negative_days`)
  - Comptage par zone de risque
  - Identification du jour le plus critique (solde minimum)

#### **D. Visualisation**
- **Graphiques** :
  - Évolution du solde cumulé avec zones colorées
  - Points marqués selon niveau de risque
  - Ligne rouge à 0 pour référence

---

## 8️⃣ Recommandations
**Actions correctives selon la situation de trésorerie**

### Ce qui a été fait :

#### **A. Analyse des risques**
- **Selon la zone** :
  - **Safe** : Recommandations d'optimisation (placements, investissements)
  - **Warning** : Actions préventives (relances clients, négociations fournisseurs)
  - **Critical** : Actions urgentes (escomptes, financements, réductions coûts)

#### **B. Recommandations spécifiques**
- **Pour améliorer le DSO** :
  - Relances clients
  - Escomptes pour paiement anticipé
  - Négociations de délais

- **Pour optimiser le DPO** :
  - Négociations avec fournisseurs
  - Utilisation maximale des délais

- **Pour gérer la dette** :
  - Couverture de taux (hedging)
  - Refinancement si opportun

#### **C. Scénarios**
- **Base, Optimiste, Pessimiste** :
  - Simulation de variations de taux d'intérêt (±100bp)
  - Simulation de variations FX (±5%)
  - Impact sur les intérêts et encaissements

---

## 📊 Résumé Technique

### Fichiers principaux implémentés :

1. **`src/data/loader.py`** : Chargement CSV
2. **`src/data/processor.py`** : Calcul DSO/DPO, statistiques, patterns
3. **`src/forecast/engine.py`** : Moteur de forecast principal
4. **`src/utils/currency.py`** : Conversion devises, API FX
5. **`src/dashboard/app.py`** : Interface utilisateur Streamlit

### Métriques calculées :

- DSO, DPO (moyennes et écarts-types)
- Moyennes quotidiennes (encaissements/décaissements)
- Volatilités (coefficients de variation)
- Patterns hebdomadaires (par jour de la semaine)
- Taux d'inflation (depuis coûts récurrents)
- Taux de retard (factures Overdue)
- Soldes par compte et devise

### Ajustements appliqués dans le forecast :

- ✅ Inflation progressive
- ✅ Volatilité aléatoire (basée sur historique)
- ✅ Patterns hebdomadaires
- ✅ Factures ouvertes (dates réelles)
- ✅ Paiements récurrents (1er du mois)
- ✅ Multi-devises (EUR, USD, JPY)

---

## 🎯 Résultat Final

Le système produit :
- **Forecast quotidien** sur 90 jours maximum
- **Soldes cumulés** par devise et total en EUR
- **Zones de risque** identifiées (Safe/Warning/Critical)
- **Jours critiques** listés
- **Recommandations** selon la situation
- **Visualisations** interactives (Plotly)
- **Scénarios** (Base/Optimiste/Pessimiste)

