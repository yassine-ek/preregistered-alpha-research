"""Approfondissement (EXPLORATOIRE) : la théorie de alpha/approfondissement/theorie.py contre des simulations. Rapide (< 20 s)."""
import numpy as np

from alpha import stats
from alpha.approfondissement import theorie


def test_sharpe_max_attendu_formule_vs_simulation():
    """E[max] de N Sharpe de bruit blanc : formule de Bailey-López de Prado vs simulation (1008 jours)."""
    n_jours = 1008
    sigma = theorie.se_sharpe(0.0, n_jours)
    for n in (8, 30):
        moyenne, _ = theorie.simuler_sharpe_max(n, n_jours, n_rep=1500, graine=5 + n)
        assert abs(theorie.sharpe_max_attendu(n, sigma) - moyenne) < 0.06, n
        # la formule approche l'espérance exacte du max de N gaussiennes à moins de 4 %
        exact = theorie.esperance_max_gaussien(n) * sigma
        assert abs(theorie.sharpe_max_attendu(n, sigma) - exact) / exact < 0.04, n
    assert theorie.sharpe_max_attendu(1, 0.5) == 0.0
    assert theorie.sharpe_max_attendu(134, 0.5) > theorie.sharpe_max_attendu(8, 0.5)  # croît avec N


def test_erreur_type_du_sharpe_vs_bruit_blanc():
    """Monte-Carlo : l'écart-type du Sharpe annualisé d'un bruit blanc = formule de Lo (1/racine(années)),
    et la SE annualisée dépend très peu du Sharpe vrai (1 + SR^2/504)."""
    rng = np.random.default_rng(1)
    n = 1008
    for sr_vrai in (0.0, 1.0):
        x = rng.normal(sr_vrai / np.sqrt(252), 1.0, size=(6000, n))
        sh = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(252)
        assert abs(sh.std(ddof=1) / theorie.se_sharpe(sr_vrai, n) - 1) < 0.04, sr_vrai
    assert abs(theorie.se_sharpe(0.0, n) - 0.5) < 0.01  # 4 ans -> 0,5, comme dans le README
    # asymétrie négative et queues épaisses : l'erreur-type grandit pour un Sharpe positif
    assert theorie.se_sharpe(1.5, n, asymetrie=-1.0, kurtosis=10.0) > theorie.se_sharpe(1.5, n)


def test_se_formule_vs_bootstrap_stationnaire_sur_bruit_blanc():
    """La largeur de l'IC bootstrap du projet (stats.ic_sharpe_bootstrap) ~ 2 x 1,96 x SE de Lo, en moyenne sur 12 séries."""
    rng = np.random.default_rng(2)
    n = 1008
    largeurs = []
    for _ in range(12):
        x = rng.standard_normal(n) * 0.01
        bas, haut = stats.ic_sharpe_bootstrap(x, n_tirages=1500, graine=int(rng.integers(1, 1e6)))
        largeurs.append((haut - bas) / (2 * 1.96))
    assert abs(np.mean(largeurs) / theorie.se_sharpe(0.0, n) - 1) < 0.12


def test_puissance_80_pourcent_par_simulation():
    """Un vrai Sharpe égal au Sharpe minimal détectable est détecté (t unilatéral 5 %) dans ~80 % des cas."""
    rng = np.random.default_rng(3)
    n, annees = 1008, 4.0
    sr_min = theorie.sharpe_min_detectable(annees)
    x = rng.normal(sr_min / np.sqrt(252), 1.0, size=(8000, n))
    sh = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(252)
    seuil = 1.6449 * theorie.se_sharpe(0.0, n)
    assert abs(np.mean(sh > seuil) - 0.80) < 0.025
    # durée nécessaire : à cette durée, le Sharpe détectable retombe sur le Sharpe visé
    y = theorie.annees_pour_detecter(0.5)
    assert abs(theorie.sharpe_min_detectable(y) - 0.5) < 0.01
    assert theorie.sharpe_min_detectable(4, n_tests=7) > theorie.sharpe_min_detectable(4)  # Bonferroni durcit


def test_proba_sharpe_inferieur_trois_methodes():
    """Analytique, paramétrique et bootstrap donnent la même probabilité sur un bruit blanc (marge 0,03)."""
    rng = np.random.default_rng(4)
    x = rng.standard_normal(1044) * 0.01  # Sharpe vrai 0
    sr_obs = 0.0
    p_a = theorie.proba_sharpe_inferieur_analytique(sr_obs, 0.5, 1044)
    p_p = theorie.proba_sharpe_inferieur_parametrique(sr_obs, 0.5, 1044, n_sim=8000)
    p_b = theorie.proba_sharpe_inferieur_bootstrap(x, sr_obs, 0.5, n_sim=3000)
    assert abs(p_a - p_p) < 0.03 and abs(p_a - p_b) < 0.04
    assert 0.1 < p_a < 0.2  # Phi(-1) ~ 0,16


def test_n_essais_pour_sharpe_et_proba():
    n = theorie.n_essais_pour_sharpe(2.0, 0.5)
    assert abs(theorie.sharpe_max_attendu(int(n), 0.5) - 2.0) < 0.02
    assert theorie.n_essais_pour_sharpe(2.0, 1.0) < theorie.n_essais_pour_sharpe(2.0, 0.5)  # backtest plus court : plus facile
    # P(au moins un des N bruits >= 2) = 1 - Phi(2/sigma)^N : vérif par simulation gaussienne directe
    rng = np.random.default_rng(6)
    sim = np.mean((rng.standard_normal((20000, 20)) * 0.8).max(axis=1) >= 2.0)
    assert abs(theorie.proba_au_moins_un_sharpe(2.0, 20, 0.8) - sim) < 0.01


def test_diversification_formules():
    s, rho = 0.5, 0.026
    n = theorie.n_sleeves_requis(s, rho, cible=2.0)
    assert abs(theorie.sharpe_pile(s, n, rho) - 2.0) < 1e-9
    assert theorie.n_sleeves_requis(0.5, 0.0) == 16.0  # sous indépendance : (2/0,5)^2 = 16
    assert theorie.n_sleeves_requis(0.5, 0.1) == float("inf")  # plafond s/racine(rho) = 1,58 < 2
    # matrice : deux sleeves non corrélées de Sharpe 1 -> racine(2)
    r = theorie.sharpe_pile_matrice(np.array([1.0, 1.0]), np.eye(2))
    assert abs(r["risque_egal"] - np.sqrt(2)) < 1e-12 and abs(r["optimal_theorique"] - np.sqrt(2)) < 1e-12
    c = np.array([[1.0, 0.3], [0.3, 1.0]])
    assert abs(theorie.correlation_moyenne(c) - 0.3) < 1e-12


def test_loi_fondamentale_identites():
    ir = theorie.ir_fondamental(0.9, 0.05, 400)
    assert abs(ir - 0.9) < 1e-12  # 0,9 x 0,05 x 20
    assert abs(theorie.ir_fondamental(0.9, theorie.ic_requis(2.0, 0.9, 400), 400) - 2.0) < 1e-12
    assert abs(theorie.ir_fondamental(0.9, 0.05, theorie.breadth_requise(2.0, 0.9, 0.05)) - 2.0) < 1e-9
    assert theorie.breadth_requise(2.0, 0.9, -0.01) == float("inf")  # IC <= 0 : aucune breadth ne suffit


def test_horizon_optimal_exponentiel_vs_grille():
    """Le maximum de (G(h) - C)/h trouvé par la condition 1 - (1+u)exp(-u) = C/A égale celui d'une grille fine."""
    a, tau, cout = 10.0, 5.0, 1.5
    h_star = theorie.horizon_optimal_exponentiel(a, tau, cout)
    grille = np.linspace(0.05, 60, 120000)
    h_grille = grille[np.argmax(theorie.rendement_net_par_jour(grille, a, tau, cout))]
    assert abs(h_star - h_grille) < 0.01
    assert theorie.horizon_optimal_exponentiel(a, tau, 1.0) < theorie.horizon_optimal_exponentiel(a, tau, 5.0)  # coût plus haut : on tient plus longtemps
    assert np.isnan(theorie.horizon_optimal_exponentiel(a, tau, 12.0))  # coût > gain total : jamais rentable
