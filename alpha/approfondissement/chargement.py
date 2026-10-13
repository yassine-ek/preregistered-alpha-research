"""Chargement des données de l'APPROFONDISSEMENT (EXPLORATOIRE, ne modifie pas le verdict).

Deux garanties :
 1. Le TEST (>= 2023-01-01) n'est jamais lu. On remplace temporairement le lecteur 1 h du projet
    par une version STRICTE qui lit le CSV par petits blocs et s'arrête au premier bloc dépassant
    2022-12-31 (au plus 2000 lignes de trop sont parsées puis jetées, au lieu de tout le fichier).
    Les minutes viennent du cache parquet annuel TRAIN/VAL, qui ne contient aucune année de TEST.
 2. Les chiffres sont ceux du pipeline officiel : on appelle `pipeline.calculer_sleeves` tel quel et
    on « espionne » ses chargements au lieu de les refaire. Un garde-fou compare les Sharpe nets VAL
    obtenus à `results/train_val.json` (égalité à 1e-9) : si le lecteur strict changeait quoi que ce
    soit, on le saurait.
"""
from __future__ import annotations

import contextlib
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from .. import donnees as d
from .. import pipeline as pl
from .. import sleeves
from ..couts import FICHIER_FRAIS, charger_couts

RACINE = Path(__file__).resolve().parents[2]
CACHE_BASE = RACINE / "cache" / "appro_base.pkl"
TAILLE_BLOC = 2000  # lignes lues d'un coup ; le TEST n'est jamais parsé au-delà d'un bloc


def verifier_pas_de_test(obj, nom: str = "objet") -> None:
    """Lève si un index de dates de `obj` (Series/DataFrame/dict de ceux-ci) atteint 2023-01-01."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            verifier_pas_de_test(v, f"{nom}[{k}]")
        return
    if isinstance(obj, (pd.Series, pd.DataFrame)) and isinstance(obj.index, pd.DatetimeIndex) and len(obj):
        if obj.index.max() >= d.DEBUT_TEST:
            raise PermissionError(f"{nom} contient des dates du TEST (max {obj.index.max()}) : scellé.")


def charger_1h_strict(actif: str, fin: pd.Timestamp = d.DEBUT_TEST, test_autorise: bool = False) -> pd.Series:
    """Même contrat que `donnees.charger_1h`, mais lecture par blocs avec arrêt anticipé."""
    fin = d._verifier_plafond(fin, test_autorise)
    morceaux = []
    for bloc in pd.read_csv(d.DOSSIER_1H / f"{actif}_1h.csv", parse_dates=["datetime"], index_col="datetime",
                            chunksize=TAILLE_BLOC):
        morceaux.append(bloc["close"][bloc.index < fin])
        if bloc.index.max() >= fin:  # fichier trié par date : tout le reste est au-delà de `fin`
            break
    s = pd.concat(morceaux)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if not test_autorise:
        assert s.empty or s.index.max() < d.DEBUT_TEST, "fuite TEST dans le chargement 1 h (strict)"
    return s


@contextlib.contextmanager
def lecteur_strict():
    """Remplace `donnees.charger_1h` par la version stricte le temps du bloc `with`."""
    ancien = d.charger_1h
    d.charger_1h = charger_1h_strict
    try:
        yield
    finally:
        d.charger_1h = ancien


def classes_actifs() -> pd.Series:
    """actif -> classe (FX, Indice, Métal, Matière première...), lue dans le fichier des coûts."""
    df = pd.read_csv(FICHIER_FRAIS, encoding="utf-8", encoding_errors="replace")
    return pd.Series(df["classe"].astype(str).values, index=df["actif"].values).loc[lambda s: ~s.index.duplicated()]


def _calculer_base() -> dict:
    """Exécute le pipeline officiel (TRAIN+VAL) et récupère au passage prix, fenêtres, résultats, poids."""
    capture: dict = {}
    orig_fen, orig_px, orig_06 = pl.charger_fenetres, d.prix_instantanes, pl.prix_indices_06h

    def espion_fen(*a, **k):
        capture["fen"] = orig_fen(*a, **k)
        return capture["fen"]

    def espion_06(*a, **k):
        capture["px06"] = orig_06(*a, **k)
        return capture["px06"]

    def espion_px(actifs, *a, **k):
        out = orig_px(actifs, *a, **k)
        capture.setdefault("prix", out)  # le 1er appel est celui des 58 actifs (prix_instantanes)
        return out

    pl.charger_fenetres, d.prix_instantanes, pl.prix_indices_06h = espion_fen, espion_px, espion_06
    try:
        with lecteur_strict():
            sortie = pl.calculer_sleeves(d.FIN_VAL, test_autorise=False)
    finally:
        pl.charger_fenetres, d.prix_instantanes, pl.prix_indices_06h = orig_fen, orig_px, orig_06
    res = sortie["resultats"]
    pile, poids_pile, kappa = pl.construire_pile(res)
    base = {
        "prix": capture["prix"], "fen": capture["fen"], "px06": capture["px06"], "res": res, "pile": pile, "poids_pile": poids_pile,
        "kappa": kappa, "poids": sortie["poids"], "c_s6": sortie["c_s6"], "couts": charger_couts(),
        "classes": classes_actifs(), "code_sha256": pl.sha256_code(),
    }
    verifier_pas_de_test(base["prix"], "prix")
    verifier_pas_de_test({k: r.net for k, r in res.items()}, "res")
    return base


def _verifier_contre_json(base: dict) -> None:
    """Garde-fou : les Sharpe nets VAL recalculés == results/train_val.json (1e-9)."""
    officiel = json.loads((RACINE / "results" / "train_val.json").read_text(encoding="utf-8"))
    tout = {**base["res"], "PILE": base["pile"]}
    for k, r in tout.items():
        s = pl.stats_periode(r, d.DEBUT_VAL, d.FIN_VAL, avec_ic=False)["sharpe_net"]
        ref = officiel["series"][k]["VAL"]["sharpe_net"]
        assert abs(s - ref) < 1e-9, f"{k} : Sharpe net VAL {s} != train_val.json {ref}"


def charger_base(rafraichir: bool = False) -> dict:
    """Base commune (prix, fenêtres, résultats, poids), avec cache pickle invalidé si le code change."""
    if CACHE_BASE.exists() and not rafraichir:
        try:
            base = pickle.loads(CACHE_BASE.read_bytes())
            if base.get("code_sha256") == pl.sha256_code():
                return base
        except Exception:
            pass
    base = _calculer_base()
    _verifier_contre_json(base)
    CACHE_BASE.parent.mkdir(exist_ok=True)
    CACHE_BASE.write_bytes(pickle.dumps(base))
    return base


def minutes(actif: str) -> pd.DataFrame:
    """Open/close 1 minute TRAIN+VAL d'un actif (cache parquet annuel, jamais d'année de TEST)."""
    m = d.charger_minutes(actif, d.DEBUT_DONNEES, d.DEBUT_TEST, test_autorise=False)
    verifier_pas_de_test(m, f"minutes {actif}")
    return m


# groupes d'actifs pratiques
PAIRES_S4 = {**sleeves.S4_LONDRES, **sleeves.S4_TOKYO}
