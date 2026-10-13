# `tests/` : la suite pytest

Lancer : `python -m pytest -q`. Les tests qui lisent les données de marché (barres 1 h, minutes) sont **sautés** si `HISTDATA_DIR` n'est pas défini ; tous les autres sont synthétiques et tournent n'importe où (c'est ce que fait l'intégration continue).
Principe : chaque brique est confrontée à une réponse connue (simulation, formule fermée, signal planté), et les garanties de causalité et de non-ouverture du TEST sont des tests.

| Fichier | Ce qu'il fait |
|---|---|
| `conftest.py` | Met le dépôt dans `sys.path` ; fabrique des prix synthétiques (marches aléatoires) pour les tests. |
| `outils_donnees.py` | Détecte les données locales et fournit les marqueurs `besoin_donnees` / `besoin_minutes` (skip propre). |
| `test_anti_look_ahead.py` | Modifier le futur ne change aucun poids passé, pour chaque sleeve. |
| `test_causalite_bout_en_bout.py` | Idem de bout en bout sur données réelles (données requises). |
| `test_couts_moteur.py` | Coûts nuls = brut, chronologie de l'exécution décalée, coûts réels, garde-fou d'ouverture du TEST, verdict. |
| `test_sleeves_structure.py` | Long 3 / short 3, achat des perdants, vol cible, signal S5, tampon S1. |
| `test_stats.py` | Sharpe, bootstrap, Newey-West, Holm, PSR, DSR, drawdown sur données de réponse connue. |
| `test_horloge_donnees.py` | Conversion heure locale → horloge des fichiers HistData (heure d'été), ouverture hebdomadaire EURUSD (cache requis). |
| `test_troncature_test.py` | Le TEST est inaccessible depuis les chemins train/val (données requises). |
| `test_approfondissement_test_scelle.py` | Lecteur strict, base sans TEST, verdict inchangé, prereg intact, empreinte du code officiel. |
| `test_approfondissement_ic.py` | L'IC est calculé sans look-ahead. |
| `test_approfondissement_diagnostics.py` | Briques de diagnostic (breadth, demi-vies, causes) sur signaux plantés. |
| `test_approfondissement_theorie.py` | Formules de l'approfondissement contre des simulations. |
| `test_dashboard_et_readme.py` | `docs/data.json` cohérent avec `results/` et sans TEST, blocs de chiffres du README à jour, aucun chemin absolu de machine. |
