"""S2 long 3 / short 3 et somme des poids nulle ; vol cible ; signal S5 ; tampon S1."""
import numpy as np
import pandas as pd
import pytest

from alpha import risque
from alpha import sleeves as sl


def _paires(fabrique_prix, n=900):
    return fabrique_prix([p for p, _ in sl.DEVISES.values()], n=n, graine=11)


def test_s2_trois_longs_trois_courts_somme_nulle(fabrique_prix):
    prix = _paires(fabrique_prix)
    w = sl.sleeve_s2(prix)
    actif = w[(w != 0).any(axis=1)]
    assert len(actif) > 400
    assert ((actif > 0).sum(axis=1) == 3).all() and ((actif < 0).sum(axis=1) == 3).all()
    assert np.allclose(actif.sum(axis=1), 0.0, atol=1e-12)
    # les longs sont bien les 3 plus forts rendements à 63 j au dernier vendredi de décision
    val = sl.valeurs_devises(prix).ffill()
    vendredi = actif.index[actif.index.dayofweek == 4][-1]
    score = (val / val.shift(63) - 1).loc[vendredi]
    assert set(w.loc[vendredi][w.loc[vendredi] > 0].index) == set(score.nlargest(3).index)
    assert set(w.loc[vendredi][w.loc[vendredi] < 0].index) == set(score.nsmallest(3).index)
    # poids constants entre deux vendredis
    semaine = w.loc[vendredi:vendredi + pd.Timedelta(days=3)]
    assert semaine.diff().abs().iloc[1:].sum().sum() == 0


def test_s3_achete_les_perdants(fabrique_prix):
    prix = _paires(fabrique_prix)
    w = sl.sleeve_s3(prix)
    actif = w[(w != 0).any(axis=1)]
    assert ((actif > 0).sum(axis=1) == 3).all() and np.allclose(actif.sum(axis=1), 0.0, atol=1e-12)
    val = sl.valeurs_devises(prix).ffill()
    vendredi = actif.index[actif.index.dayofweek == 4][-1]
    score = (val / val.shift(5) - 1).loc[vendredi]
    assert set(w.loc[vendredi][w.loc[vendredi] > 0].index) == set(score.nsmallest(3).index)


def test_vol_cible_ex_ante():
    rng = np.random.default_rng(0)
    x = pd.DataFrame(rng.normal(0, 0.01, size=(400, 5)), index=pd.bdate_range("2015-01-01", periods=400),
                     columns=list("abcde"))
    sig = pd.DataFrame(1.0, index=x.index, columns=x.columns)
    w, _ = risque.poids_vol_cible(sig, x)
    cov, _ = risque.covariance_ewma(x)
    t = 300
    var_annuelle = 252 * w.iloc[t].to_numpy() @ cov[t] @ w.iloc[t].to_numpy()
    assert np.sqrt(var_annuelle) == pytest.approx(0.10, rel=1e-9)


def test_signal_s5_sens():
    jours = pd.bdate_range("2020-01-01", "2020-03-31")
    cols = [sl.S5_INDICE_US] + [v[1] for v in sl.S5_PAIRES.values()]
    px = pd.DataFrame(100.0, index=jours, columns=cols)
    px.loc["2020-01-31", sl.S5_INDICE_US] = 110.0   # l'indice US surperforme tout le monde en janvier
    px.loc["2020-02-03":"2020-02-27", sl.S5_INDICE_US] = 100.0
    px.loc["2020-02-28", sl.S5_INDICE_US] = 90.0    # et sous-performe en février
    s = sl.signal_s5(px)
    assert s.loc["2020-01-31", "EURUSD"] == 1 and s.loc["2020-01-31", "USDJPY"] == -1  # vendre l'USD
    assert s.loc["2020-02-28", "EURUSD"] == -1 and s.loc["2020-02-28", "USDJPY"] == 1  # acheter l'USD
    assert s.dropna(how="all").index.tolist() == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28"),
                                                  pd.Timestamp("2020-03-31")]


def test_tampon_s1_reduit_la_rotation(fabrique_prix):
    prix = fabrique_prix([f"A{i}" for i in range(6)], n=800, graine=4)
    _, rend = sl.rendements_et_signal(prix)
    signal = sl.previsions_ewmac(prix) / 10
    cible, unite = risque.poids_vol_cible(signal, rend, sigma_min=sl.SIGMA_MIN_QUOTIDIEN)
    avec = sl.appliquer_tampon(cible, unite, 0.10)
    assert avec.diff().abs().sum().sum() < cible.diff().abs().sum().sum()
    # on ne s'éloigne jamais de plus d'un tampon de la cible
    assert ((avec - cible).abs() <= 0.10 * unite.abs() + 1e-12).all().all()
