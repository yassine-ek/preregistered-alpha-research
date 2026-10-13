"""Horloge réelle des minutes HistData (constat de la contre-vérification du 13/10).

Le prereg suppose des minutes en EST fixe (UTC-5). C'est faux : l'horloge suit l'heure d'été
(ouverture hebdomadaire du FX toujours à 17h00). Conséquence de l'ancienne hypothèse : les fenêtres
Londres/Tokyo de S4 et la fenêtre New York de S7 étaient lues une heure trop tôt pendant ~7 mois par an.
Ces tests échouent avec l'ancienne conversion `tz_convert('Etc/GMT+5')`."""
import pandas as pd
import pytest

from alpha import donnees as d

ANNEES_CACHE = range(2010, 2023)
CACHE_PRET = all((d.DOSSIER_CACHE / "minutes" / f"EURUSD_{a}.parquet").exists() for a in ANNEES_CACHE)


def _clock(date, hhmm, fuseau):
    h = pd.Timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[3:]))
    return d.local_vers_horloge_donnees(pd.DatetimeIndex([date]), h, fuseau)[0]


@pytest.mark.parametrize("date, hhmm, fuseau, attendu", [
    # régime ≤ 2018 : heure légale de New York
    ("2018-07-12", "15:30", "America/New_York", "2018-07-12 15:30"),    # été
    ("2018-12-06", "15:30", "America/New_York", "2018-12-06 15:30"),    # hiver
    ("2018-03-14", "15:30", "America/New_York", "2018-03-14 15:30"),    # US en DST, UE pas encore
    ("2018-07-12", "08:00", "Europe/London", "2018-07-12 03:00"),       # Londres BST -> 03h00
    ("2018-07-12", "09:00", "Asia/Tokyo", "2018-07-11 20:00"),          # Tokyo en été : 20h00 la veille
    # régime ≥ 2019 : UTC-5 l'hiver européen, UTC-4 l'été européen
    ("2022-07-12", "15:30", "America/New_York", "2022-07-12 15:30"),
    ("2022-12-06", "15:30", "America/New_York", "2022-12-06 15:30"),
    ("2021-03-17", "15:30", "America/New_York", "2021-03-17 14:30"),    # US en DST, UE encore en hiver
    ("2021-03-17", "08:00", "Europe/London", "2021-03-17 03:00"),
    ("2022-07-12", "09:00", "Asia/Tokyo", "2022-07-11 20:00"),
    ("2022-12-06", "09:00", "Asia/Tokyo", "2022-12-05 19:00"),
    # S5 : heure déjà exprimée dans l'horloge des fichiers -> lue telle quelle
    ("2022-07-12", "06:00", d.FUSEAU_DONNEES, "2022-07-12 06:00"),
])
def test_conversion_locale_vers_horloge_des_fichiers(date, hhmm, fuseau, attendu):
    assert _clock(pd.Timestamp(date), hhmm, fuseau) == pd.Timestamp(attendu)


@pytest.mark.skipif(not CACHE_PRET, reason="cache minutes EURUSD absent : lancer run_train_val.py une fois")
def test_regle_predit_l_ouverture_hebdomadaire_du_fx():
    """Le FX ouvre le dimanche à 17h00 heure de New York (21h00 UTC l'été, 22h00 l'hiver). La règle
    d'horloge doit prédire la première minute de chaque semaine (2010-2022) ; l'ancienne règle EST fixe
    n'en prédisait qu'environ 36 %."""
    bon, ancien, n = 0, 0, 0
    for an in ANNEES_CACHE:
        m = d.charger_minutes("EURUSD", debut=pd.Timestamp(f"{an}-01-01"), fin=pd.Timestamp(f"{an + 1}-01-01"))
        idx = m.index.to_series()
        for t in idx[idx.diff() > pd.Timedelta(hours=40)]:
            if t.dayofweek != 6:
                continue
            n += 1
            utc = pd.DatetimeIndex([t.normalize() + pd.Timedelta(hours=17)]).tz_localize("America/New_York").tz_convert("UTC")
            for p, cible in ((d.utc_vers_horloge_donnees(utc)[0], "bon"),
                             (utc.tz_convert(d.FUSEAU_DONNEES).tz_localize(None)[0], "ancien")):
                if 0 <= (t - p) / pd.Timedelta(minutes=1) <= 10:
                    if cible == "bon":
                        bon += 1
                    else:
                        ancien += 1
    assert n > 600
    assert bon / n > 0.98
    assert ancien / n < 0.5
