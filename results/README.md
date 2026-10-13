# `results/` : les sorties figées

Tous les chiffres du README et de `docs/*.md` sont lus ici (les tableaux de chiffres sont générés, aucun n'est tapé à la main). Les fichiers sont produits par les scripts, ne sont pas à éditer, et ne contiennent aucune donnée du TEST.

| Fichier | Contenu | Produit par |
|---|---|---|
| `train_val.json` | Statistiques TRAIN et VAL de chaque sleeve et de la pile (Sharpe net/brut, IC bootstrap, Newey-West, Holm, PSR, DSR, drawdown, rotation, coût), poids de la pile, corrélations, gates, empreinte de la v1 du prereg et du code. | `scripts/run_train_val.py` |
| `rendements_train_val.csv` | Rendements quotidiens bruts et coûts de chaque série (net = brut − coût), 2010-01-01 à 2022-12-30 ; source du tableau de bord. | `scripts/run_train_val.py` |
| `verdict_alpha.json` | Verdict (`ECHEC`), gates, statut du TEST (scellé). | `scripts/verdict.py` |
| `reproduction_et_trades.json` | Reproduction à 1e-9 de `train_val.json` après le passage aux chemins relatifs, nombre de trades (ordres exécutés) par sleeve, frais par classe d'actifs. | `scripts/auditer_reproduction_trades_frais.py` |
| `empreinte_code.json` | Empreintes SHA-256 du code officiel avant et après la mise en conformité GitHub (13/10) et après les corrections du 14/10, fichiers modifiés. | écrit à la main à chaque changement du code officiel (voir `notes_implementation.md`) |
| `sensibilite_couts_exploratoire.json` | EXPLORATOIRE : Sharpe VAL selon le multiple des coûts, coût de rentabilité. | `scripts/sensibilite_couts.py` |
| `approfondissement.json` | EXPLORATOIRE : chiffres des questions Q1 à Q7. | `scripts/run_approfondissement.py` |
| `controle_positif.json` | EXPLORATOIRE, hors verdict : sleeve synthétique à edge connu passée dans les mêmes statistiques (illustration à graine fixe, taux de détection par Sharpe vrai). | `scripts/run_controle_positif.py` |
| `notes_implementation.md` | Interprétations prises là où le prereg était ambigu, contre-vérification du 13/10 (horloge HistData), mise en conformité GitHub (empreinte du code), corrections du 14/10. | à la main |

`test_ouvert.json` n'existe pas : le TEST n'a jamais été ouvert.
