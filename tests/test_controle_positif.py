"""Contrôle positif (EXPLORATOIRE, hors verdict) : une sleeve synthétique à edge connu traverse le même pipeline de statistiques.

Aucune donnée de marché : rendements simulés (graine fixe) et résultats versionnés dans results/."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from alpha import donnees as d
from alpha import stats
from alpha.approfondissement import signal_synthetique as ss

RACINE = Path(__file__).resolve().parents[1]


def _json(nom: str) -> dict:
    return json.loads((RACINE / "results" / nom).read_text(encoding="utf-8"))


def test_sharpe_vrai_de_la_simulation():
    """La simulation a bien le Sharpe annualisé VRAI demandé (grand échantillon : erreur-type ~ 0,02)."""
    for sr in (0.0, 1.0, 2.0):
        x = ss.simuler_rendements(sr, 400_000, np.random.default_rng(7))
        assert abs(stats.sharpe(x) - sr) < 0.12
        assert abs(x.std(ddof=1) * np.sqrt(252) - ss.VOL_ANNUELLE) < 0.002


def test_tirage_deterministe_et_graine_fixe():
    a, na = ss.tirage_illustration(500)
    b, nb = ss.tirage_illustration(500)
    assert np.array_equal(a, b) and all(np.array_equal(x, y) for x, y in zip(na, nb))
    assert ss.GRAINE == 20261014 and ss.SHARPE_VRAI == 1.0
    assert len(na) == 7                                   # 7 sleeves nulles + l'edge : N = 8 essais, comme le protocole


def test_le_pipeline_detecte_un_edge_fort_et_pas_le_bruit():
    """Edge fort (Sharpe 2) : G2 passe presque toujours ; bruit pur (Sharpe 0) : G2 passe rarement (faux positifs)."""
    p = ss.puissance(sharpes_vrais=(0.0, 2.0), n_jours=1044, n_rep=60, n_tirages=300)["par_sharpe_vrai"]
    assert p["2.0"]["taux_G2"] >= 0.85
    assert p["0.0"]["taux_G2"] <= 0.12
    assert p["2.0"]["sharpe_estime_moyen"] > 1.7 and abs(p["0.0"]["sharpe_estime_moyen"]) < 0.3


def test_illustration_utilise_les_memes_fonctions_que_les_sleeves_reelles():
    csv = pd.read_csv(RACINE / "results" / "rendements_train_val.csv", index_col=0, parse_dates=True)
    dates = csv.loc["2011-02-24":].index
    il = ss.illustration(dates)
    assert set(il["VAL"]) >= {"sharpe_net", "ic95_sharpe", "drawdown_max", "rotation_annuelle"}   # sortie de pipeline.stats_periode
    assert set(il["gates"]) >= {"G1", "G2", "G3"} and il["n_jours_val"] == 1044
    assert il["VAL"]["ic95_sharpe"][0] < il["VAL"]["sharpe_net"] < il["VAL"]["ic95_sharpe"][1]
    assert dates.max() < d.DEBUT_TEST                      # le TEST n'existe pas ici


def test_resultats_versionnes_coherents_et_hors_verdict():
    r = _json("controle_positif.json")
    assert r["verdict_officiel_inchange"]["verdict"] == _json("verdict_alpha.json")["verdict"] == "ECHEC"
    assert r["verdict_officiel_inchange"]["statut_test"].startswith("scelle")
    assert not (RACINE / "results" / "test_ouvert.json").exists()
    assert r["illustration"]["graine"] == ss.GRAINE and r["frontieres"]["val_fin"] == "2022-12-31"
    par = r["puissance"]["par_sharpe_vrai"]
    assert par["0.0"]["taux_G2"] <= 0.10                 # peu de faux positifs
    assert par["2.0"]["taux_G2"] >= 0.90                 # edge fort détecté
    assert par["0.0"]["taux_G2"] < par["1.0"]["taux_G2"] < par["2.0"]["taux_G2"]   # la détection croît avec l'edge
    # le résultat versionné se recalcule à l'identique depuis la graine fixe
    csv = pd.read_csv(RACINE / "results" / "rendements_train_val.csv", index_col=0, parse_dates=True)
    il = ss.illustration(csv.loc[_json("train_val.json")["meta"]["debut_commun_pile"]:].index)
    assert abs(il["VAL"]["sharpe_net"] - r["illustration"]["VAL"]["sharpe_net"]) < 1e-9
    assert (RACINE / "figures" / "controle_positif.png").exists()
