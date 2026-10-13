"""Approfondissement (EXPLORATOIRE) : briques de diagnostics.py (breadth, demi-vies, causes, profil gain/coût)."""
import numpy as np
import pandas as pd

from alpha.approfondissement import diagnostics as dg


def test_participation_nombre_effectif_de_paris():
    assert abs(dg.participation(np.eye(10)) - 10) < 1e-9          # 10 paris indépendants
    assert abs(dg.participation(np.ones((10, 10))) - 1) < 1e-9    # un seul pari déguisé en 10
    c = 0.5 * np.ones((10, 10)) + 0.5 * np.eye(10)                # corrélation 0,5
    assert abs(dg.participation(c) - 100 / (10 + 90 * 0.25)) < 1e-9


def test_n_effectif_transversal_retire_le_facteur_commun():
    """Des actifs qui ne bougent qu'avec un facteur commun valent 1 pari en brut, mais N-1 paris relatifs."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2015-01-01", periods=800)
    commun = rng.standard_normal((800, 1))
    Z = pd.DataFrame(commun + 0.2 * rng.standard_normal((800, 6)), index=idx)
    assert dg.n_effectif(Z, False, idx[0], idx[-1]) < 1.6
    assert dg.n_effectif(Z, True, idx[0], idx[-1]) > 3.5


def test_demi_vie_signal_ar1():
    rho = 0.9
    ac = {k: rho ** k for k in (1, 2, 4, 8, 13)}
    hl = dg.demi_vie_signal(ac, pas=1)
    assert abs(hl - np.log(2) / -np.log(rho)) < 0.5       # 6,6 pas (interpolation linéaire entre retards)
    assert dg.demi_vie_signal({1: 0.99, 2: 0.98}, 1) is None  # reste au-dessus de 0,5 : non défini
    assert dg.demi_vie_signal({1: 0.2}, 5) < 5               # tombe sous 0,5 avant un pas : moins d'un pas


def test_demi_vie_exponentielle_ic():
    h = [1, 2, 5, 10, 20, 60]
    ic = [0.05 * np.exp(-x / 10) for x in h]
    assert abs(dg.demi_vie_exponentielle(h, ic) - 10 * np.log(2)) < 1e-9
    assert dg.demi_vie_exponentielle(h, [-0.01] * 6) is None   # IC négatif : demi-vie non définie
    assert dg.demi_vie_exponentielle(h, [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]) is None  # IC croissant : pas de décroissance


def test_hetero_q_constance():
    rng = np.random.default_rng(1)
    # douze Sharpe annuels tirés autour d'un Sharpe constant : p de constance non nul
    sa = pd.Series(0.3 + rng.normal(0, 1.0, 12), index=range(2011, 2023))
    assert dg.hetero_q(sa)["p_constance"] > 0.05
    # six années à +3 puis six à -3 : hétérogénéité évidente
    sa2 = pd.Series([3.0] * 6 + [-3.0] * 6, index=range(2011, 2023))
    assert dg.hetero_q(sa2)["p_constance"] < 1e-6


def test_cause_principale_regles():
    c = dg.cause_principale
    assert c(0.1, -0.1, -0.3, 0.2)["cause"] == "pas d'alpha brut"
    assert "coût amplificateur" in c(-0.2, 0.1, -1.8, 0.0)["precision"]          # perte de 1,9 point de Sharpe due aux coûts
    assert c(0.6, 0.5, 0.0, 0.0)["cause"] == "coût"                              # alpha brut des deux côtés, net mangé
    assert c(0.6, 0.1, 0.05, 0.0, corr_indices=0.8)["cause"] == "régime"         # bêta actions
    assert c(0.6, 0.1, 0.05, 1.5, corr_indices=0.0)["cause"] == "régime"         # dépendance à la vol
    assert c(0.6, 0.1, 0.05, 0.2, corr_indices=0.1)["cause"] == "instabilité"


def test_plus_proche_grille_log():
    assert dg.plus_proche(29.8) == 20 and dg.plus_proche(9.5) == 10 and dg.plus_proche(3.5) == 5 and dg.plus_proche(51) == 60


def _spec_signal_persistant(avec_signal: bool):
    """Un actif unique dont le rendement suit le signe d'un signal persistant (ou pas)."""
    rng = np.random.default_rng(5)
    n = 3000
    idx = pd.bdate_range("2010-01-01", periods=n)
    s = np.sign(np.sin(np.arange(n) / 40.0))               # signal lent : change de signe tous les ~125 jours
    drift = 0.004 * s if avec_signal else 0.0 * s
    P = pd.DataFrame({"A": 100 * np.exp(np.cumsum(drift + 0.01 * rng.standard_normal(n)))}, index=idx)
    F = pd.DataFrame({"A": s}, index=idx)
    sig = pd.DataFrame({"A": 0.01}, index=idx)
    return dg.SpecQuotidienne("S1", F, P, sig, F, 1, "poolee", pd.Series({"A": 1.0}))


def test_profil_gain_cout_signal_planté():
    """Avec un vrai signal lent, le gain brut croît avec h et le coût par jour décroît ; sans signal, le gain est ~0."""
    avec = dg.profil_gain_cout(_spec_signal_persistant(True), horizons=[1, 5, 20, 60])["TRAIN"]
    assert avec[20]["gain_bps"] > avec[1]["gain_bps"] > 0
    # signal lent : seuls les vrais retournements coûtent, le coût par jour ne dépend presque pas de h
    assert abs(avec[60]["cout_bps_par_jour"] / avec[1]["cout_bps_par_jour"] - 1) < 0.2
    sans = dg.profil_gain_cout(_spec_signal_persistant(False), horizons=[1, 5, 20, 60])["TRAIN"]
    assert abs(sans[20]["gain_bps"]) < 0.6 * abs(avec[20]["gain_bps"])
    # le gain par jour de l'exposition brute vaut ~ 0,004 x 1e4 = 40 bps/jour pour le signal planté
    assert 25 < avec[20]["gain_bps_par_jour"] < 55


def test_profil_cout_par_jour_decroit_pour_un_signal_qui_change_tout_le_temps():
    """Signal de signe aléatoire (change presque à chaque décision) : le coût par décision est constant, donc le coût par jour ~ 1/h."""
    rng = np.random.default_rng(6)
    n = 3000
    idx = pd.bdate_range("2010-01-01", periods=n)
    P = pd.DataFrame({"A": 100 * np.exp(np.cumsum(0.01 * rng.standard_normal(n)))}, index=idx)
    F = pd.DataFrame({"A": np.sign(rng.standard_normal(n))}, index=idx)
    sp = dg.SpecQuotidienne("S1", F, P, pd.DataFrame({"A": 0.01}, index=idx), F, 1, "poolee", pd.Series({"A": 1.0}))
    pg = dg.profil_gain_cout(sp, horizons=[1, 5, 20])["TRAIN"]
    assert pg[20]["cout_bps_par_jour"] < pg[1]["cout_bps_par_jour"] / 10
    assert abs(pg[1]["gain_bps"]) < 5  # aucun gain : le signal est du bruit


def test_theme6_sur_json_synthetique():
    """Deux fois la même sleeve de Sharpe 1 à corrélation 0 -> pile racine(2) ; la formule du thème 6 le retrouve."""
    noms = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    corr = pd.DataFrame(np.eye(7), index=noms, columns=noms)
    tv = {"correlations": {"VAL": corr.to_dict()}, "series": {k: {"VAL": {"sharpe_net": 1.0}} for k in noms + ["PILE"]}}
    tv["series"]["PILE"]["VAL"]["sharpe_net"] = float(np.sqrt(7))
    t6 = dg.theme6_diversification(tv)
    assert abs(t6["pile_formule_risque_egal_avec_sharpe_reels"] - np.sqrt(7)) < 1e-9
    assert abs(t6["n_sleeves_requis_sharpe_05_rho_observe"] - 16.0) < 1e-9
    assert abs(t6["sharpe_individuel_requis_avec_7_sleeves"] - 2 / np.sqrt(7)) < 1e-9
