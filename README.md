# FMCG Distributor Churn Prediction

## Business Problem
In FMCG distribution networks, losing a distributor is significantly more
expensive than retaining one. This project builds a full end-to-end ML pipeline
to predict which distributors are likely to churn (stop ordering) within the
next 90 days, and explains WHY using SHAP values — giving sales teams
actionable, distributor-level insights.

**1 in 2 distributors in this dataset had churned at snapshot date.**

---

## Dataset
**UCI Online Retail II** — 1,067,371 transactions, 2009–2011
- Each `CustomerID` treated as a distributor
- 5,878 unique distributors after cleaning
- 779,425 clean order rows loaded into MySQL

---

## Tech Stack
| Layer | Tools |
|---|---|
| Database | MySQL + SQLAlchemy |
| ETL | Python, pandas, openpyxl |
| Feature Engineering | pandas, scikit-learn, IQR capping |
| EDA | plotly, seaborn, matplotlib |
| ML | scikit-learn, XGBoost, LightGBM |
| Explainability | SHAP |

---

## Project Structure
```
fmcg_churn_project/
├── sql/
│   ├── schema.sql               # Table definitions (distributors + orders)
│   ├── 02_rfm_features.sql      # RFM features + 90-day churn labels
│   └── 03_feature_store.sql     # ML-ready VIEW with RFM scores + segments
├── src/
│   ├── db_loader.py             # ETL: Excel → MySQL (gitignored)
│   ├── run_sql.py               # SQL executor utility (gitignored)
│   └── feature_engineering.py  # Scaling, encoding, train/test split
├── notebooks/
│   ├── 01_eda.ipynb             # Exploratory analysis + business insights
│   └── 02_models.ipynb          # All ML models (KNN → Stacking → SHAP)
├── outputs/
│   ├── rfm_distributions.png
│   ├── behavioral_signals.png
│   ├── correlation_heatmap.png
│   ├── shap_global_importance.png
│   ├── shap_beeswarm.png
│   ├── shap_waterfall.png
│   ├── all_models_roc.png
│   └── model_comparison.csv
└── README.md
```

---

## Data Pipeline
```
Excel (1,067,371 rows)
   ↓ db_loader.py — clean + load
distributors (5,878 rows) + orders (779,425 rows) → MySQL
   ↓ 02_rfm_features.sql
order_summary + distributor_features (RFM + churn label)
   ↓ 03_feature_store.sql
feature_store VIEW (RFM scores + segments)
   ↓ feature_engineering.py
Train/test splits + scaled arrays → outputs/*.pkl
   ↓ 02_models.ipynb
13 models trained, evaluated, compared
```

---

## Feature Engineering
11 features used for ML after removing leaking features:

| Feature | Type | Description |
|---|---|---|
| frequency | RFM | Total orders placed |
| monetary | RFM | Total spend £ |
| avg_order_value | RFM | Average order size |
| order_gap_std | Behavioral | Std dev of days between orders |
| avg_order_gap_days | Behavioral | Average days between orders |
| unique_skus | Behavioral | Total unique products ordered |
| product_categories | Behavioral | Unique product categories |
| spend_trend_pct | Trend | Last 90d vs prior 90d spend change |
| customer_lifespan_days | Trend | Days between first and last order |
| f_score | RFM score | Frequency quintile (1-5) |
| m_score | RFM score | Monetary quintile (1-5) |

**Note:** `recency_days` and derived features (`r_score`, `rfm_total_score`,
`rfm_segment_encoded`) were intentionally excluded — recency directly encodes
the 90-day churn label and would cause data leakage.

---

## Key EDA Insights

| Metric | Active | Churned |
|---|---|---|
| Avg recency | 32 days | 366 days |
| Avg frequency | 9.6 orders | 3.0 orders |
| Avg monetary | £4,840 | £1,134 |
| Avg unique SKUs | 119 | 45 |
| Avg spend trend | +0.64 | -0.20 |

1. **Spend trend is a leading indicator** — churned distributors show
   negative spend trend before fully dropping off, giving a 90-day
   early warning window for sales intervention
2. **SKU diversity predicts loyalty** — active distributors carry 119
   unique SKUs vs 45 for churned. Single-product distributors are
   higher flight risks
3. **Churned dropout is clean, not gradual** — low order gap std for
   churned distributors suggests a single trigger event rather than
   gradual disengagement

---

## Model Results

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| **Stochastic GB** | 0.7202 | 0.6765 | 0.8063 | 0.7357 | **0.8040** |
| Random Forest (GridSearch) | 0.7296 | 0.6796 | 0.8327 | 0.7484 | 0.8031 |
| XGBoost | 0.7262 | 0.6772 | 0.8275 | 0.7448 | 0.8023 |
| Bagging (50 DTs) | 0.7279 | 0.6808 | 0.8222 | 0.7448 | 0.8009 |
| LightGBM | 0.7262 | 0.6804 | 0.8169 | 0.7424 | 0.8008 |
| RF (RandomizedSearch) | 0.7228 | 0.6709 | 0.8363 | 0.7445 | 0.7978 |
| Gradient Boosting | 0.7100 | 0.6667 | 0.7993 | 0.7270 | 0.7978 |
| Stacking (RF+XGB+LGBM→LR) | 0.7151 | 0.6701 | 0.8081 | 0.7326 | 0.7917 |
| Decision Tree | 0.7066 | 0.6618 | 0.8028 | 0.7255 | 0.7884 |
| SVM (RBF) | 0.7134 | 0.6667 | 0.8134 | 0.7328 | 0.7827 |
| KNN | 0.7219 | 0.6817 | 0.7958 | 0.7344 | 0.7773 |
| AdaBoost | 0.6803 | 0.6182 | 0.8838 | 0.7275 | 0.7744 |
| Naive Bayes | 0.6879 | 0.6463 | 0.7817 | 0.7076 | 0.7440 |
| Cascading (NB→LightGBM) | 0.7049 | 0.6604 | 0.8011 | 0.7239 | — |

**Best model: Stochastic Gradient Boosting (ROC-AUC 0.804)**

---

## Production Recommendation

| Use Case | Recommended Model | Reason |
|---|---|---|
| Daily distributor dashboard | Naive Bayes or Decision Tree | Fast + explainable |
| Weekly churn report | Random Forest or LightGBM | Balanced accuracy |
| Monthly strategy review | Stochastic GB | Highest ROC-AUC |
| Field sales tool | Decision Tree rules | No ML knowledge needed |
| Individual distributor alerts | SHAP waterfall | Actionable reasons |

---

## Notable ML Decisions
- **Data leakage caught and fixed** — recency_days encodes the churn
  label directly and was removed from features
- **IQR capping** instead of removal — extreme spenders are real
  distributors, just outliers in scale
- **Stratified split** — preserves 50/50 churn ratio in train and test
- **Early stopping** on XGBoost and LightGBM — optimal tree count
  chosen automatically
- **Stacking underperformed** individual ensembles — base learners
  too similar (all tree-based), meta-learner had limited signal to exploit

---

## How to Run
```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/fmcg-churn-prediction.git
pip install pandas mysql-connector-python sqlalchemy openpyxl tqdm
pip install jupyter plotly seaborn matplotlib scikit-learn
pip install xgboost lightgbm shap

# 2. Add data
# Download UCI Online Retail II → data/online_retail_II.xlsx

# 3. Run pipeline
python src/db_loader.py
python src/run_sql.py sql/02_rfm_features.sql
python src/run_sql.py sql/03_feature_store.sql
python src/feature_engineering.py

# 4. Run notebooks
jupyter notebook notebooks/01_eda.ipynb
jupyter notebook notebooks/02_models.ipynb
```

---

## Status
- [x] MySQL schema + ETL pipeline
- [x] RFM feature engineering in SQL
- [x] Feature store VIEW with segments
- [x] EDA with business insights
- [x] Feature engineering + leakage fix
- [x] 13 ML models trained and compared
- [x] SHAP explainability
- [x] Production recommendation
