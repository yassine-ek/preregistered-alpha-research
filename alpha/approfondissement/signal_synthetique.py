"""CONTRÔLE POSITIF (EXPLORATOIRE, hors verdict) : le pipeline de statistiques détecte-t-il un edge quand il en existe un ?

Idée. Un test qui répond toujours « pas d'edge » ne prouve rien : il faut montrer qu'il répond « edge » quand on en
plante un. On simule donc une sleeve SYNTHÉTIQUE dont le Sharpe vrai est connu (rendements gaussiens indépendants, vol
annuelle 10 %, graine fixe) et on la passe dans EXACTEMENT les mêmes fonctions que les sleeves réelles :
`pipeline.stats_periode` (Sharpe, IC 95 % par bootstrap stationnaire, drawdown), `stats.newey_west`, `stats.psr`,
`stats.dsr` (N = 8 essais, comme le protocole : 7 sleeves nulles + la sleeve à edge) et `gates.evaluer_gates_val`.

Deux volets :
  1. une illustration à graine fixe (Sharpe vrai 1,0), TRAIN et VAL ;
  2. une étude de répétition : pour chaque Sharpe vrai d'une petite grille, la fréquence à laquelle G1, G2 et G3 passeraient
     sur une fenêtre de la longueur de VAL. Au Sharpe vrai 0 cette fréquence est le taux de faux positifs.

Rien ici ne lit de données de marché ni ne touche au verdict ou au TEST : seules les dates (TRAIN/VAL) du calendrier servent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import donnees as d
from .. import gates, moteur, stats
from .. import pipeline as pl

GRAINE = 20261014          # fixée AVANT de regarder le résultat (jour de la correction) ; jamais cherchée
SHARPE_VRAI = 1.0          # edge de l'illustration
VOL_ANNUELLE = 0.10        # même volatilité cible que les sleeves du protocole
GRILLE_SHARPE_VRAI = (0.0, 0.5, 1.0, 1.5, 2.0)


def simuler_rendements(sharpe_vrai: float, n: int, rng: np.random.Generator, vol_annuelle: float = VOL_ANNUELLE) -> np.ndarray:
    """n rendements quotidiens gaussiens indépendants dont le Sharpe annualisé VRAI vaut `sharpe_vrai`.

    sigma_j = vol / racine(252) ; mu_j = Sharpe_vrai x vol / 252, donc mu_j / sigma_j x racine(252) = Sharpe_vrai."""
    sigma = vol_annuelle / np.sqrt(stats.JOURS_PAR_AN)
    mu = sharpe_vrai * vol_annuelle / stats.JOURS_PAR_AN
    return rng.normal(mu, sigma, size=n)


def resultat_synthetique(nom: str, rendements: np.ndarray, dates: pd.DatetimeIndex) -> moteur.Resultat:
    """Enveloppe une série simulée dans le même objet que les sleeves réelles (rendement net, sans coût de transaction)."""
    brut = pd.Series(rendements, index=dates)
    zero = pd.Series(0.0, index=dates)
    return moteur.Resultat(nom, brut, zero, zero.copy(), dates[0])


def _dsr_et_gates(edge_val: np.ndarray, nulles_val: list[np.ndarray], stats_val: dict) -> dict:
    """NW, PSR(0), DSR (N = 8 : l'edge + 7 sleeves nulles) et gates G1-G3 : mêmes fonctions que `stats_val_etendues` et `evaluer_gates_val`."""
    sharpes_q = np.array([stats.sharpe(x, annualiser=False) for x in [edge_val, *nulles_val]])
    assert len(sharpes_q) == pl.N_ESSAIS
    sr0 = stats.sharpe_reference_dsr(sharpes_q)
    dsr = stats.dsr(edge_val, sharpes_q)
    return {"nw": stats.newey_west(edge_val), "psr0": stats.psr(edge_val, 0.0), "dsr": dsr,
            "sr0_annualise": float(sr0 * np.sqrt(stats.JOURS_PAR_AN)), "gates": gates.evaluer_gates_val(stats_val, dsr)}


def tirage_illustration(n: int, sharpe_vrai: float = SHARPE_VRAI, graine: int = GRAINE) -> tuple[np.ndarray, list[np.ndarray]]:
    """Le tirage de l'illustration : la sleeve à edge connu, puis 7 sleeves nulles (graine fixe, toujours le même)."""
    rng = np.random.default_rng(graine)
    edge = simuler_rendements(sharpe_vrai, n, rng)
    return edge, [simuler_rendements(0.0, n, rng) for _ in range(pl.N_ESSAIS - 1)]


def illustration(dates: pd.DatetimeIndex, sharpe_vrai: float = SHARPE_VRAI, graine: int = GRAINE) -> dict:
    """Une sleeve à edge connu + 7 sleeves nulles, sur le calendrier réel TRAIN + VAL, passées dans les statistiques du protocole."""
    edge, nulles = tirage_illustration(len(dates), sharpe_vrai, graine)
    r = resultat_synthetique("SYNTH", edge, dates)
    train = pl.stats_periode(r, d.DEBUT_DONNEES, d.FIN_TRAIN)
    val = pl.stats_periode(r, d.DEBUT_VAL, d.FIN_VAL)
    masque_val = (dates >= d.DEBUT_VAL) & (dates <= d.FIN_VAL)
    sortie = _dsr_et_gates(edge[masque_val], [x[masque_val] for x in nulles], val)
    return {"sharpe_vrai": sharpe_vrai, "graine": graine, "n_jours_total": int(len(dates)), "n_jours_val": int(val["n_jours"]),
            "TRAIN": train, "VAL": val, **sortie}


def puissance(sharpes_vrais=GRILLE_SHARPE_VRAI, n_jours: int = 1044, n_rep: int = 300, n_tirages: int = 1000,
              graine: int = GRAINE) -> dict:
    """Pour chaque Sharpe vrai : fréquence de passage de G1 (Sharpe >= 1), G2 (borne basse de l'IC 95 % > 0) et G3 (DSR >= 0,95)
    sur `n_rep` fenêtres simulées de `n_jours` jours (longueur de VAL), et couverture de l'IC 95 % (le vrai Sharpe est-il dedans ?).

    n_tirages est réduit à 1 000 par répétition (5 000 pour l'illustration) : seul le coût de calcul change, pas la procédure."""
    sortie = {}
    for k, sr in enumerate(sharpes_vrais):
        sh, g1, g2, g3, couvre = [], 0, 0, 0, 0
        for i in range(n_rep):
            rng = np.random.default_rng(np.random.SeedSequence([graine, k, i]))
            edge = simuler_rendements(sr, n_jours, rng)
            nulles = [simuler_rendements(0.0, n_jours, rng) for _ in range(pl.N_ESSAIS - 1)]
            s = stats.sharpe(edge)
            bas, haut = stats.ic_sharpe_bootstrap(edge, n_tirages=n_tirages, graine=graine + i)
            dsr = stats.dsr(edge, np.array([stats.sharpe(x, annualiser=False) for x in [edge, *nulles]]))
            sh.append(s)
            g1 += s >= gates.SEUIL_G1
            g2 += bas > 0
            g3 += dsr >= gates.SEUIL_G3
            couvre += bas <= sr <= haut
        sortie[str(sr)] = {"sharpe_estime_moyen": float(np.mean(sh)), "sharpe_estime_ecart_type": float(np.std(sh, ddof=1)),
                           "taux_G1": g1 / n_rep, "taux_G2": g2 / n_rep, "taux_G3": g3 / n_rep, "couverture_ic95": couvre / n_rep}
    return {"n_rep": n_rep, "n_jours": n_jours, "n_tirages_bootstrap": n_tirages, "par_sharpe_vrai": sortie}
