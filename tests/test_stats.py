"""Statistiques sur données simulées dont la réponse est connue."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from alpha import stats


def _serie(mu, sigma, n, graine=0):
    return np.random.default_rng(graine).normal(mu, sigma, n)


def test_sharpe_connu():
    r = _serie(0.001, 0.01, 200_000)
    assert stats.sharpe(r) == pytest.approx(0.1 * np.sqrt(252), rel=0.05)
    assert stats.sharpe(r, annualiser=False) == pytest.approx(0.1, abs=0.01)


def test_bootstrap_ic_contient_la_verite_et_largeur_theorique():
    n = 1000
    r = _serie(0.0006, 0.01, n, graine=2)
    bas, haut = stats.ic_sharpe_bootstrap(r, n_tirages=2000)
    vrai = 0.06 * np.sqrt(252)
    assert bas < vrai < haut
    # écart-type théorique du Sharpe annualisé ~ sqrt(252/n)
    assert (haut - bas) / (2 * 1.96) == pytest.approx(np.sqrt(252 / n), rel=0.25)


def test_bootstrap_stationnaire_longueur_moyenne_des_blocs():
    rng = np.random.default_rng(0)
    n = 500
    idx = stats.indices_bootstrap_stationnaire(n, 20, 400, rng)
    assert idx.min() >= 0 and idx.max() < n
    continu = (idx[:, 1:] == (idx[:, :-1] + 1) % n).mean()
    assert continu == pytest.approx(1 - 1 / 20, abs=0.01)


def test_newey_west_iid_et_ar1():
    r = _serie(0.0005, 0.01, 20000, graine=3)
    nw = stats.newey_west(r)
    t_naif = r.mean() / (r.std(ddof=1) / np.sqrt(len(r)))
    assert nw["t_nw"] == pytest.approx(t_naif, rel=0.25)
    # AR(1) positif : la variance de la moyenne est plus grande, le t NW doit être plus petit
    e = _serie(0, 0.01, 20000, graine=4)
    x = np.zeros_like(e)
    for i in range(1, len(e)):
        x[i] = 0.5 * x[i - 1] + e[i]
    x += 0.0003
    t_naif = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    assert abs(stats.newey_west(x)["t_nw"]) < 0.8 * abs(t_naif)


def test_holm_exemple_a_la_main():
    aj = stats.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    # tri : 0.01*3=0.03 ; 0.03*2=0.06 ; 0.04*1=0.04 -> max cumulé 0.06
    assert aj == {"a": pytest.approx(0.03), "b": pytest.approx(0.06), "c": pytest.approx(0.06)}


def test_psr_limites():
    fort = _serie(0.002, 0.01, 2000, graine=5)   # Sharpe quotidien 0,2
    nul = _serie(0.0, 0.01, 2000, graine=6)
    assert stats.psr(fort, 0.0) > 0.999
    assert 0.05 < stats.psr(nul, 0.0) < 0.95
    # contre une référence plus haute que le Sharpe observé, la proba tombe sous 50 %
    assert stats.psr(fort, 0.3) < 0.5


def test_dsr_formule_explicite():
    r = _serie(0.0007, 0.01, 1000, graine=7)
    essais = np.array([0.02, -0.01, 0.05, 0.0, 0.03, -0.04, 0.01, 0.04])
    n = len(essais)
    g = 0.5772156649015329
    sr0 = np.sqrt(essais.var(ddof=1)) * ((1 - g) * sps.norm.ppf(1 - 1 / n) + g * sps.norm.ppf(1 - 1 / (n * np.e)))
    assert stats.sharpe_reference_dsr(essais) == pytest.approx(sr0)
    assert stats.dsr(r, essais) == pytest.approx(stats.psr(r, sr0))
    assert stats.dsr(r, essais) < stats.psr(r, 0.0)  # corriger du nombre d'essais ne peut que baisser
    assert stats.sharpe_reference_dsr(np.array([0.1])) == 0.0  # un seul essai : pas de déflation


def test_drawdown():
    r = pd.Series([0.1, -0.5, 0.2, 0.0])
    assert stats.drawdown_max(r) == pytest.approx(-0.5)
