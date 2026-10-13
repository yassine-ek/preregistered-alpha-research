"""Anti-look-ahead (idée du `lookahead-analysis` de freqtrade) : si l'on modifie les
données FUTURES, les poids PASSÉS ne doivent pas bouger d'un epsilon, pour chaque sleeve."""
import numpy as np
import pandas as pd

from alpha import sleeves as sl


def _egaux(a: pd.DataFrame, b: pd.DataFrame, jusqua):
    x = a.loc[:jusqua].to_numpy()
    y = b.loc[:jusqua].to_numpy()
    assert np.array_equal(np.nan_to_num(x, nan=-9.9), np.nan_to_num(y, nan=-9.9)), "les poids passés dépendent du futur"


def _perturber_prix(prix, apres, graine=1):
    p = prix.copy()
    rng = np.random.default_rng(graine)
    futur = p.index > apres
    p.loc[futur] = p.loc[futur] * np.exp(rng.normal(0, 0.05, size=(futur.sum(), p.shape[1])))
    return p


def _activite(w):
    return int((w.abs().sum(axis=1) > 0).sum())


def test_s1(fabrique_prix):
    cols = [f"A{i}" for i in range(8)]
    prix = fabrique_prix(cols, n=1000)
    t0 = prix.index[700]
    a = sl.sleeve_s1(prix)
    b = sl.sleeve_s1(_perturber_prix(prix, t0))
    assert _activite(a.loc[:t0]) > 100  # le test n'est pas vide
    _egaux(a, b, t0)
    assert not np.array_equal(a.loc[t0:].to_numpy(), b.loc[t0:].to_numpy())  # le futur, lui, change


def _paires(fabrique_prix, n=900):
    cols = [p for p, _ in sl.DEVISES.values()]
    return fabrique_prix(cols, n=n)


def test_s2_s3(fabrique_prix):
    prix = _paires(fabrique_prix)
    t0 = prix.index[600]
    for f in (sl.sleeve_s2, sl.sleeve_s3):
        a, b = f(prix), f(_perturber_prix(prix, t0))
        assert _activite(a.loc[:t0]) > 50
        _egaux(a, b, t0)


def test_s6(fabrique_prix):
    prix = fabrique_prix(sl.INDICES_S6, n=900)
    t0 = prix.index[500]
    a, b = sl.sleeve_s6(prix, 0.0126), sl.sleeve_s6(_perturber_prix(prix, t0), 0.0126)
    assert _activite(a.loc[:t0]) > 50
    _egaux(a, b, t0)


def _fenetres(n=900, graine=3, cols=("a", "b", "c", "d", "e", "f")):
    rng = np.random.default_rng(graine)
    idx = pd.bdate_range("2012-01-02", periods=n)
    return pd.DataFrame(rng.normal(0, 0.003, size=(n, len(cols))), index=idx, columns=list(cols))


def test_s4():
    cols = list(sl.S4_LONDRES) + list(sl.S4_TOKYO)
    fen = _fenetres(cols=cols)
    t0 = fen.index[600]
    fen2 = fen.copy()
    fen2.loc[fen2.index >= t0] *= 3.0  # on modifie la fenêtre du jour t0 ET toutes les suivantes
    a, b = sl.sleeve_s4(fen), sl.sleeve_s4(fen2)
    assert _activite(a.loc[:t0]) > 100
    _egaux(a, b, t0)  # le poids du jour t0 ne voit pas la fenêtre de t0 elle-même


def test_s5():
    paires = list(sl.S5_PAIRES)
    fen = _fenetres(cols=paires)
    indices = [sl.S5_INDICE_US] + [v[1] for v in sl.S5_PAIRES.values()]
    px = 100 * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.01, size=(len(fen), len(indices))), axis=0))
    px = pd.DataFrame(px, index=fen.index, columns=indices)
    t0 = fen.index[600]
    fen2 = fen.copy()
    fen2.loc[fen2.index >= t0] *= 3.0
    px2 = px.copy()
    px2.loc[px2.index > t0] *= 1.7
    a, b = sl.sleeve_s5(fen, px), sl.sleeve_s5(fen2, px2)
    assert _activite(a.loc[:t0]) >= 15  # ~1 jour actif par mois
    _egaux(a, b, t0)


def test_s7():
    fen = _fenetres(cols=("SPXUSD",))["SPXUSD"]
    matin = pd.Series(np.random.default_rng(7).normal(0, 0.007, len(fen)), index=fen.index)
    t0 = fen.index[600]
    fen2, matin2 = fen.copy(), matin.copy()
    fen2.loc[fen2.index >= t0] *= 3.0
    matin2.loc[matin2.index > t0] *= -1.0  # le signal du matin de t0 est connu à t0, pas celui d'après
    a, b = sl.sleeve_s7(fen, matin), sl.sleeve_s7(fen2, matin2)
    assert _activite(a.loc[:t0]) > 100
    _egaux(a, b, t0)
