"""Approfondissement (EXPLORATOIRE) : l'IC est calculé SANS look-ahead.

Deux garanties testées : (1) les prévisions des sleeves quotidiennes ne dépendent pas du futur (modifier les prix
après t0 ne change aucune prévision <= t0) ; (2) seul le rendement CIBLE regarde le futur, et il commence
après le jour d'exécution (J+1) : le rendement de J -> J+1 n'entre jamais dans l'IC.
"""
import numpy as np
import pandas as pd

from alpha import risque, sleeves
from alpha.approfondissement import diagnostics as dg


def _base_synthetique(fabrique_prix, n=900):
    """Mini-base au format de chargement.charger_base : 9 paires FX + 7 indices de S6, prix aléatoires."""
    cols = [p for p, _ in sleeves.DEVISES.values()] + sleeves.INDICES_S6
    prix = fabrique_prix(cols, n=n)
    return prix


def _specs(prix):
    """Construit les specs sur des prix donnés (poids calculés par les fonctions réelles des sleeves)."""
    base = {"prix": prix, "couts": pd.Series(1.0, index=prix.columns),
            "poids": {"S1": sleeves.sleeve_s1(prix), "S2": sleeves.sleeve_s2(prix), "S3": sleeves.sleeve_s3(prix),
                      "S6": sleeves.sleeve_s6(prix, 0.0126)}}
    return dg.specs_quotidiennes(base)


def _perturber(prix, apres, graine=1):
    p = prix.copy()
    futur = p.index > apres
    rng = np.random.default_rng(graine)
    p.loc[futur] = p.loc[futur] * np.exp(rng.normal(0, 0.05, size=(futur.sum(), p.shape[1])))
    return p


def _egaux(a: pd.DataFrame, b: pd.DataFrame, jusqua):
    x, y = a.loc[:jusqua].to_numpy(float), b.loc[:jusqua].to_numpy(float)
    assert np.array_equal(np.nan_to_num(x, nan=-9.9), np.nan_to_num(y, nan=-9.9))


def test_previsions_ne_dependent_pas_du_futur(fabrique_prix):
    prix = _base_synthetique(fabrique_prix)
    t0 = prix.index[600]
    a, b = _specs(prix), _specs(_perturber(prix, t0))
    for nom in ("S1", "S2", "S3", "S6"):
        assert a[nom].F.loc[:t0].notna().to_numpy().sum() > 20, nom  # le test n'est pas vide
        _egaux(a[nom].F, b[nom].F, t0)
        _egaux(a[nom].sigma, b[nom].sigma, t0)  # la vol utilisée pour normaliser est elle aussi purement passée


def test_ic_des_dates_anciennes_inchange_quand_on_change_le_futur(fabrique_prix):
    """La cible R_h(J) ne dépend que des prix <= J+1+h : modifier le futur APRÈS cette échéance ne la change pas, le modifier
    AVANT la change (la cible regarde bien le futur, et lui seul). Pour l'IC de coupe (rangs par date, S2), la série d'IC
    des dates anciennes est donc identique au bit près. L'IC « poolé » (S1) normalise par des rangs GLOBAUX : c'est un
    estimateur d'évaluation sur l'échantillon entier, pas une prévision ; ses entrées (prévision, vol, cible) restent
    causales, ce que l'on vérifie ici."""
    prix = _base_synthetique(fabrique_prix)
    h, t0 = 5, prix.index[600]
    a, b = _specs(prix), _specs(_perturber(prix, t0))
    limite = prix.index[600 - (1 + h) - 1]  # dernière date de décision dont la fenêtre finit avant t0
    for nom in ("S1", "S2"):
        ra, rb = dg.rendement_futur(a[nom].P, h), dg.rendement_futur(b[nom].P, h)
        _egaux(ra, rb, limite)
        assert not np.array_equal(np.nan_to_num(ra.loc[prix.index[601]:].to_numpy()), np.nan_to_num(rb.loc[prix.index[601]:].to_numpy()))
    ia, ib = dg.ic_serie(a["S2"], h), dg.ic_serie(b["S2"], h)
    commun = ia.loc[:limite].index.intersection(ib.loc[:limite].index)
    assert len(commun) > 30
    assert np.array_equal(ia.loc[commun].to_numpy(), ib.loc[commun].to_numpy())
    apres = ia.loc[prix.index[601]:].index.intersection(ib.index)
    assert not np.array_equal(ia.loc[apres].to_numpy(), ib.loc[apres].to_numpy())


def test_rendement_futur_exclut_le_jour_d_execution():
    idx = pd.bdate_range("2020-01-01", periods=10)
    P = pd.DataFrame({"A": [100, 101, 103, 102, 105, 106, 104, 107, 108, 110.0]}, index=idx)
    r = dg.rendement_futur(P, h=2)
    # décision à l'indice 0 : exécution à 1 (101), sortie à 3 (102) -> 102/101 - 1
    assert abs(r["A"].iloc[0] - (102 / 101 - 1)) < 1e-12
    # les 3 dernières lignes n'ont pas de rendement futur complet
    assert r["A"].iloc[-3:].isna().all()
    m = dg.rendement_du_jour(P, h=2)
    assert abs(m["A"].iloc[0] - (102 / 103 - 1)) < 1e-12  # le seul jour 2 : de 103 (indice 2) à 102 (indice 3)


def test_ic_vaut_un_pour_la_cible_et_zero_pour_la_veille():
    """Prévision = la cible elle-même -> IC 1 ; prévision = le rendement du jour d'exécution (J -> J+1), exclu -> IC ~ 0."""
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2015-01-01", periods=1500)
    cols = [f"A{i}" for i in range(12)]
    P = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), len(cols))), axis=0)), index=idx, columns=cols)
    cible = P.shift(-2) / P.shift(-1) - 1.0                     # rendement de J+1 à J+2 : la cible à h=1
    exclu = P.shift(-1) / P - 1.0                               # J -> J+1 : avant l'exécution
    sig = pd.DataFrame(0.01, index=idx, columns=cols)           # vol constante : la normalisation ne change pas les rangs
    base = dg.SpecQuotidienne("T", cible, P, sig, cible, 1, "coupe", pd.Series(1.0, index=cols))
    assert abs(dg.ic_serie(base, 1).mean() - 1.0) < 1e-9
    base.F = exclu
    assert abs(dg.ic_serie(base, 1).mean()) < 0.03


def test_ic_retrouve_un_signal_plante():
    """Y = 0,2 F + bruit : la corrélation de rang transversale moyenne vaut ~0,2 (coupe) et ~0,2 (poolée)."""
    rng = np.random.default_rng(10)
    idx = pd.bdate_range("2015-01-01", periods=1000)
    F = pd.DataFrame(rng.standard_normal((1000, 40)), index=idx)
    Y = 0.2 * F + np.sqrt(1 - 0.04) * pd.DataFrame(rng.standard_normal((1000, 40)), index=idx)
    assert abs(dg.ic_coupe_par_date(F, Y).mean() - 0.19) < 0.02
    assert abs(dg.ic_poolee_par_date(F, Y).mean() - 0.19) < 0.02
    ic0 = dg.ic_coupe_par_date(F, Y.sample(frac=1.0, random_state=1).set_axis(idx))  # futur permuté dans le temps
    assert abs(ic0.mean()) < 0.02
    r = dg.resume_ic(dg.ic_coupe_par_date(F, Y), idx[0], idx[-1], 1)
    assert r["t_nw"] > 10 and r["se"] > 0


def test_vol_ewma_est_causale(fabrique_prix):
    prix = _base_synthetique(fabrique_prix, 400)
    r = prix.pct_change()
    t0 = prix.index[250]
    r2 = r.copy()
    r2.loc[r2.index > t0] *= 3.0
    assert np.array_equal(np.nan_to_num(risque.vol_ewma(r).loc[:t0].to_numpy()), np.nan_to_num(risque.vol_ewma(r2).loc[:t0].to_numpy()))
