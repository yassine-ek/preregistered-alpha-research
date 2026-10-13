"""Chaîne complète : données -> poids -> rendements nets -> pile -> statistiques.

Un seul chemin de code sert à run_train_val.py (fin = 2022-12-30, TEST scellé) et à
ouvrir_test.py (fin = dernière donnée, test_autorise=True). Comme tout est causal, les
chiffres TRAIN/VAL sont identiques dans les deux cas (ouvrir_test le vérifie).
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import donnees as d
from . import moteur, risque, sleeves, stats
from .couts import charger_couts

NOMS_SLEEVES = {
    "S1": "Trend following EWMAC",
    "S2": "Momentum cross-sectionnel devises",
    "S3": "Retournement court terme devises",
    "S4": "Saisonnalité intrajournalière FX",
    "S5": "Fixing de fin de mois",
    "S6": "Actions gérées par la volatilité",
    "S7": "Momentum intrajournalier SPX",
}
N_ESSAIS = 8  # 7 sleeves + la pile
RACINE = Path(__file__).resolve().parents[1]


def _log(msg: str, verbeux: bool) -> None:
    if verbeux:
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------- fenêtres 1 minute
def charger_fenetres(fin_incluse: pd.Timestamp, test_autorise: bool, verbeux: bool = False) -> dict:
    """Rendements de fenêtre (S4, S5, S7) + rendement du matin SPX. Un actif à la fois :
    le gros DataFrame 1 minute est libéré dès que ses fenêtres sont extraites."""
    fin_excl = pd.Timestamp(fin_incluse) + pd.Timedelta(days=1)
    dates = d.jours_ouvres(d.DEBUT_DONNEES, fin_incluse)
    fen4, fen5, pnl4, pnl5 = {}, {}, {}, {}
    fen7 = matin = pnl7 = None
    actifs = sorted(set(sleeves.S4_LONDRES) | set(sleeves.S4_TOKYO) | set(sleeves.S5_PAIRES) | {"SPXUSD"})
    for a in actifs:
        _log(f"minutes {a}", verbeux)
        m = d.charger_minutes(a, d.DEBUT_DONNEES, fin_excl, test_autorise)
        if a in sleeves.S4_LONDRES:
            f = d.rendements_fenetre(m, dates, "Europe/London", "08:00", "14:00")
            fen4[a], pnl4[a] = f["ret"], f["date_pnl"]
        if a in sleeves.S4_TOKYO:
            f = d.rendements_fenetre(m, dates, "Asia/Tokyo", "09:00", "15:00")
            fen4[a], pnl4[a] = f["ret"], f["date_pnl"]
        if a in sleeves.S5_PAIRES:
            f = d.rendements_fenetre(m, dates, d.FUSEAU_DONNEES, "06:00", "10:00")
            fen5[a], pnl5[a] = f["ret"], f["date_pnl"]
        if a == "SPXUSD":
            f = d.rendements_fenetre(m, dates, "America/New_York", "15:30", "16:00")
            fen7, pnl7 = f["ret"], f["date_pnl"]
            matin = d.rendement_matin_spx(m, dates)
        del m
    return {
        "dates": dates,
        "fen4": pd.DataFrame(fen4), "pnl4": pd.DataFrame(pnl4),
        "fen5": pd.DataFrame(fen5), "pnl5": pd.DataFrame(pnl5),
        "fen7": fen7, "pnl7": pnl7, "matin": matin,
    }


def prix_indices_06h(fin_incluse: pd.Timestamp, test_autorise: bool) -> pd.DataFrame:
    """Prix des indices à 06h00 EST (close de la barre 1 h étiquetée 05h00), signal S5."""
    dates = d.jours_ouvres(d.DEBUT_DONNEES, fin_incluse)
    fin_excl = pd.Timestamp(fin_incluse) + pd.Timedelta(days=1)
    indices = [sleeves.S5_INDICE_US] + [v[1] for v in sleeves.S5_PAIRES.values()]
    cols = {i: d.prix_a_heure_1h(d.charger_1h(i, fin_excl, test_autorise), dates, 6) for i in indices}
    return pd.DataFrame(cols)


# ---------------------------------------------------------------- calcul des sleeves
def calculer_sleeves(fin_incluse: pd.Timestamp = d.FIN_VAL, test_autorise: bool = False,
                     verbeux: bool = False) -> dict:
    fin_incluse = pd.Timestamp(fin_incluse)
    couts = charger_couts()
    actifs = d.univers()
    jours = d.jours_ouvres(d.DEBUT_DONNEES, fin_incluse)
    _log("prix instantanés 11h00", verbeux)
    prix = d.prix_instantanes(actifs, d.DEBUT_DONNEES, fin_incluse, test_autorise)
    res: dict[str, moteur.Resultat] = {}
    poids: dict[str, pd.DataFrame] = {}

    _, rend = sleeves.rendements_et_signal(prix)
    _log("S1 trend following", verbeux)
    poids["S1"] = sleeves.sleeve_s1(prix)
    res["S1"] = moteur.resultat_quotidien("S1", poids["S1"], rend, couts)

    val = sleeves.valeurs_devises(prix)
    rend_dev = val.ffill().pct_change(fill_method=None)
    cout_dev = pd.Series({dev: couts[paire] for dev, (paire, _) in sleeves.DEVISES.items()})
    _log("S2 momentum FX", verbeux)
    poids["S2"] = sleeves.sleeve_s2(prix)
    res["S2"] = moteur.resultat_quotidien("S2", poids["S2"], rend_dev, cout_dev)
    _log("S3 retournement FX", verbeux)
    poids["S3"] = sleeves.sleeve_s3(prix)
    res["S3"] = moteur.resultat_quotidien("S3", poids["S3"], rend_dev, cout_dev)

    _log("S6 actions vol-gérées (calibrage de c sur TRAIN)", verbeux)
    c_s6 = sleeves.calibrer_c_s6(prix.loc[: d.FIN_TRAIN])
    poids["S6"] = sleeves.sleeve_s6(prix, c_s6)
    res["S6"] = moteur.resultat_quotidien("S6", poids["S6"], rend[sleeves.INDICES_S6], couts)

    _log("fenêtres 1 minute (S4, S5, S7)", verbeux)
    f = charger_fenetres(fin_incluse, test_autorise, verbeux)
    poids["S4"] = sleeves.sleeve_s4(f["fen4"])
    res["S4"] = moteur.resultat_intrajournalier("S4", poids["S4"], f["fen4"], f["pnl4"], couts, jours)
    px06 = prix_indices_06h(fin_incluse, test_autorise)
    poids["S5"] = sleeves.sleeve_s5(f["fen5"], px06)
    res["S5"] = moteur.resultat_intrajournalier("S5", poids["S5"], f["fen5"], f["pnl5"], couts, jours)
    poids["S7"] = sleeves.sleeve_s7(f["fen7"], f["matin"])
    fen7 = f["fen7"].to_frame("SPXUSD")
    res["S7"] = moteur.resultat_intrajournalier("S7", poids["S7"], fen7, f["pnl7"].to_frame("SPXUSD"), couts, jours)

    # la sortie ne doit contenir aucune date de TEST quand il est scellé
    if not test_autorise:
        for r in res.values():
            assert r.net.index.max() < d.DEBUT_TEST
    ordre = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    return {"resultats": {k: res[k] for k in ordre}, "poids": poids, "c_s6": c_s6, "jours": jours}


# ------------------------------------------------------------------------- la pile
def construire_pile(resultats: dict[str, moteur.Resultat], fin_train: pd.Timestamp = d.FIN_TRAIN):
    """Poids ∝ 1/vol réalisée de chaque sleeve sur TRAIN (fenêtre commune où toutes sont
    actives), puis échelle unique pour que la pile ait 10 % de vol sur TRAIN. Aucun poids
    ne dépend d'un Sharpe. Les coûts de la pile sont la somme pondérée des coûts des
    sleeves, SANS compensation entre sleeves (hypothèse prudente)."""
    debut_commun = max(r.debut for r in resultats.values())
    noms = list(resultats)
    nets = pd.DataFrame({n: resultats[n].net for n in noms})
    train = nets.loc[debut_commun:fin_train]
    vol = train.std(ddof=1) * np.sqrt(stats.JOURS_PAR_AN)
    inv = 1.0 / vol
    w = inv / inv.sum()
    brut_c = sum(w[n] * resultats[n].brut for n in noms)
    cout_c = sum(w[n] * resultats[n].cout for n in noms)
    rot_c = sum(w[n] * resultats[n].rotation for n in noms)
    net_c = brut_c - cout_c
    kappa = risque.CIBLE_VOL / (net_c.loc[debut_commun:fin_train].std(ddof=1) * np.sqrt(stats.JOURS_PAR_AN))
    pile = moteur.Resultat("PILE", kappa * brut_c, kappa * cout_c, kappa * rot_c, debut_commun)
    return pile, {n: float(w[n]) for n in noms}, float(kappa)


# -------------------------------------------------------------------- statistiques
def stats_periode(r: moteur.Resultat, debut: pd.Timestamp, fin: pd.Timestamp, avec_ic: bool = True) -> dict:
    """Statistiques de r sur [max(debut, début actif) ; fin]."""
    sub = r.tranche(max(pd.Timestamp(debut), r.debut), fin)
    out = stats.resume_periode(sub.brut, sub.cout, sub.rotation)
    out["premier_jour"] = str(sub.net.index.min().date()) if len(sub.net) else None
    if avec_ic:
        bas, haut = stats.ic_sharpe_bootstrap(sub.net.to_numpy())
        out["ic95_sharpe"] = [bas, haut]
    return out


def stats_val_etendues(resultats: dict[str, moteur.Resultat], pile: moteur.Resultat) -> dict:
    """NW + Holm (sur les 7 sleeves) + PSR(0) + DSR (N = 8) sur VAL."""
    tout = {**resultats, "PILE": pile}
    val = {k: r.tranche(max(d.DEBUT_VAL, r.debut), d.FIN_VAL).net for k, r in tout.items()}
    sharpes_q = np.array([stats.sharpe(v, annualiser=False) for v in val.values()])
    assert len(sharpes_q) == N_ESSAIS
    nw = {k: stats.newey_west(v) for k, v in val.items()}
    holm = stats.holm({k: nw[k]["p_nw"] for k in resultats})
    sr0 = stats.sharpe_reference_dsr(sharpes_q)
    sortie = {}
    for k, v in val.items():
        sortie[k] = {
            **nw[k],
            "p_holm_sleeves": holm.get(k),
            "psr0": stats.psr(v, 0.0),
            "dsr": stats.dsr(v, sharpes_q),
        }
    return {"par_serie": sortie, "sr0_dsr_quotidien": sr0, "sr0_dsr_annualise": sr0 * np.sqrt(stats.JOURS_PAR_AN),
            "sharpes_val_quotidiens": dict(zip(val.keys(), sharpes_q.tolist()))}


def sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def sha256_code() -> str:
    """Empreinte du code qui produit les résultats (alpha/*.py + run_train_val, ouvrir_test, verdict), pour tracer la version qui a produit un résultat."""
    h = hashlib.sha256()
    fichiers = list((RACINE / "alpha").glob("*.py")) + [RACINE / "scripts" / n for n in
                                                       ("run_train_val.py", "ouvrir_test.py", "verdict.py")]
    for f in sorted(fichiers):
        h.update(f.name.encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))  # fins de ligne normalisées : même empreinte sous Windows et Linux
    return h.hexdigest()
