"""Coûts et moteur : coûts nuls = rendement brut ; chronologie exacte d'une exécution décalée."""
import numpy as np
import pandas as pd
import pytest

from alpha import couts, gates, moteur


def _jeu():
    idx = pd.bdate_range("2020-01-01", periods=10)
    rend = pd.DataFrame({"X": [0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09]}, index=idx)
    poids = pd.DataFrame({"X": 0.0}, index=idx)
    poids.iloc[2:5] = 1.0  # décidé aux jours 2, 3 et 4 ; décidé 0 au jour 5
    return rend, poids


def test_chronologie_execution():
    rend, poids = _jeu()
    r = moteur.resultat_quotidien("T", poids, rend, pd.Series({"X": 10.0}))
    # décidé au jour 2 -> exécuté au snapshot 3 -> gagne les rendements des jours 4, 5 et 6
    # (0.04, 0.05, 0.06) ; décidé 0 au jour 5 -> exécuté au snapshot 6 -> plus rien ensuite
    assert r.brut.iloc[3] == 0.0 and r.brut.iloc[2] == 0.0
    assert r.brut.iloc[4:7].tolist() == pytest.approx([0.04, 0.05, 0.06])
    assert r.brut.iloc[7] == 0.0
    # coût d'ouverture au snapshot 3, de fermeture au snapshot 6 : 10 bps x 1
    assert r.cout.iloc[3] == pytest.approx(0.001) and r.cout.iloc[6] == pytest.approx(0.001)
    assert r.cout.sum() == pytest.approx(0.002)
    assert r.debut == poids.index[4]


def test_couts_nuls_donnent_le_brut():
    rend, poids = _jeu()
    poids.iloc[7] = -2.0
    r = moteur.resultat_quotidien("T", poids, rend, pd.Series({"X": 0.0}))
    assert (r.cout == 0).all()
    assert np.allclose(r.net, r.brut)


def test_intrajournalier_deux_jambes_et_couts_nuls():
    idx = pd.bdate_range("2020-01-01", periods=4)
    poids = pd.DataFrame({"X": [1.0, -2.0, 0.0, 1.0]}, index=idx)
    ret = pd.DataFrame({"X": [0.01, 0.02, 0.05, np.nan]}, index=idx)
    pnl = pd.DataFrame({"X": idx}, index=idx)
    r = moteur.resultat_intrajournalier("I", poids, ret, pnl, pd.Series({"X": 5.0}), idx)
    assert r.brut.tolist() == pytest.approx([0.01, -0.04, 0.0, 0.0])
    assert r.cout.tolist() == pytest.approx([2 * 5e-4, 2 * 2 * 5e-4, 0.0, 0.0])  # NaN -> pas de trade, pas de coût
    r0 = moteur.resultat_intrajournalier("I", poids, ret, pnl, pd.Series({"X": 0.0}), idx)
    assert np.allclose(r0.net, r0.brut)


def test_couts_reels(tmp_path):
    c = couts.charger_couts()
    assert c["SPXUSD"] == 12.0 and c["FRXEUR"] == 12.0
    assert c["EURUSD"] == pytest.approx(0.483075, abs=1e-5)
    f = tmp_path / "frais.csv"
    f.write_text("actif,classe,frais_bps_par_jambe,frais_editable_override\n"
                 "AAA,FX,1.0,\nBBB,FX,1.0,3.5\nIDX,Indice,4.0,2.0\n", encoding="utf-8")
    c2 = couts.charger_couts(f)
    assert c2["AAA"] == 1.0 and c2["BBB"] == 3.5 and c2["IDX"] == 12.0  # override sinon frais ; indices figés


def test_garde_fou_ouverture_du_test(tmp_path):
    def tv(g1, g2):
        return {"gates": {"G1": {"passe": g1}, "G2": {"passe": g2}}}

    ok, _ = gates.conditions_ouverture_test(tv(True, True), tmp_path / "test_ouvert.json")
    assert ok
    assert not gates.conditions_ouverture_test(tv(False, True), tmp_path / "test_ouvert.json")[0]
    assert not gates.conditions_ouverture_test(tv(True, False), tmp_path / "test_ouvert.json")[0]
    assert not gates.conditions_ouverture_test(None, tmp_path / "test_ouvert.json")[0]
    (tmp_path / "test_ouvert.json").write_text("{}")
    assert not gates.conditions_ouverture_test(tv(True, True), tmp_path / "test_ouvert.json")[0]


def test_verdict_selon_le_paragraphe_8():
    def g(a, b, c, d4=None):
        return {"G1": {"passe": a}, "G2": {"passe": b}, "G3": {"passe": c}, "G4": {"passe": d4}}

    assert gates.verdict(g(False, False, False), False) == ("ECHEC", "scelle_G1_ou_G2_en_echec")
    assert gates.verdict(g(True, True, True), False)[0] == "TEST_NON_OUVERT"
    assert gates.verdict(g(True, True, True, True), True)[0] == "SUCCES"
    assert gates.verdict(g(True, True, False, True), True)[0] == "ECHEC"
    assert gates.verdict(g(True, True, True, False), True)[0] == "ECHEC"
    assert gates.evaluer_g4(0.4, 1.0)["passe"] is False   # < 0,5 x Sharpe VAL
    assert gates.evaluer_g4(0.6, 1.0)["passe"] is True
