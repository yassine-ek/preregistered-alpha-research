# `scripts/` : lancer les calculs et fabriquer les sorties

Les scripts « calcul » lisent les données de marché (`HISTDATA_DIR`) ; les scripts « vitrine » ne lisent que `results/` et tournent sans données. Aucun script ne charge le TEST, sauf `ouvrir_test.py` qui ne doit **pas** être lancé.

| Fichier | Ce qu'il fait / produit |
|---|---|
| `run_train_val.py` | Calcule TOUT sur TRAIN et VAL (TEST scellé) : `results/train_val.json`, `results/rendements_train_val.csv`, figures `pnl_cumule`, `correlations`, `sharpe_val_ic`, `cout_annuel`. |
| `verdict.py` | Assemble `results/verdict_alpha.json` (ECHEC / SUCCES / TEST non ouvert) à partir de `train_val.json`. |
| `ouvrir_test.py` | **À ne pas lancer.** Ouvrirait le TEST une seule fois ; refuse si G1 ou G2 échoue (c'est le cas), si le prereg a changé ou si le TEST a déjà été ouvert. Jamais exécuté. |
| `sensibilite_couts.py` | EXPLORATOIRE : Sharpe VAL selon le multiple des coûts et coût de rentabilité → `results/sensibilite_couts_exploratoire.json`, `figures/sensibilite_couts.png`. |
| `run_approfondissement.py` | EXPLORATOIRE : sept questions (Q1 à Q7) → `results/approfondissement.json`, `figures/appro_*.png`. |
| `auditer_reproduction_trades_frais.py` | Recalcule la chaîne, vérifie la reproduction à 1e-9 de `train_val.json`, compte les trades, résume les frais → `results/reproduction_et_trades.json`. |
| `exporter_dashboard.py` | Écrit `docs/data.json`, `docs/data.js`, copie la page et crée `docs/.nojekyll` (lit `results/`, sans données). |
| `generer_figures_vitrine.py` | Écrit `figures/hero_equity.png`, `toutes_variantes.png`, `overfit_scatter.png` (lit `results/`, sans données). |
| `generer_readme_tete.py` | Réécrit dans `README.md` les blocs de chiffres (frais, métriques TRAIN \| VAL, variantes) depuis `results/` ; un test vérifie qu'ils sont à jour. |
| `build_nb_alpha_04.py` | Génère `notebooks/visite_guidee.ipynb`. |
| `build_nb_appro_04.py` | Génère `notebooks/approfondissement.ipynb`. |
