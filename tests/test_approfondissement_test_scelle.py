"""Approfondissement (EXPLORATOIRE) : la troncature du TEST reste active (rien >= 2023-01-01 n'est lu ni produit)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alpha import donnees as d
from alpha.approfondissement import chargement as ap
from outils_donnees import besoin_donnees

RACINE = Path(__file__).resolve().parents[1]


def _csv_1h(dossier: Path, actif: str = "XXXUSD") -> pd.DatetimeIndex:
    idx = pd.date_range("2022-06-01", "2024-06-01", freq="h")
    pd.DataFrame({"datetime": idx, "close": np.linspace(1, 2, len(idx))}).to_csv(dossier / f"{actif}_1h.csv", index=False)
    return idx


def test_lecteur_strict_tronque_et_arrete_tot(tmp_path, monkeypatch):
    idx = _csv_1h(tmp_path)
    monkeypatch.setattr(d, "DOSSIER_1H", tmp_path)
    monkeypatch.setattr(ap, "TAILLE_BLOC", 500)
    lus = {"lignes": 0}
    vrai = pd.read_csv

    def espion(*a, **k):
        for bloc in vrai(*a, **k):
            lus["lignes"] += len(bloc)
            yield bloc

    monkeypatch.setattr(pd, "read_csv", espion)
    s = ap.charger_1h_strict("XXXUSD")
    assert s.index.max() < d.DEBUT_TEST and s.index.max() >= pd.Timestamp("2022-12-31 22:00")
    n_total = len(idx)
    n_gardes = int((idx < d.DEBUT_TEST).sum())
    assert lus["lignes"] <= n_gardes + 500            # au plus un bloc au-delà du plafond
    assert lus["lignes"] < n_total / 2                # et on n'a PAS lu les 17 000 lignes de TEST
    with pytest.raises(PermissionError):
        ap.charger_1h_strict("XXXUSD", fin=pd.Timestamp("2024-01-01"))


def test_lecteur_strict_identique_au_lecteur_du_projet(tmp_path, monkeypatch):
    _csv_1h(tmp_path)
    monkeypatch.setattr(d, "DOSSIER_1H", tmp_path)
    a, b = ap.charger_1h_strict("XXXUSD"), d.charger_1h("XXXUSD")
    pd.testing.assert_series_equal(a, b)


def test_contexte_lecteur_strict_restaure_le_lecteur_officiel():
    avant = d.charger_1h
    with ap.lecteur_strict():
        assert d.charger_1h is ap.charger_1h_strict
    assert d.charger_1h is avant


def test_verifier_pas_de_test_leve():
    ok = pd.Series([1.0, 2.0], index=pd.to_datetime(["2022-12-29", "2022-12-30"]))
    ap.verifier_pas_de_test({"a": ok, "b": ok.to_frame()})
    mauvais = pd.Series([1.0, 2.0], index=pd.to_datetime(["2022-12-30", "2023-01-02"]))
    with pytest.raises(PermissionError):
        ap.verifier_pas_de_test({"x": mauvais})
    with pytest.raises(PermissionError):
        ap.verifier_pas_de_test(mauvais.to_frame())


@besoin_donnees
def test_minutes_et_base_ne_contiennent_pas_de_test():
    """Intégration : la base chargée (cache pickle ou pipeline) s'arrête à 2022-12-30 ; les minutes demandées aussi."""
    base = ap.charger_base()
    assert base["prix"].index.max() < d.DEBUT_TEST
    for nom, r in {**base["res"], "PILE": base["pile"]}.items():
        assert r.net.index.max() < d.DEBUT_TEST, nom
    for cle in ("fen4", "fen5", "pnl4", "pnl5"):
        assert base["fen"][cle].index.max() < d.DEBUT_TEST, cle
    m = ap.minutes("EURUSD")
    assert m.index.max() < d.DEBUT_TEST
    with pytest.raises(PermissionError):
        d.charger_minutes("EURUSD", debut=pd.Timestamp("2022-11-01"), fin=pd.Timestamp("2023-02-01"))


def test_json_approfondissement_sans_test_et_verdict_inchange():
    chemin = RACINE / "results" / "approfondissement.json"
    if not chemin.exists():
        pytest.skip("results/approfondissement.json pas encore généré")
    j = json.loads(chemin.read_text(encoding="utf-8"))
    assert pd.Timestamp(j["meta"]["dernier_jour_utilise"]) < d.DEBUT_TEST
    assert j["verdict_officiel_inchange"]["verdict"] == "ECHEC"
    assert j["verdict_officiel_inchange"]["statut_test"].startswith("scelle")
    assert not (RACINE / "results" / "test_ouvert.json").exists()  # ouvrir_test.py n'a jamais tourné


def test_prereg_et_ouvrir_test_intacts():
    """Garde-fou de l'approfondissement : la v1 du prereg garde son empreinte d'origine, PREREGISTRATION.md = v1 + les avenants 1 et 2
    (rien de plus : pas d'avenant ajouté par l'approfondissement), et le TEST n'a jamais été ouvert."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verifier_prereg", RACINE / "scripts" / "verifier_prereg.py")
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    assert vp.verifier() == []
    prereg = (RACINE / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert "AVENANT 1" in prereg and "AVENANT 2" in prereg and "AVENANT 3" not in prereg
    assert not (RACINE / "results" / "test_ouvert.json").exists()


def test_code_officiel_inchange_empreinte_identique():
    """L'approfondissement vit dans alpha/approfondissement/ (hors alpha/*.py) : l'empreinte du code officiel
    (alpha/*.py + run_train_val, ouvrir_test, verdict) est celle enregistrée dans results/empreinte_code.json.

    results/train_val.json garde l'empreinte du code d'AVANT la mise en conformité GitHub (chemins relatifs) ; le lien entre
    les deux est expliqué fichier par fichier dans results/empreinte_code.json et results/notes_implementation.md."""
    from alpha import pipeline as pl
    tv = json.loads((RACINE / "results" / "train_val.json").read_text(encoding="utf-8"))
    emp = json.loads((RACINE / "results" / "empreinte_code.json").read_text(encoding="utf-8"))
    assert emp["avant_chemins_13_10"]["sha256_code_octets_bruts"] == tv["meta"]["code_sha256"]
    assert pl.sha256_code() == emp["apres_audit_14_10"]["sha256_code"]      # la plus récente ; apres_chemins_13_10 reste l'historique
