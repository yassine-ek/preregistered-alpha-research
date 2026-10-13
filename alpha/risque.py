"""Estimation du risque (EWMA, passé seulement) et mise à l'échelle des sleeves à 10 % de vol.

Pourquoi une covariance et pas juste des vols : plusieurs sleeves empilent des paris très
corrélés (le dollar commande la plupart des paires FX). Viser 10 % de vol « ex ante »
sans tenir compte des corrélations sous-estimerait le risque réel.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEMI_VIE = 36          # jours (prereg, section 4)
CIBLE_VOL = 0.10       # volatilité annuelle visée par sleeve
MIN_OBS = 63           # un actif n'a pas de position tant qu'il a moins de 63 observations
JOURS_PAR_AN = 252


def covariance_ewma(x: pd.DataFrame, demi_vie: float = DEMI_VIE) -> tuple[np.ndarray, np.ndarray]:
    """Covariance EWMA (second moment centré en 0, standard en gestion du risque court
    terme) par paires complètes. cov[t] n'utilise que les lignes <= t.

    Un NaN (marché fermé, actif pas encore coté) n'ajoute rien à l'estimation de ses
    paires au lieu d'être compté comme un rendement nul : sinon les actifs récents
    auraient une vol sous-estimée et un levier trop grand."""
    v = x.to_numpy(dtype=float)
    T, N = v.shape
    lam = 0.5 ** (1.0 / demi_vie)
    num = np.zeros((N, N))
    den = np.zeros((N, N))
    cov = np.zeros((T, N, N))
    nobs = np.zeros((T, N))
    compte = np.zeros(N)
    for t in range(T):
        fini = np.isfinite(v[t])
        r = np.where(fini, v[t], 0.0)
        m = fini.astype(float)
        num = lam * num + np.outer(r, r)
        den = lam * den + np.outer(m, m)
        compte += m
        with np.errstate(invalid="ignore", divide="ignore"):
            cov[t] = np.where(den > 0, num / den, 0.0)
        nobs[t] = compte
    return cov, nobs


def poids_vol_cible(
    signal: pd.DataFrame,
    x: pd.DataFrame,
    jours_actifs_par_an: float = JOURS_PAR_AN,
    cible: float = CIBLE_VOL,
    groupes: list[list[str]] | None = None,
    decalage: int = 0,
    sigma_min: float = 0.0,
    min_obs: int = MIN_OBS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Transforme un signal relatif (prévision/10, ±1…) en poids notionnels tels que la
    vol annuelle ex ante de la sleeve vaille `cible`.

    poids_i = k_t * signal_i / sigma_i (risque égal par actif), k_t unique par jour tel
    que jours_actifs_par_an * somme_g w_g' Sigma_g w_g = cible^2.
    `x` : rendements par période de détention (journaliers, ou de fenêtre pour l'intrajournalier).
    `decalage` : nombre de lignes de retard sur l'estimation du risque. 0 pour les sleeves
    quotidiennes (décision au jour J avec les données <= J, exécution décalée ensuite) ;
    1 pour l'intrajournalier (la fenêtre du jour n'est connue qu'une fois close, donc le
    risque du jour J ne s'appuie que sur les fenêtres des jours < J).
    `sigma_min` : plancher de la vol par période utilisée pour dimensionner (0 = aucun).
    `groupes` : blocs de colonnes dont la covariance croisée est mise à zéro (fenêtres
    horaires qui ne se chevauchent pas, par exemple Londres et Tokyo en S4).
    Retourne (poids, taille_unitaire) ; taille_unitaire = poids quand signal = 1."""
    cols = list(x.columns)
    signal = signal.reindex(index=x.index, columns=cols)
    cov, nobs = covariance_ewma(x)
    if decalage:
        cov = np.concatenate([np.zeros((decalage,) + cov.shape[1:]), cov[:-decalage]])
        nobs = np.concatenate([np.zeros((decalage, nobs.shape[1])), nobs[:-decalage]])
    sigma = np.sqrt(np.einsum("tii->ti", cov))
    s = signal.to_numpy(dtype=float)
    valide = np.isfinite(s) & (nobs >= min_obs) & (sigma > 0)
    # plancher de vol : évite un levier démesuré sur un actif quasi gelé (peg HKD, DKK)
    sigma_eff = np.maximum(sigma, sigma_min)
    sigma_sur = np.where(sigma_eff > 0, sigma_eff, 1.0)  # évite la division par 0 hors positions valides
    brut = np.where(valide, s / sigma_sur, 0.0)
    if groupes is None:
        groupes = [cols]
    var = np.zeros(len(brut))
    for g in groupes:
        masque = np.array([c in g for c in cols], dtype=float)
        w = brut * masque
        var += np.einsum("ti,tij,tj->t", w, cov, w)
    var_annuelle = jours_actifs_par_an * np.maximum(var, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(var_annuelle > 0, cible / np.sqrt(var_annuelle), 0.0)
    poids = brut * k[:, None]
    unite = np.where(valide, 1.0 / sigma_sur, 0.0) * k[:, None]
    return (pd.DataFrame(poids, index=x.index, columns=cols),
            pd.DataFrame(unite, index=x.index, columns=cols))


def vol_ewma(serie: pd.DataFrame | pd.Series, demi_vie: float = DEMI_VIE, min_obs: int = MIN_OBS):
    """Écart-type EWMA (second moment) ; NaN tant que moins de `min_obs` observations."""
    return (serie ** 2).ewm(halflife=demi_vie, min_periods=min_obs).mean() ** 0.5
