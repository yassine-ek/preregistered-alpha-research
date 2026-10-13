"""Formules et simulations de l'APPROFONDISSEMENT (EXPLORATOIRE, ne modifie pas le verdict).

Aucune donnée ici : ce module ne contient que de la théorie (loi fondamentale de Grinold, erreur-type
du Sharpe de Lo/Mertens, puissance, Sharpe maximal attendu de Bailey-López de Prado, diversification),
donc il est rapide à tester contre des simulations. Les Sharpe sont ANNUALISÉS (racine de 252) sauf
mention « _jour ».
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

from .. import stats

JOURS = stats.JOURS_PAR_AN
EULER = stats.EULER_MASCHERONI


# ------------------------------------------------------------ Théme 1 : loi fondamentale
def ir_fondamental(tc: float, ic: float, breadth: float) -> float:
    """Clarke-de Silva-Thorley : IR = TC x IC x racine(BR)."""
    return float(tc * ic * np.sqrt(breadth))


def ic_requis(ir_cible: float, tc: float, breadth: float) -> float:
    """IC qu'il faudrait pour atteindre `ir_cible` avec ce transfert et cette breadth."""
    return float(ir_cible / (tc * np.sqrt(breadth)))


def breadth_requise(ir_cible: float, tc: float, ic: float) -> float:
    """Nombre de paris indépendants par an qu'il faudrait avec l'IC observé (inf si IC <= 0)."""
    if ic <= 0 or tc <= 0:
        return float("inf")
    return float((ir_cible / (tc * ic)) ** 2)


# --------------------------------------------------- Théme 3 : erreur-type et puissance
def se_sharpe(sr_annuel: float, n_jours: int, asymetrie: float = 0.0, kurtosis: float = 3.0) -> float:
    """Erreur-type ANNUALISÉE du Sharpe (Lo 2002, corrigée de Mertens 2002).

    Variance du Sharpe par jour : (1 - g3 SR + (g4 - 1)/4 SR^2) / n ; pour des rendements gaussiens
    (g3 = 0, g4 = 3) cela donne (1 + SR^2/2)/n, la formule de Lo. SR est en unités JOURNALIÈRES dans
    la formule (SR_jour = SR_annuel / racine(252)), puis on re-multiplie par racine(252)."""
    sr_j = sr_annuel / np.sqrt(JOURS)
    var_j = (1.0 - asymetrie * sr_j + (kurtosis - 1.0) / 4.0 * sr_j ** 2) / n_jours
    return float(np.sqrt(JOURS * var_j))


def sharpe_min_detectable(annees: float, puissance: float = 0.80, alpha: float = 0.05,
                          unilateral: bool = True, n_tests: int = 1) -> float:
    """Plus petit Sharpe VRAI détecté avec la puissance voulue : SR = z_alpha SE(0) + z_puissance SE(SR).
    Point fixe (la SE dépend légèrement du SR). `n_tests` > 1 : correction de Bonferroni."""
    a = alpha / n_tests
    z_a = sps.norm.ppf(1 - a) if unilateral else sps.norm.ppf(1 - a / 2)
    z_b = sps.norm.ppf(puissance)
    n = int(round(annees * JOURS))
    sr = (z_a + z_b) * se_sharpe(0.0, n)
    for _ in range(50):
        sr = z_a * se_sharpe(0.0, n) + z_b * se_sharpe(sr, n)
    return float(sr)


def annees_pour_detecter(sr_vrai: float, puissance: float = 0.80, alpha: float = 0.05,
                         unilateral: bool = True, n_tests: int = 1) -> float:
    """Durée d'historique (années) pour détecter `sr_vrai` : SE(0) = 1/racine(Y), SE(SR) = racine((1+SR^2/504)/Y)."""
    a = alpha / n_tests
    z_a = sps.norm.ppf(1 - a) if unilateral else sps.norm.ppf(1 - a / 2)
    z_b = sps.norm.ppf(puissance)
    return float((z_a + z_b * np.sqrt(1.0 + sr_vrai ** 2 / (2.0 * JOURS))) ** 2 / sr_vrai ** 2)


def proba_sharpe_inferieur_analytique(sr_obs: float, sr_vrai: float, n_jours: int) -> float:
    """P(SR_estimé <= sr_obs | SR vrai = sr_vrai), approximation normale de Lo."""
    return float(sps.norm.cdf((sr_obs - sr_vrai) / se_sharpe(sr_vrai, n_jours)))


def proba_sharpe_inferieur_parametrique(sr_obs: float, sr_vrai: float, n_jours: int, n_sim: int = 20000,
                                        graine: int = 7) -> float:
    """Même probabilité par simulation de rendements gaussiens indépendants."""
    rng = np.random.default_rng(graine)
    mu_j = sr_vrai / np.sqrt(JOURS)  # volatilité journalière = 1
    x = rng.normal(mu_j, 1.0, size=(n_sim, n_jours))
    sh = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(JOURS)
    return float(np.mean(sh <= sr_obs))


def proba_sharpe_inferieur_bootstrap(r: np.ndarray, sr_obs: float, sr_vrai: float, n_sim: int = 5000,
                                     bloc_moyen: float = 20, graine: int = 11) -> float:
    """Même probabilité par bootstrap stationnaire : on recentre les rendements OBSERVÉS de la sleeve
    pour que leur Sharpe vaille `sr_vrai` (queues et autocorrélation empiriques conservées)."""
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    centre = x - x.mean() + sr_vrai * x.std(ddof=1) / np.sqrt(JOURS)
    rng = np.random.default_rng(graine)
    idx = stats.indices_bootstrap_stationnaire(len(centre), bloc_moyen, n_sim, rng)
    ech = centre[idx]
    sh = ech.mean(axis=1) / ech.std(axis=1, ddof=1) * np.sqrt(JOURS)
    return float(np.mean(sh <= sr_obs))


# ------------------------------------------------------- Théme 4 : tests multiples
def sharpe_max_attendu(n_essais: int, sigma_sr: float) -> float:
    """Sharpe maximal attendu sous H0 (aucun vrai edge) parmi `n_essais` essais de Sharpe estimés
    d'écart-type `sigma_sr` (Bailey-López de Prado 2014) :
    E[max] ~ sigma ((1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))), g = constante d'Euler-Mascheroni."""
    if n_essais < 2:
        return 0.0
    z1 = sps.norm.ppf(1.0 - 1.0 / n_essais)
    z2 = sps.norm.ppf(1.0 - 1.0 / (n_essais * np.e))
    return float(sigma_sr * ((1.0 - EULER) * z1 + EULER * z2))


def esperance_max_gaussien(n: int) -> float:
    """Valeur exacte (intégration numérique) de E[max de n gaussiennes standard]."""
    x = np.linspace(-9, 9, 200001)
    f = n * x * sps.norm.pdf(x) * sps.norm.cdf(x) ** (n - 1)
    return float(np.trapezoid(f, x))


def simuler_sharpe_max(n_essais: int, n_jours: int, n_rep: int = 2000, graine: int = 3) -> tuple[float, float]:
    """Moyenne et écart-type du Sharpe annualisé MAXIMAL de `n_essais` stratégies de bruit blanc."""
    rng = np.random.default_rng(graine)
    maxi = np.empty(n_rep)
    for i in range(n_rep):
        x = rng.standard_normal((n_essais, n_jours))
        maxi[i] = (x.mean(axis=1) / x.std(axis=1, ddof=1)).max() * np.sqrt(JOURS)
    return float(maxi.mean()), float(maxi.std(ddof=1))


def n_essais_pour_sharpe(sr_cible: float, sigma_sr: float) -> float:
    """Plus petit N tel que le Sharpe maximal attendu sous H0 atteigne `sr_cible` (dichotomie sur la formule)."""
    bas, haut = 2.0, 2.0
    while sharpe_max_attendu(int(haut), sigma_sr) < sr_cible and haut < 1e15:
        haut *= 2.0
    bas = haut / 2.0
    for _ in range(80):
        milieu = np.sqrt(bas * haut)
        if sharpe_max_attendu(int(milieu), sigma_sr) < sr_cible:
            bas = milieu
        else:
            haut = milieu
    return float(haut)


def proba_au_moins_un_sharpe(sr_cible: float, n_essais: int, sigma_sr: float) -> float:
    """P(au moins un des N essais de bruit atteint `sr_cible`) = 1 - Phi(sr/sigma)^N."""
    return float(-np.expm1(n_essais * sps.norm.logcdf(sr_cible / sigma_sr)))


# ----------------------------------------------------------- Théme 6 : diversification
def sharpe_pile(s: float, n: int, rho: float) -> float:
    """SR_pile = s racine(N / (1 + (N-1) rho)) : N sleeves de même Sharpe s, corrélation moyenne rho."""
    return float(s * np.sqrt(n / (1.0 + (n - 1) * rho)))


def n_sleeves_requis(s: float, rho: float, cible: float = 2.0) -> float:
    """Nombre de sleeves de Sharpe s (corrélation moyenne rho) pour atteindre `cible` :
    N = cible^2 (1 - rho) / (s^2 - cible^2 rho) ; infini si s^2 <= cible^2 rho (plafond s/racine(rho) < cible)."""
    den = s ** 2 - cible ** 2 * rho
    return float("inf") if den <= 0 else float(cible ** 2 * (1.0 - rho) / den)


def sharpe_pile_matrice(sharpes: np.ndarray, corr: np.ndarray) -> dict:
    """Pile de risque égal (poids ∝ 1/vol) et pile de variance minimale conditionnelle (poids optimaux)
    avec les vrais Sharpe et la vraie matrice de corrélation."""
    s = np.asarray(sharpes, dtype=float)
    c = np.asarray(corr, dtype=float)
    egal = float(s.sum() / np.sqrt(np.ones(len(s)) @ c @ np.ones(len(s))))
    optimal = float(np.sqrt(max(s @ np.linalg.solve(c, s), 0.0)))
    return {"risque_egal": egal, "optimal_theorique": optimal}


def correlation_moyenne(corr: np.ndarray) -> float:
    """Moyenne des corrélations hors diagonale."""
    c = np.asarray(corr, dtype=float)
    n = len(c)
    return float((c.sum() - n) / (n * (n - 1)))


# ---------------------------------------------- Théme 2 : horizon optimal sous coût
def horizon_optimal_exponentiel(a: float, tau: float, cout: float) -> float:
    """Gain cumulé de prévision G(h) = a (1 - exp(-h/tau)), coût par aller-retour `cout`. Le rendement net
    PAR JOUR est (G(h) - cout)/h ; son maximum vérifie 1 - (1 + u) exp(-u) = cout/a avec u = h/tau
    (le gain marginal égale le taux net moyen). Retourne h* (inf-> NaN si cout >= a : jamais rentable)."""
    if cout >= a or a <= 0:
        return float("nan")
    cible = cout / a
    bas, haut = 1e-9, 1.0
    while 1 - (1 + haut) * np.exp(-haut) < cible:
        haut *= 2
    for _ in range(100):
        m = 0.5 * (bas + haut)
        if 1 - (1 + m) * np.exp(-m) < cible:
            bas = m
        else:
            haut = m
    return float(tau * 0.5 * (bas + haut))


def rendement_net_par_jour(h: np.ndarray, a: float, tau: float, cout: float) -> np.ndarray:
    """(G(h) - cout) / h pour G(h) = a (1 - exp(-h/tau))."""
    h = np.asarray(h, dtype=float)
    return (a * (1.0 - np.exp(-h / tau)) - cout) / h
