"""Détection des données locales : les tests qui les lisent sont sautés proprement si elles manquent.

Les données (barres 1 h dérivées, minutes HistData) ne sont pas versionnées. Pour lancer la suite complète :
    export HISTDATA_DIR=/chemin/vers/les/donnees     # contient processed/univers/ et histdata_raw/
Sans cela (cas de l'intégration continue), seuls les tests synthétiques tournent.
"""
import pytest

from alpha import donnees as d

DONNEES_1H = (d.DOSSIER_1H / "EURUSD_1h.csv").exists()
MINUTES_2022 = (d.DOSSIER_CACHE / "minutes" / "EURUSD_2022.parquet").exists() or (d.DOSSIER_1MIN / "EURUSD").exists()

MOTIF = "données locales absentes : définir HISTDATA_DIR (voir README, section Reproduire)"
besoin_donnees = pytest.mark.skipif(not DONNEES_1H, reason=MOTIF)
besoin_minutes = pytest.mark.skipif(not MINUTES_2022, reason=MOTIF)
