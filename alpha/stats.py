"""Statistiques du prereg (section 7) : Sharpe, bootstrap stationnaire, Newey-West, Holm,
PSR, DSR (Bailey-López de Prado), drawdown, rotation.

Tout est calculé sur des rendements QUOTIDIENS ; annualisation par racine de 252.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

JOURS_PAR_AN = 252
EULER_MASCHERONI = 0.5772156649015329


def sharpe(r: np.ndarray | pd.Series, annualiser: bool = True) -> float:
    """Sharpe (rendement sans taux : sleeves long/short sur CFD, voir limites du README)."""
    r = np.asarray(r, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    s = r.mean() / r.std(ddof=1)
    return float(s * np.sqrt(JOURS_PAR_AN)) if annualiser else float(s)


def drawdown_max(r: pd.Series) -> float:
    """Pire baisse depuis un sommet de la courbe de capital composée (valeur négative)."""
    courbe = (1.0 + r.fillna(0.0)).cumprod()
    return float((courbe / courbe.cummax() - 1.0).min())


def indices_bootstrap_stationnaire(n: int, bloc_moyen: float, n_tirages: int, rng: np.random.Generator) -> np.ndarray:
    """Indices du bootstrap stationnaire de Politis-Romano : des blocs consécutifs dont la
    longueur suit une loi géométrique de moyenne `bloc_moyen`, avec rebouclage circulaire.
    Conserve l'autocorrélation à court terme, ce qu'un bootstrap iid ignorerait."""
    nouveau = rng.random((n_tirages, n)) < 1.0 / bloc_moyen
    nouveau[:, 0] = True
    debuts = rng.integers(0, n, size=(n_tirages, n))
    t = np.arange(n)[None, :]
    debut_bloc = np.maximum.accumulate(np.where(nouveau, t, 0), axis=1)
    depart = np.take_along_axis(debuts, debut_bloc, axis=1)
    return (depart + (t - debut_bloc)) % n


def ic_sharpe_bootstrap(r: pd.Series | np.ndarray, bloc_moyen: float = 20, n_tirages: int = 5000,
                        graine: int = 20261013, niveau: float = 0.95) -> tuple[float, float]:
    """IC (percentiles) du Sharpe annualisé par bootstrap stationnaire."""
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    rng = np.random.default_rng(graine)
    idx = indices_bootstrap_stationnaire(len(x), bloc_moyen, n_tirages, rng)
    ech = x[idx]
    sd = ech.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sh = ech.mean(axis=1) / sd * np.sqrt(JOURS_PAR_AN)
    sh = sh[np.isfinite(sh)]
    a = (1 - niveau) / 2
    return float(np.quantile(sh, a)), float(np.quantile(sh, 1 - a))


def newey_west(r: pd.Series | np.ndarray, retards: int | None = None) -> dict:
    """t de Newey-West (noyau de Bartlett) de la moyenne quotidienne. Les rendements de
    stratégies sont autocorrélés (positions persistantes) : le t naïf serait trop optimiste.
    Retards par défaut : partie entière de 4 (n/100)^(2/9)."""
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if retards is None:
        retards = int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))
    e = x - x.mean()
    lrv = e @ e / n
    for k in range(1, retards + 1):
        poids = 1.0 - k / (retards + 1.0)
        lrv += 2.0 * poids * (e[k:] @ e[:-k]) / n
    se = np.sqrt(max(lrv, 0.0) / n)
    t = float(x.mean() / se) if se > 0 else float("nan")
    p = float(2 * (1 - sps.norm.cdf(abs(t)))) if np.isfinite(t) else float("nan")
    return {"t_nw": t, "p_nw": p, "retards": retards}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """p-values ajustées de Holm (descente pas à pas, contrôle de l'erreur de famille)."""
    noms = list(pvals)
    p = np.array([pvals[k] for k in noms], dtype=float)
    m = len(p)
    ordre = np.argsort(p)
    ajuste = np.empty(m)
    courant = 0.0
    for rang, i in enumerate(ordre):
        courant = max(courant, (m - rang) * p[i])
        ajuste[i] = min(1.0, courant)
    return dict(zip(noms, ajuste.tolist()))


def psr(r: pd.Series | np.ndarray, sr_ref: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio (Bailey-López de Prado 2012) : probabilité que le vrai
    Sharpe dépasse `sr_ref`. `sr_ref` en unités PAR PÉRIODE (quotidien). Corrige de
    l'asymétrie et de l'aplatissement : un Sharpe obtenu avec des queues épaisses vaut moins."""
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    sr = x.mean() / x.std(ddof=1)
    g3 = sps.skew(x)
    g4 = sps.kurtosis(x, fisher=False)
    denom = np.sqrt(1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2)
    return float(sps.norm.cdf((sr - sr_ref) * np.sqrt(n - 1) / denom))


def sharpe_reference_dsr(sharpes_essais: np.ndarray) -> float:
    """SR0 : Sharpe maximal attendu de N essais SANS aucun vrai edge, d'après la variance
    observée des Sharpe des essais (même unité que les Sharpe passés, ici quotidienne)."""
    s = np.asarray(sharpes_essais, dtype=float)
    n = len(s)
    if n < 2:
        return 0.0
    v = s.var(ddof=1)
    z1 = sps.norm.ppf(1.0 - 1.0 / n)
    z2 = sps.norm.ppf(1.0 - 1.0 / (n * np.e))
    return float(np.sqrt(v) * ((1 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2))


def dsr(r: pd.Series | np.ndarray, sharpes_essais_quotidiens: np.ndarray) -> float:
    """Deflated Sharpe Ratio : PSR contre le Sharpe qu'on obtiendrait par pur hasard en
    testant N stratégies (ici N = 8 : 7 sleeves + la pile)."""
    return psr(r, sharpe_reference_dsr(sharpes_essais_quotidiens))


def resume_periode(brut: pd.Series, cout: pd.Series, rotation: pd.Series) -> dict:
    """Chiffres de base d'une période (rendements nets = brut - coûts)."""
    net = brut - cout
    n = int(net.notna().sum())
    ans = n / JOURS_PAR_AN
    return {
        "n_jours": n,
        "sharpe_net": sharpe(net),
        "sharpe_brut": sharpe(brut),
        "rendement_annuel_net": float(net.mean() * JOURS_PAR_AN),
        "vol_annuelle": float(net.std(ddof=1) * np.sqrt(JOURS_PAR_AN)),
        "drawdown_max": drawdown_max(net),
        "rotation_annuelle": float(rotation.sum() / ans) if ans > 0 else float("nan"),
        "cout_annuel": float(cout.sum() / ans) if ans > 0 else float("nan"),
    }
