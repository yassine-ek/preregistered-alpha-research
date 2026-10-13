# `alpha/` : le moteur de recherche

Le paquet Python du projet : données, coûts réels, risque, les 7 sleeves, le moteur d'exécution, les statistiques, les gates du protocole et la chaîne complète. Ces fichiers (`alpha/*.py`) forment le **code officiel** : leur empreinte SHA-256 est enregistrée dans `results/empreinte_code.json`, toute modification doit être expliquée dans `results/notes_implementation.md`.

| Fichier | Rôle |
|---|---|
| `__init__.py` | Marque le dossier comme paquet. |
| `donnees.py` | Chargement des barres 1 h et des minutes HistData (racine `HISTDATA_DIR`), instantané de 11h00, conversion d'horloge (heure d'été), fenêtres intrajournalières. **Le TEST (≥ 2023) est scellé** : toute demande au-delà de 2022 lève `PermissionError`. |
| `couts.py` | Coût réel par jambe et par actif (bps), lu dans `data/frais_editable.csv` (override sinon frais ; indices figés à 12 bps). |
| `risque.py` | Covariance EWMA (passé seulement) et mise à l'échelle des sleeves vers 10 % de volatilité annuelle ex ante. |
| `sleeves.py` | Les 7 sleeves (S1 trend EWMAC, S2 momentum devises, S3 retournement devises, S4 saisonnalité FX, S5 fixing de fin de mois, S6 actions gérées par la vol, S7 momentum SPX) : poids datés, paramètres figés, aucune grille. |
| `moteur.py` | Poids → rendements nets quotidiens : exécution décalée (un jour plein ou une minute), coûts sur chaque jambe, rotation. |
| `stats.py` | Sharpe, drawdown, bootstrap stationnaire, Newey-West, Holm, PSR, DSR, résumé de période. |
| `gates.py` | Gates G1-G4 et verdict (§8 du pré-enregistrement) ; condition d'ouverture du TEST. Aucun seuil n'est ajustable. |
| `pipeline.py` | Chaîne complète données → sleeves → pile → statistiques ; `sha256_code()` donne l'empreinte du code officiel. |
| `graphiques.py` | Figures de `scripts/run_train_val.py` : PnL cumulé, corrélations, Sharpe VAL avec IC, coûts annuels. |
| `approfondissement/` | Analyse exploratoire a posteriori, hors empreinte officielle (voir son README). |
