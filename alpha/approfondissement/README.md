# `alpha/approfondissement/` : pourquoi rien ne marche, et que faudrait-il ?

Analyse **EXPLORATOIRE**, non pré-enregistrée, qui ne modifie pas le verdict `ECHEC`. TRAIN et VAL seulement : le TEST n'est jamais chargé. Le sous-paquet est volontairement hors de `alpha/*.py` pour que l'empreinte du code officiel ne bouge pas.
Les résultats sont dans `results/approfondissement.json`, les figures dans `figures/appro_*.png`, la lecture dans la section « Approfondissement » du README principal.

| Fichier | Rôle |
|---|---|
| `__init__.py` | Marque le sous-paquet et rappelle pourquoi il est hors de l'empreinte officielle. |
| `chargement.py` | Charge les données avec un lecteur 1 h strict (arrêt avant 2023), réutilise `pipeline.calculer_sleeves` tel quel et compare les Sharpe nets VAL à `results/train_val.json` (1e-9) ; cache `cache/appro_base.pkl` (non versionné). |
| `diagnostics.py` | Les mesures : breadth et IC (loi fondamentale de Grinold), décroissance du signal et horizon sous coût, anatomie de l'échec de chaque sleeve, diversification, capacité (impact racine carrée). |
| `theorie.py` | Formules pures, sans données : erreur-type du Sharpe (Lo), puissance, Sharpe maximal attendu sous H0 (Bailey-López de Prado), diversification, horizon optimal. |
| `figures.py` | Les 8 figures `appro_q*.png`, toutes marquées « EXPLORATOIRE ». |
