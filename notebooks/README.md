# `notebooks/` : les carnets exécutés

Deux carnets Jupyter avec leurs sorties (lisibles sur GitHub sans rien installer). Ils sont générés par des scripts, pas écrits à la main.

| Fichier | Ce qu'il montre |
|---|---|
| `visite_guidee.ipynb` | Visite pas à pas : deux pièges de données (étiquette des barres 1 h, horloge HistData), chacune des 7 sleeves S1 à S7 avec sa source de la littérature et ses poids, la pile (poids ∝ 1/vol TRAIN), les limites. Généré par `scripts/build_nb_visite_guidee.py`. |
| `approfondissement.ipynb` | Un chapitre par question de l'approfondissement exploratoire (Q1 à Q7) puis « ce qu'il faudrait de vrai pour un Sharpe net > 2 » : loi fondamentale, décroissance du signal, puissance, tests multiples, anatomie de l'échec, diversification, capacité. Généré par `scripts/build_nb_approfondissement.py`. |

Réexécuter : `python -m jupyter nbconvert --to notebook --execute --inplace notebooks/<nom>.ipynb` (données locales et `HISTDATA_DIR` requis, voir le README principal).
