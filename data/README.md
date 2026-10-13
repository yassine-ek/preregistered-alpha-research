# `data/` : coûts réels et emplacement des données locales

| Fichier | Rôle |
|---|---|
| `frais_editable.csv` | Coût réel par jambe et par actif, en bps (colonnes `actif, classe, frais_bps_par_jambe, frais_editable_override, source, date_reference, note`). Règle du protocole : override s'il est renseigné, sinon `frais_bps_par_jambe` ; indices figés à 12 bps. Tout résultat calculé avec d'autres coûts est invalide. Lu par `alpha/couts.py`. Spreads relevés sur les pages publiques des courtiers cités (colonne `source`), à titre indicatif ; l'auteur n'est affilié à aucun d'eux. Les colonnes `source` et `note` sont conservées telles quelles : ce sont des coûts de détail, pas des coûts d'exécution mesurés. |
| `histdata/` (non versionné) | Emplacement par défaut des données de marché si `HISTDATA_DIR` n'est pas défini : `histdata/processed/univers/<ACTIF>_1h.csv` et `histdata/histdata_raw/<ACTIF>/<ACTIF>_<année>.zip`. Ignoré par git, jamais publié. |
