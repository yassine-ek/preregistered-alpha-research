# `scripts/` : lancer les calculs et fabriquer les sorties

Les scripts « calcul » lisent les données de marché (`HISTDATA_DIR`) ; les scripts « vitrine » ne lisent que `results/` et tournent sans données. Aucun script ne charge le TEST, sauf `ouvrir_test.py` qui ne doit **pas** être lancé.

| Fichier | Ce qu'il fait / produit |
|---|---|
| `run_train_val.py` | Calcule TOUT sur TRAIN et VAL (TEST scellé) : `results/train_val.json`, `results/rendements_train_val.csv`, figures `pnl_cumule`, `correlations`, `sharpe_val_ic`, `cout_annuel`. |
| `verdict.py` | Assemble `results/verdict_alpha.json` (ECHEC / SUCCES / TEST non ouvert) à partir de `train_val.json`. |
| `ouvrir_test.py` | **À ne pas lancer.** Ouvrirait le TEST une seule fois ; refuse si G1 ou G2 échoue (c'est le cas), si l'empreinte de `PREREGISTRATION_v1.md` a changé (ou si le fichier courant n'est plus la v1 + avenants) ou si le TEST a déjà été ouvert. Jamais exécuté. |
| `sensibilite_couts.py` | EXPLORATOIRE : Sharpe VAL selon le multiple des coûts et coût de rentabilité → `results/sensibilite_couts_exploratoire.json`, `figures/sensibilite_couts.png`. |
| `run_approfondissement.py` | EXPLORATOIRE : sept questions (Q1 à Q7) → `results/approfondissement.json`, `figures/appro_*.png`. |
| `auditer_reproduction_trades_frais.py` | Recalcule la chaîne, vérifie la reproduction à 1e-9 de `train_val.json`, compte les trades, résume les frais → `results/reproduction_et_trades.json`. |
| `exporter_dashboard.py` | Écrit `docs/data.json`, `docs/data.js`, copie la page et crée `docs/.nojekyll` (lit `results/`, sans données). |
| `generer_figures_vitrine.py` | Écrit `figures/hero_equity.png`, `toutes_variantes.png`, `overfit_scatter.png` (lit `results/`, sans données). |
| `generer_readme_tete.py` | Réécrit les blocs de chiffres `<!-- AUTO:... -->` de `README.md`, `docs/resultats_detailles.md` et `docs/approfondissement.md` (résultats clés, frais, métriques TRAIN \| VAL, variantes, contrôle positif, sensibilité aux coûts) depuis `results/` ; un test vérifie qu'ils sont à jour. |
| `verifier_prereg.py` | Vérifie l'empreinte SHA-256 de `PREREGISTRATION_v1.md` (fins de ligne normalisées) et que `PREREGISTRATION.md` = la v1 dont `(aucun)` est remplacé par les avenants. Sans données ; code de sortie 0 si conforme. Importé par `ouvrir_test.py`, `run_train_val.py`, `run_approfondissement.py`. |
| `verifier_donnees.py` | Message guidé (où télécharger, arborescence, `HISTDATA_DIR`) quand les données de marché manquent ; appelé par les scripts de rejeu. |
| `run_controle_positif.py` | EXPLORATOIRE, hors verdict : contrôle positif (sleeve synthétique de Sharpe vrai connu dans les mêmes statistiques) → `results/controle_positif.json`, `figures/controle_positif.png` (lit `results/`, sans données). |
| `build_nb_visite_guidee.py` | Génère `notebooks/visite_guidee.ipynb`. |
| `build_nb_approfondissement.py` | Génère `notebooks/approfondissement.ipynb`. |
