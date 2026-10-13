"""Test de bout en bout : ajouter des données futures ne change AUCUN rendement passé.

C'est la propriété sur laquelle repose ouvrir_test.py (il recompute tout avec les données
2023+ et exige que TRAIN/VAL restent identiques). Le test n'utilise que des données <= 2022.
Il est sauté si le cache parquet des minutes n'est pas encore construit (sinon il faudrait
plus d'une minute de lecture de zips)."""
import numpy as np
import pandas as pd
import pytest

from alpha import donnees as d
from alpha import pipeline as pl
from outils_donnees import DONNEES_1H

ACTIFS_MINUTES = ["AUDUSD", "EURUSD", "GBPUSD", "NZDUSD", "SPXUSD", "USDCHF", "USDJPY"]
CACHE_PRET = DONNEES_1H and all((d.DOSSIER_CACHE / "minutes" / f"{a}_2022.parquet").exists() for a in ACTIFS_MINUTES)


@pytest.mark.skipif(not CACHE_PRET, reason="cache minutes ou données 1 h absents : définir HISTDATA_DIR puis lancer run_train_val.py une fois")
def test_rendements_passes_inchanges_quand_on_ajoute_du_futur():
    coupe = pd.Timestamp("2021-06-30")
    court = pl.calculer_sleeves(coupe)
    long = pl.calculer_sleeves(d.FIN_VAL)
    for k in court["resultats"]:
        a = court["resultats"][k].net.loc[:"2021-06-29"].to_numpy()
        b = long["resultats"][k].net.loc[:"2021-06-29"].to_numpy()
        assert np.array_equal(a, b), f"{k} : un rendement passé change quand on ajoute du futur"
    # le TEST reste hors de portée de ces chemins
    assert max(r.net.index.max() for r in long["resultats"].values()) < d.DEBUT_TEST
