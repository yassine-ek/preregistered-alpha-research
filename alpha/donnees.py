"""Chargement des données (1 h et 1 minute) et construction des instantanés.

Règle d'or de ce module : le TEST (>= 2023-01-01) est SCELLÉ. Toute fonction de
chargement reçoit une borne `fin` (exclue) qui vaut par défaut DEBUT_TEST ; demander
plus loin lève PermissionError sauf si l'appelant passe `test_autorise=True`, ce que
seul `scripts/ouvrir_test.py` fait. Les données sont tronquées DÈS la lecture et un
assert vérifie le résultat : aucune ligne >= 2023-01-01 n'entre en mémoire.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

RACINE_PROJET = Path(__file__).resolve().parents[1]
# Données locales, jamais versionnées : variable d'environnement HISTDATA_DIR, sinon <projet>/data/histdata.
# Arborescence attendue : <racine>/processed/univers/<ACTIF>_1h.csv (barres 1 h) et
# <racine>/histdata_raw/<ACTIF>/<ACTIF>_<année>.zip (minutes HistData). Si elle est absente, les tests
# qui lisent les données sont sautés (voir tests/outils_donnees.py).
RACINE_DONNEES = Path(os.environ.get("HISTDATA_DIR") or RACINE_PROJET / "data" / "histdata")
DOSSIER_1H = RACINE_DONNEES / "processed" / "univers"
DOSSIER_1MIN = RACINE_DONNEES / "histdata_raw"
DOSSIER_CACHE = RACINE_PROJET / "cache"

# Découpage temporel du prereg (section 3)
DEBUT_DONNEES = pd.Timestamp("2010-01-01")
FIN_TRAIN = pd.Timestamp("2018-12-31")
DEBUT_VAL = pd.Timestamp("2019-01-01")
FIN_VAL = pd.Timestamp("2022-12-31")
DEBUT_TEST = pd.Timestamp("2023-01-01")  # borne EXCLUE du chargement train/val

ACTIFS_EXCLUS = {
    "WTIUSD", "ETXEUR", "XAUAUD", "XAUCHF", "XAUEUR", "XAUGBP", "UDXUSD", "GRXEUR",
}

# ATTENTION (relecture du 13/10) : les minutes HistData ne sont PAS en EST fixe (UTC-5), contrairement
# à ce que dit le prereg. L'horloge des fichiers suit l'heure d'été : ouverture hebdomadaire du FX
# toujours à 17h00, pic NFP à 08h30 et ouverture cash US à 09h30 été comme hiver. Deux régimes, établis
# sur l'ouverture hebdomadaire du FX (voir results/notes_implementation.md, section « Corrections ») :
#  - jusqu'au 2018-12-31 : heure légale de New York (DST américain) ;
#  - depuis le 2019-01-01 : UTC-5 l'hiver européen, UTC-4 l'été européen (= Europe/London - 5 h).
# Les deux coïncident hors des ~5 semaines par an où les DST américain et européen diffèrent.
DEBUT_HORLOGE_UE = pd.Timestamp("2019-01-01", tz="UTC")
# Fuseau « étiquettes » : les heures données directement dans l'horloge des fichiers (instantané 11h00,
# fenêtre S5 06h00-10h00) sont lues telles quelles, sans conversion.
FUSEAU_DONNEES = "Etc/GMT+5"
HEURE_INSTANTANE_EST = 11  # fixing global retenu par PIVOT-0 (étiquette de l'horloge des fichiers)


def _verifier_plafond(fin: pd.Timestamp, test_autorise: bool) -> pd.Timestamp:
    """Refuse de dépasser le plafond TEST sans autorisation explicite."""
    fin = pd.Timestamp(fin)
    if fin > DEBUT_TEST and not test_autorise:
        raise PermissionError(
            f"Le TEST (>= {DEBUT_TEST.date()}) est scellé : fin={fin} refusée. "
            "Seul scripts/ouvrir_test.py peut passer test_autorise=True."
        )
    return fin


def univers() -> list[str]:
    """Les actifs 1 h non exclus (58 sur les 60 fichiers : WTIUSD et GRXEUR sont morts)."""
    noms = sorted(p.name[: -len("_1h.csv")] for p in DOSSIER_1H.glob("*_1h.csv"))
    return [a for a in noms if a not in ACTIFS_EXCLUS]


# --------------------------------------------------------------------------- 1 h
def charger_1h(actif: str, fin: pd.Timestamp = DEBUT_TEST, test_autorise: bool = False) -> pd.Series:
    """Close 1 h. ATTENTION : l'étiquette `datetime` est le DÉBUT de la barre ; le close
    est donc le prix à étiquette + 59 min (vérifié contre le 1 minute : 97 % de
    correspondance à +59 min, 2 % à +0)."""
    fin = _verifier_plafond(fin, test_autorise)
    s = pd.read_csv(DOSSIER_1H / f"{actif}_1h.csv", parse_dates=["datetime"], index_col="datetime")["close"]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[s.index < fin]
    if not test_autorise:
        assert s.empty or s.index.max() < DEBUT_TEST, "fuite TEST dans le chargement 1 h"
    return s


def jours_ouvres(debut: pd.Timestamp, fin: pd.Timestamp) -> pd.DatetimeIndex:
    """Lundi-vendredi, bornes incluses. Pas de calendrier de bourse : un jour férié
    donne simplement un prix manquant (rendement nul)."""
    return pd.bdate_range(debut, fin)


def instantane_quotidien(s1h: pd.Series, jours: pd.DatetimeIndex) -> pd.Series:
    """Prix à 11h00 EST de chaque jour ouvré.

    Le close d'une barre étiquetée 10h00 tombe à 10h59 : c'est le dernier close connu à
    11h00. On prend donc la dernière barre d'étiquette <= 10h00 DU MÊME JOUR ; sinon NaN
    (le report de 3 jours max est fait plus tard, pour le signal seulement).
    Interprétation conservatrice : la barre étiquetée 11h00 se terminerait à 11h59, après
    l'instantané."""
    cible = jours + pd.Timedelta(hours=HEURE_INSTANTANE_EST - 1)
    pos = s1h.index.searchsorted(cible, side="right") - 1
    valide = pos >= 0
    pos = np.where(valide, pos, 0)
    etiquettes = s1h.index[pos]
    meme_jour = etiquettes.normalize() == jours
    valeurs = np.where(valide & meme_jour, s1h.values[pos], np.nan)
    return pd.Series(valeurs, index=jours, name=s1h.name)


def prix_instantanes(actifs: list[str], debut: pd.Timestamp = DEBUT_DONNEES,
                     fin: pd.Timestamp = FIN_VAL, test_autorise: bool = False) -> pd.DataFrame:
    """Matrice (jours ouvrés x actifs) des prix bruts de 11h00 EST (NaN si absent).
    `fin` est INCLUSE ici (dernier jour demandé)."""
    fin = pd.Timestamp(fin)
    _verifier_plafond(fin + pd.Timedelta(days=1), test_autorise)
    jours = jours_ouvres(debut, fin)
    colonnes = {}
    for a in actifs:
        s = charger_1h(a, fin=fin + pd.Timedelta(days=1), test_autorise=test_autorise)
        colonnes[a] = instantane_quotidien(s, jours)
    return pd.DataFrame(colonnes)


def prix_a_heure_1h(s1h: pd.Series, jours: pd.DatetimeIndex, heure_est: int, tolerance_jours: int = 4) -> pd.Series:
    """Prix à `heure_est` h 00 EST de chaque jour : close de la barre étiquetée heure_est-1.
    On accepte la dernière barre disponible avant (jour férié, indice fermé) dans la limite
    de `tolerance_jours` : un prix périmé est strictement passé, jamais futur."""
    cible = jours + pd.Timedelta(hours=heure_est - 1)
    pos = s1h.index.searchsorted(cible, side="right") - 1
    valide = pos >= 0
    pos = np.where(valide, pos, 0)
    etiquettes = s1h.index[pos]
    frais = (cible - etiquettes) <= pd.Timedelta(days=tolerance_jours)
    return pd.Series(np.where(valide & frais, s1h.values[pos], np.nan), index=jours)


# ------------------------------------------------------------------------ 1 minute
def _fichiers_minute(actif: str, annee: int) -> list[Path]:
    """Annuel s'il existe, sinon les mensuels de l'année (2026)."""
    dossier = DOSSIER_1MIN / actif
    annuel = dossier / f"{actif}_{annee}.zip"
    if annuel.exists():
        return [annuel]
    return sorted(dossier.glob(f"{actif}_{annee}[0-1][0-9].zip"))


def _lire_zip_minute(chemin: Path) -> pd.DataFrame:
    """Un zip HistData -> DataFrame (open, close) indexé par minute (horloge des fichiers, naïve)."""
    with zipfile.ZipFile(chemin) as z:
        nom = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        brut = pd.read_csv(z.open(nom), header=None, usecols=[0, 1, 2, 5],
                           dtype={0: "string", 1: "string"})
    brut.columns = ["d", "t", "o", "c"]  # usecols garde l'ordre des colonnes du fichier
    idx = pd.to_datetime(brut["d"] + " " + brut["t"], format="%Y.%m.%d %H:%M")
    out = pd.DataFrame({"o": brut["o"].astype("float64").values, "c": brut["c"].astype("float64").values}, index=idx)
    out.index.name = "minute"
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def _annee_minute(actif: str, annee: int) -> pd.DataFrame:
    """Année de minutes, avec cache parquet (le cache est par actif et par année :
    ne jamais appeler pour une année de TEST depuis un script train/val)."""
    DOSSIER_CACHE.mkdir(exist_ok=True)
    (DOSSIER_CACHE / "minutes").mkdir(exist_ok=True)
    chemin = DOSSIER_CACHE / "minutes" / f"{actif}_{annee}.parquet"
    if chemin.exists():
        return pd.read_parquet(chemin)
    fichiers = _fichiers_minute(actif, annee)
    if not fichiers:
        return pd.DataFrame({"o": [], "c": []}, index=pd.DatetimeIndex([], name="minute"))
    df = pd.concat([_lire_zip_minute(f) for f in fichiers]).sort_index()
    df.to_parquet(chemin)
    return df


def charger_minutes(actif: str, debut: pd.Timestamp = DEBUT_DONNEES, fin: pd.Timestamp = DEBUT_TEST,
                    test_autorise: bool = False) -> pd.DataFrame:
    """Open/close 1 minute, index = horloge des fichiers (naïf), tronqué à `fin` (exclue)."""
    fin = _verifier_plafond(fin, test_autorise)
    debut = pd.Timestamp(debut)
    annees = range(debut.year, (fin - pd.Timedelta(nanoseconds=1)).year + 1)
    morceaux = [_annee_minute(actif, a) for a in annees]
    df = pd.concat(morceaux) if morceaux else pd.DataFrame({"o": [], "c": []})
    df = df[(df.index >= debut) & (df.index < fin)]
    if not test_autorise:
        assert df.empty or df.index.max() < DEBUT_TEST, "fuite TEST dans le chargement 1 minute"
    return df


# ------------------------------------------------- fenêtres intrajournalières (S4/S5/S7)
def utc_vers_horloge_donnees(utc: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Instants UTC (tz-aware) -> étiquette naïve de l'horloge réelle des minutes HistData."""
    ny = utc.tz_convert("America/New_York").tz_localize(None)
    ue = utc.tz_convert("Europe/London").tz_localize(None) - pd.Timedelta(hours=5)
    return pd.DatetimeIndex(np.where(utc < DEBUT_HORLOGE_UE, ny.values, ue.values))


def local_vers_horloge_donnees(dates_locales: pd.DatetimeIndex, decalage: pd.Timedelta, fuseau: str) -> pd.DatetimeIndex:
    """date locale + heure locale d'un marché -> étiquette de l'horloge des minutes (gère l'heure d'été
    locale ET le DST de l'horloge des données). `fuseau == FUSEAU_DONNEES` : heure déjà exprimée dans
    l'horloge des fichiers, lue telle quelle (S5)."""
    local = (dates_locales + decalage).tz_localize(fuseau, ambiguous="NaT", nonexistent="NaT")
    if fuseau == FUSEAU_DONNEES:
        return local.tz_localize(None)
    return utc_vers_horloge_donnees(local.tz_convert("UTC"))


def date_comptable(instant_est: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Jour ouvré auquel on rattache un PnL réalisé à `instant_est` : le PnL gagné entre
    l'instantané 11h00 du jour J-1 (exclu) et celui du jour J (inclus) est daté J. Les
    week-ends sont reportés au lundi. Ainsi aucun PnL n'est daté avant sa réalisation."""
    jour = (instant_est - pd.Timedelta(hours=HEURE_INSTANTANE_EST)).normalize() + pd.Timedelta(days=1)
    dow = jour.dayofweek
    decal = np.where(dow == 5, 2, np.where(dow == 6, 1, 0))
    return jour + pd.to_timedelta(decal, unit="D")


def prix_minute(m: pd.DataFrame, instants: pd.DatetimeIndex, champ: str, sens: str,
                tolerance_min: int = 5) -> np.ndarray:
    """Prix 1 minute à `instants` (EST naïf).
    sens='apres' : première minute d'étiquette >= instant (pour un `open` d'exécution : un
    trou de données retarde l'exécution, il ne l'avance jamais).
    sens='avant' : dernière minute d'étiquette <= instant (pour un `close` de signal :
    uniquement du passé). Au-delà de la tolérance -> NaN (pas de trade)."""
    idx = m.index
    vals = m[champ].values
    t = pd.DatetimeIndex(instants)
    ok_t = ~t.isna()
    t_fill = t.where(ok_t, idx[0] if len(idx) else pd.Timestamp("2000-01-01"))
    if sens == "apres":
        pos = idx.searchsorted(t_fill, side="left")
        dans = pos < len(idx)
        pos = np.where(dans, pos, 0)
        ecart = idx[pos] - t_fill
        bon = dans & (ecart <= pd.Timedelta(minutes=tolerance_min)) & ok_t
    else:
        pos = idx.searchsorted(t_fill, side="right") - 1
        dans = pos >= 0
        pos = np.where(dans, pos, 0)
        ecart = t_fill - idx[pos]
        bon = dans & (ecart <= pd.Timedelta(minutes=tolerance_min)) & ok_t
    return np.where(bon, vals[pos], np.nan)


def rendements_fenetre(m: pd.DataFrame, dates_locales: pd.DatetimeIndex, fuseau: str,
                       debut_hhmm: str, fin_hhmm: str) -> pd.DataFrame:
    """Rendement open->open d'une fenêtre horaire locale pour chaque date locale.

    Convention du prereg + délai conservateur d'une minute : le signal est la minute
    d'étiquette `debut` (confirmée à sa clôture), l'entrée se fait à l'open de la minute
    suivante (debut+1 min), la sortie à l'open de la minute qui suit la fin de fenêtre
    (fin+1 min). Retourne ['ret', 'date_pnl'] indexé par date locale."""
    h0 = pd.Timedelta(hours=int(debut_hhmm[:2]), minutes=int(debut_hhmm[3:]))
    h1 = pd.Timedelta(hours=int(fin_hhmm[:2]), minutes=int(fin_hhmm[3:]))
    t_in = local_vers_horloge_donnees(dates_locales, h0 + pd.Timedelta(minutes=1), fuseau)
    t_out = local_vers_horloge_donnees(dates_locales, h1 + pd.Timedelta(minutes=1), fuseau)
    p_in = prix_minute(m, t_in, "o", "apres")
    p_out = prix_minute(m, t_out, "o", "apres")
    ret = p_out / p_in - 1.0
    ds = pd.Series(date_comptable(t_out), index=dates_locales)
    return pd.DataFrame({"ret": ret, "date_pnl": ds.values}, index=dates_locales)


def rendement_matin_spx(m: pd.DataFrame, dates_locales: pd.DatetimeIndex) -> pd.Series:
    """S7 : rendement close 16h00 ET de la veille ouvrée -> 10h00 ET du jour (closes de
    minutes étiquetées 16:00 et 10:00, ET = America/New_York)."""
    fuseau = "America/New_York"
    t_10 = local_vers_horloge_donnees(dates_locales, pd.Timedelta(hours=10), fuseau)
    veille = dates_locales - pd.offsets.BDay(1)
    t_16 = local_vers_horloge_donnees(veille, pd.Timedelta(hours=16), fuseau)
    p10 = prix_minute(m, t_10, "c", "avant")
    p16 = prix_minute(m, t_16, "c", "avant")
    return pd.Series(p10 / p16 - 1.0, index=dates_locales)
