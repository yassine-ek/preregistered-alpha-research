"""Le TEST (>= 2023-01-01) doit être inaccessible depuis les chemins train/val."""
import pandas as pd
import pytest

from alpha import donnees as d
from outils_donnees import besoin_donnees, besoin_minutes


@besoin_donnees
def test_1h_tronque():
    s = d.charger_1h("EURUSD")
    assert s.index.max() < d.DEBUT_TEST
    assert s.index.max() >= pd.Timestamp("2022-12-29")  # la fin de VAL est bien là


def test_1h_refuse_au_dela():
    with pytest.raises(PermissionError):
        d.charger_1h("EURUSD", fin=pd.Timestamp("2024-01-01"))


@besoin_donnees
def test_instantanes_refusent_le_test():
    with pytest.raises(PermissionError):
        d.prix_instantanes(["EURUSD"], d.DEBUT_DONNEES, pd.Timestamp("2023-02-01"))
    p = d.prix_instantanes(["EURUSD"], d.DEBUT_DONNEES, d.FIN_VAL)
    assert p.index.max() <= d.FIN_VAL


@besoin_minutes
def test_minutes_tronquees_et_refus():
    m = d.charger_minutes("EURUSD", debut=pd.Timestamp("2022-11-01"))
    assert len(m) > 10000 and m.index.max() < d.DEBUT_TEST
    with pytest.raises(PermissionError):
        d.charger_minutes("EURUSD", debut=pd.Timestamp("2022-11-01"), fin=pd.Timestamp("2023-03-01"))


@besoin_minutes
def test_annee_test_jamais_lue_en_mode_scelle(monkeypatch):
    """En mode scellé, aucune année >= 2023 ne doit même être demandée au disque."""
    annees_lues = []
    original = d._annee_minute

    def espion(actif, annee):
        annees_lues.append(annee)
        return original(actif, annee)

    monkeypatch.setattr(d, "_annee_minute", espion)
    d.charger_minutes("EURUSD", debut=pd.Timestamp("2022-06-01"))
    assert annees_lues and max(annees_lues) == 2022


@besoin_minutes
def test_fenetre_heure_d_ete_et_d_hiver():
    """Fenêtre Londres 08h-14h : 03h01-09h01 sur l'horloge des fichiers, été comme hiver (l'horloge
    HistData suit l'heure d'été, elle n'est pas en EST fixe : voir tests/test_horloge_donnees.py).
    Ancienne version de ce test (fausse) : 02h01-08h01 l'été."""
    m = d.charger_minutes("EURUSD", debut=pd.Timestamp("2022-06-01"))
    dates = pd.DatetimeIndex(["2022-07-12", "2022-12-06"])
    f = d.rendements_fenetre(m, dates, "Europe/London", "08:00", "14:00")
    et = m.loc["2022-07-12 09:01", "o"] / m.loc["2022-07-12 03:01", "o"] - 1
    hi = m.loc["2022-12-06 09:01", "o"] / m.loc["2022-12-06 03:01", "o"] - 1
    assert abs(f["ret"].iloc[0] - et) < 1e-12 and abs(f["ret"].iloc[1] - hi) < 1e-12


def test_date_comptable():
    idx = pd.DatetimeIndex(["2022-03-08 09:01",   # mardi avant 11h -> mardi
                            "2022-03-08 12:00",   # mardi après 11h -> mercredi
                            "2022-03-11 16:00",   # vendredi après 11h -> lundi
                            "2022-03-13 18:00"])  # dimanche -> lundi
    out = d.date_comptable(idx)
    assert list(out.strftime("%Y-%m-%d")) == ["2022-03-08", "2022-03-09", "2022-03-14", "2022-03-14"]
