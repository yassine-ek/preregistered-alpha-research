"""Diagnostics de l'APPROFONDISSEMENT : pourquoi les 7 sleeves ne marchent pas ici ?

EXPLORATOIRE, non pré-enregistré, ne modifie pas le verdict. TRAIN (<= 2018) et VAL (2019-2022)
seulement : le TEST (>= 2023) n'est jamais chargé (voir chargement.py).

Notations. Une sleeve produit à la date de décision J une PRÉVISION F[J, i] (le signal ou le poids) pour
chaque instrument i. Elle est exécutée à J+1 (un jour plein de décalage, comme le moteur), donc le
rendement « suivant » à l'horizon h est R_h(J, i) = P[J+1+h, i] / P[J+1, i] - 1. On le normalise par
la volatilité du passé (EWMA, connue en J) : y = R_h / (sigma_J racine(h)). L'IC est la corrélation de
rang entre F et y. Seule la CIBLE y regarde le futur ; les prévisions, elles, n'en dépendent pas
(testé : tests/test_approfondissement_ic.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

from .. import donnees as d
from .. import risque, sleeves, stats
from . import theorie
from .chargement import PAIRES_S4, verifier_pas_de_test

H_GRILLE = [1, 2, 5, 10, 20, 60]
MIN_S4 = [5, 15, 30, 60, 120, 240, 360]
MIN_S5 = [5, 15, 30, 60, 120, 240]
MIN_S7 = [1, 5, 10, 15, 20, 30]
PERIODES = {"TRAIN": (d.DEBUT_DONNEES, d.FIN_TRAIN), "VAL": (d.DEBUT_VAL, d.FIN_VAL)}
PERIODES_IC = {**PERIODES, "TOUT": (d.DEBUT_DONNEES, d.FIN_VAL)}  # TOUT = TRAIN+VAL, plus de puissance pour les courbes d'IC


def _nettoyer(o):
    """JSON strict : NaN/inf -> None, types numpy -> types Python."""
    if isinstance(o, dict):
        return {str(k): _nettoyer(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_nettoyer(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


# ------------------------------------------------------------------ machinerie de l'IC
def rendement_futur(P: pd.DataFrame, h: int, decalage: int = 1) -> pd.DataFrame:
    """R_h(J) = P[J+decalage+h] / P[J+decalage] - 1 : rendement exécuté à J+1, tenu h jours."""
    return P.shift(-(decalage + h)) / P.shift(-decalage) - 1.0


def rendement_du_jour(P: pd.DataFrame, h: int, decalage: int = 1) -> pd.DataFrame:
    """Rendement MARGINAL du seul jour h après l'exécution (courbe de décroissance « pure »)."""
    return P.shift(-(decalage + h)) / P.shift(-(decalage + h - 1)) - 1.0


def ic_coupe_par_date(F: pd.DataFrame, Y: pd.DataFrame, n_min: int = 4) -> pd.Series:
    """Corrélation de rang TRANSVERSALE (entre instruments) à chaque date."""
    ok = F.notna() & Y.notna()
    rf, ry = F.where(ok).rank(axis=1), Y.where(ok).rank(axis=1)
    ic = rf.corrwith(ry, axis=1)
    return ic.where(ok.sum(axis=1) >= n_min).dropna()


def ic_poolee_par_date(F: pd.DataFrame, Y: pd.DataFrame, n_min: int = 1) -> pd.Series:
    """IC « poolé » : rangs globaux (tous instruments, toutes dates) puis produit centré réduit
    moyenné par date. La moyenne de la série est la corrélation de rang globale ; la série sert
    au t de Newey-West. Capte la part « série temporelle » du signal (trend following)."""
    ok = F.notna() & Y.notna()
    f, y = F.where(ok).to_numpy(float), Y.where(ok).to_numpy(float)
    m = ok.to_numpy()
    if m.sum() < 30:
        return pd.Series(dtype=float)
    zf, zy = np.full(f.shape, np.nan), np.full(f.shape, np.nan)
    for z, v in ((zf, f), (zy, y)):
        r = sps.rankdata(v[m])
        z[m] = (r - r.mean()) / r.std()
    prod = np.where(m, zf * zy, np.nan)
    n = m.sum(axis=1)
    c = pd.Series(np.nansum(prod, axis=1) / np.where(n > 0, n, np.nan), index=F.index)
    return c.where(n >= n_min).dropna()


def resume_ic(serie: pd.Series, debut, fin, h: int, espacement: int = 1) -> dict:
    """Moyenne de l'IC sur [debut ; fin] et t de Newey-West (retards = chevauchement des rendements futurs)."""
    s = serie.loc[debut:fin].dropna()
    if len(s) < 20:
        return {"ic": None, "t_nw": None, "se": None, "n_dates": int(len(s))}
    retards = int(min(max(np.ceil(h / espacement), 5 if espacement == 1 else 2), len(s) // 4))
    nw = stats.newey_west(s.to_numpy(), retards=retards)
    # erreur-type NW de la moyenne : on recentre la série sur 1, son t vaut alors 1/SE
    t1 = stats.newey_west(s.to_numpy() - s.mean() + 1.0, retards=retards)["t_nw"]
    return {"ic": float(s.mean()), "t_nw": nw["t_nw"], "se": float(1.0 / t1) if t1 and np.isfinite(t1) else None,
            "n_dates": int(len(s))}


# ---------------------------------------------------------- les sleeves quotidiennes
@dataclass
class SpecQuotidienne:
    nom: str
    F: pd.DataFrame        # prévision à la date de décision (NaN : pas de décision)
    P: pd.DataFrame        # prix (reportés) pour les rendements futurs
    sigma: pd.DataFrame    # vol quotidienne EWMA, passé seulement
    W: pd.DataFrame        # poids réellement décidés (après tampon, plafond, normalisation)
    espacement: int        # jours ouvrés entre deux décisions
    mode: str              # 'coupe' (transversal) ou 'poolee'
    cout: pd.Series        # bps par jambe, par colonne


def specs_quotidiennes(base: dict) -> dict[str, SpecQuotidienne]:
    """Prévisions (sans aucun accès au futur) de S1, S2, S3, S6 à partir des fonctions des sleeves."""
    prix, couts, poids = base["prix"], base["couts"], base["poids"]
    rend = prix.ffill().pct_change(fill_method=None)
    sig = risque.vol_ewma(rend)
    specs = {"S1": SpecQuotidienne("S1", sleeves.previsions_ewmac(prix), prix.ffill(), sig, poids["S1"], 1, "poolee",
                                   couts.reindex(prix.columns))}
    val = sleeves.valeurs_devises(prix)
    v_sig, rd = val.ffill(limit=3), val.ffill().pct_change(fill_method=None)
    sig_d = risque.vol_ewma(rd)
    cout_dev = pd.Series({dev: couts[paire] for dev, (paire, _) in sleeves.DEVISES.items()})
    vendredi = pd.Series(prix.index.dayofweek == 4, index=prix.index)
    for nom, score in (("S2", v_sig / v_sig.shift(sleeves.HORIZON_S2) - 1.0),
                       ("S3", -(v_sig / v_sig.shift(sleeves.HORIZON_S3) - 1.0))):
        specs[nom] = SpecQuotidienne(nom, score.where(vendredi, np.nan), val.ffill(), sig_d, poids[nom], 5,
                                     "coupe", cout_dev)
    cols6 = sleeves.INDICES_S6
    fin_mois = pd.Series(sleeves.dernier_jour_ouvre_du_mois(prix.index), index=prix.index)
    specs["S6"] = SpecQuotidienne("S6", poids["S6"].where(fin_mois, np.nan), prix[cols6].ffill(), sig[cols6],
                                  poids["S6"], 21, "poolee", couts.reindex(cols6))
    return specs


def ic_serie(spec: SpecQuotidienne, h: int, marginal: bool = False) -> pd.Series:
    """Série de l'IC par date de décision pour l'horizon h (cumulé, ou jour h seul si marginal)."""
    cols = spec.F.columns
    brut = rendement_du_jour(spec.P, h) if marginal else rendement_futur(spec.P, h)
    echelle = spec.sigma[cols] if marginal else spec.sigma[cols] * np.sqrt(h)
    Y = brut[cols] / echelle
    if spec.mode == "coupe":
        return ic_coupe_par_date(spec.F, Y)
    return ic_poolee_par_date(spec.F, Y)


def courbe_ic(spec: SpecQuotidienne, horizons=H_GRILLE) -> dict:
    """{periode: {h: resume_ic}} pour l'IC cumulé, et pour l'IC marginal (jour h seul)."""
    out = {"cumule": {p: {} for p in PERIODES_IC}, "marginal": {p: {} for p in PERIODES_IC}}
    for h in horizons:
        for cle, marg in (("cumule", False), ("marginal", True)):
            s = ic_serie(spec, h, marg)
            for p, (a, b) in PERIODES_IC.items():
                out[cle][p][h] = resume_ic(s, a, b, 1 if marg else h, spec.espacement)
    return out


def demi_vie_exponentielle(horizons, valeurs) -> float | None:
    """Demi-vie (jours) d'un ajustement log-linéaire ic(h) = A exp(-h/tau) sur les points POSITIFS.
    Non défini (None) s'il y a moins de 3 points positifs ou si la pente n'est pas décroissante."""
    h = np.array(horizons, dtype=float)
    v = np.array([np.nan if x is None else x for x in valeurs], dtype=float)
    ok = np.isfinite(v) & (v > 0)
    if ok.sum() < 3:
        return None
    pente = np.polyfit(h[ok], np.log(v[ok]), 1)[0]
    return float(np.log(2) / -pente) if pente < 0 else None


def autocorr_signal(F: pd.DataFrame, pas: int, retards_pas=(1, 2, 4, 8, 13)) -> dict:
    """Corrélation (Pearson, poolée) entre le signal et lui-même `k` décisions plus tôt."""
    f = F.dropna(how="all")
    out = {}
    for k in retards_pas:
        a, b = f.iloc[k:].to_numpy(float), f.iloc[:-k].to_numpy(float)
        ok = np.isfinite(a) & np.isfinite(b)
        out[k] = float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 30 else None
    return {"pas_en_jours": pas, "autocorr": out}


def demi_vie_signal(autocorr: dict, pas: int) -> float | None:
    """Demi-vie du signal (jours) : retard où l'autocorrélation passe sous 0,5 (interpolation linéaire entre
    les retards testés, point de départ rho(0) = 1). None si elle reste au-dessus de 0,5 sur tous les retards."""
    pts = [(0, 1.0)] + sorted((k, v) for k, v in autocorr.items() if v is not None)
    for (k0, r0), (k1, r1) in zip(pts[:-1], pts[1:]):
        if r1 < 0.5 <= r0:
            return float((k0 + (r0 - 0.5) / (r0 - r1) * (k1 - k0)) * pas)
    return None


# --------------------------------------------- profil gain / coût selon l'horizon de re-signalisation
def positions_signe(spec: SpecQuotidienne) -> pd.DataFrame:
    """Positions « de principe » à partir de la prévision, normalisées à exposition brute 1 :
    S1 = signe de la prévision ; S2/S3 = +1 pour les 3 meilleurs scores, -1 pour les 3 pires."""
    F = spec.F.dropna(how="all")
    if spec.nom == "S1":
        pos = np.sign(F)
    else:
        r = F.rank(axis=1, method="first")
        pos = (r > F.notna().sum(axis=1).to_numpy()[:, None] - 3).astype(float) - (r <= 3).astype(float)
        pos = pos.where(F.notna())
    n_act = pos.abs().sum(axis=1).replace(0, np.nan)
    return pos.div(n_act, axis=0)


def profil_gain_cout(spec: SpecQuotidienne, horizons=H_GRILLE) -> dict:
    """Pour chaque horizon h : gain brut moyen d'une position de principe tenue h jours (bps de l'exposition
    brute), coût moyen de la re-signalisation tous les h jours (|variation de position| x coût), et
    rendement net PAR JOUR. Sert à situer l'horizon où le gain marginal de prévision rattrape le coût
    marginal de rotation. Sleeves à rebalancement hebdomadaire : h >= 5 seulement."""
    pos = positions_signe(spec)
    c = spec.cout.reindex(pos.columns).to_numpy() / 1e4
    out = {}
    for p, (a, b) in PERIODES.items():
        out[p] = {}
        for h in horizons:
            if spec.espacement > 1 and h < spec.espacement:
                out[p][h] = None
                continue
            R = rendement_futur(spec.P[pos.columns], h)
            sel = pos.loc[a:b]
            gain = (sel * R.reindex(sel.index)).sum(axis=1, min_count=1).dropna()
            k = max(int(round(h / spec.espacement)), 1)
            pos_prec = pos.shift(k).reindex(sel.index) if spec.espacement > 1 else pos.shift(h).reindex(sel.index)
            cout = ((sel - pos_prec).abs() * c[None, :]).sum(axis=1, min_count=1).reindex(gain.index).dropna()
            gain = gain.reindex(cout.index)
            if len(gain) < 20:
                out[p][h] = None
                continue
            g, co = float(gain.mean() * 1e4), float(cout.mean() * 1e4)
            out[p][h] = {"gain_bps": g, "cout_bps": co, "net_bps_par_jour": (g - co) / h,
                         "gain_bps_par_jour": g / h, "cout_bps_par_jour": co / h, "n": int(len(gain))}
    return out


# ------------------------------------------------------ IC en minutes (S4, S5, S7)
def retours_minutes(m: pd.DataFrame, dates: pd.DatetimeIndex, fuseau: str, debut_hhmm: str,
                    minutes_apres: list[int]) -> pd.DataFrame:
    """Rendement open->open entre l'entrée (début de fenêtre + 1 minute, comme le moteur) et l'entrée + k minutes."""
    h0 = pd.Timedelta(hours=int(debut_hhmm[:2]), minutes=int(debut_hhmm[3:]))
    t_in = d.local_vers_horloge_donnees(dates, h0 + pd.Timedelta(minutes=1), fuseau)
    p_in = d.prix_minute(m, t_in, "o", "apres")
    cols = {}
    for k in minutes_apres:
        cols[k] = d.prix_minute(m, t_in + pd.Timedelta(minutes=k), "o", "apres") / p_in - 1.0
    return pd.DataFrame(cols, index=dates)


def _ic_minutes_un_actif(direction: pd.DataFrame, rets: dict[str, pd.DataFrame], cout: pd.Series, minutes: list[int]) -> dict:
    """IC de rang poolé (toutes paires, tous jours) entre la direction et le rendement après k minutes,
    + gain brut moyen (bps) et coût aller-retour moyen (bps), par période."""
    out = {p: {} for p in PERIODES_IC}
    for k in minutes:
        Y = pd.DataFrame({a: rets[a][k] for a in rets})
        for p, (a, b) in PERIODES_IC.items():
            F = direction[list(rets)].loc[a:b]
            y = Y.loc[a:b]
            ok = (F.notna() & y.notna() & (F != 0))
            if ok.to_numpy().sum() < 30:
                out[p][k] = None
                continue
            s = ic_poolee_par_date(F.where(ok), y.where(ok))
            r = resume_ic(s, a, b, 1)
            gains = float(np.nanmean((F.where(ok) * y.where(ok)).to_numpy(float))) * 1e4
            nb = ok.sum().reindex(list(rets))
            cmoy = float((cout.reindex(list(rets)) * nb).sum() / nb.sum())
            out[p][k] = {**r, "gain_bps": gains, "cout_aller_retour_bps": 2 * cmoy}
    return out


def ic_minutes_sleeves(base: dict, charger_minutes) -> dict:
    """Décroissance en minutes de S4 (session locale), S5 (fixing de fin de mois) et S7 (dernière demi-heure),
    plus, pour S7, l'IC du signal du matin sur les 12 demi-heures de 10h00 à 16h00 (délai croissant)."""
    f, couts = base["fen"], base["couts"]
    dates = d.jours_ouvres(d.DEBUT_DONNEES, d.FIN_VAL)
    out = {}
    # S4 : direction constante par paire, fenêtre = session locale
    rets4, dir4 = {}, pd.DataFrame(index=dates)
    for a, sens in PAIRES_S4.items():
        m = charger_minutes(a)
        fuseau, deb = ("Europe/London", "08:00") if a in sleeves.S4_LONDRES else ("Asia/Tokyo", "09:00")
        rets4[a] = retours_minutes(m, dates, fuseau, deb, MIN_S4)
        dir4[a] = float(sens)
    out["S4"] = _ic_minutes_un_actif(dir4, rets4, couts, MIN_S4)
    # S5 : direction = signal de fin de mois (NaN ailleurs), fenêtre 06h00-10h00 (étiquettes)
    sig5 = sleeves.signal_s5(base["px06"]).reindex(dates)
    rets5 = {a: retours_minutes(charger_minutes(a), dates, d.FUSEAU_DONNEES, "06:00", MIN_S5) for a in sleeves.S5_PAIRES}
    out["S5"] = _ic_minutes_un_actif(sig5, rets5, couts, MIN_S5)
    # S7 : direction = signe du rendement du matin, fenêtre d'entrée 15h30 ET
    m7 = charger_minutes("SPXUSD")
    sig7 = pd.DataFrame({"SPXUSD": np.sign(base["fen"]["matin"].reindex(dates)).replace(0.0, np.nan)})
    rets7 = {"SPXUSD": retours_minutes(m7, dates, "America/New_York", "15:30", MIN_S7)}
    out["S7"] = _ic_minutes_un_actif(sig7, rets7, couts, MIN_S7)
    # S7 : IC du signal selon le DÉLAI (blocs d'une demi-heure de 10h00 à 15h30 ET, sortie +30 min)
    delais = {}
    for k in range(12):
        debut = pd.Timedelta(hours=10, minutes=30 * k)
        hhmm = f"{int(debut.total_seconds() // 3600):02d}:{int(debut.total_seconds() // 60 % 60):02d}"
        r = retours_minutes(m7, dates, "America/New_York", hhmm, [30])
        delais[hhmm] = _ic_minutes_un_actif(sig7, {"SPXUSD": r}, couts, [30])
    out["S7_delai_bloc_30min"] = delais
    verifier_pas_de_test(dir4, "dir4")
    return out


# ------------------------------------------------------------ Théme 1 : Grinold
def participation(R: np.ndarray) -> float:
    """Nombre effectif de paris indépendants = (somme des valeurs propres)^2 / somme de leurs carrés
    = N^2 / somme des carrés des corrélations (Meucci : « effective number of bets »)."""
    R = np.asarray(R, dtype=float)
    R = np.nan_to_num(R, nan=0.0)
    np.fill_diagonal(R, 1.0)
    return float(len(R) ** 2 / np.sum(R ** 2))


def n_effectif(Z: pd.DataFrame, transversal: bool, a, b) -> float:
    """Participation de la matrice de corrélation de rendements normalisés Z sur [a ; b].
    transversal=True : on retire la moyenne du jour (seuls les paris RELATIFS comptent pour un IC de coupe)."""
    z = Z.loc[a:b].dropna(axis=1, thresh=int(0.5 * len(Z.loc[a:b])))
    if transversal:
        z = z.sub(z.mean(axis=1), axis=0)
    c = z.corr(min_periods=100).to_numpy()
    c = np.where(np.isfinite(c), c, 0.0)
    return participation(c)


def transfert(spec: SpecQuotidienne, a, b) -> float:
    """TC = corrélation entre la prévision F et la position pondérée du risque w x sigma (Clarke et al.).
    Transversal (S2, S3) : moyenne des corrélations par date ; sinon corrélation poolée."""
    F = spec.F.loc[a:b]
    W = (spec.W * spec.sigma[spec.W.columns]).reindex(F.index)
    if spec.nom == "S6":  # prévision = le poids lui-même, plafonné par la règle de levier 2 : on compare à c/variance brute
        return _tc_s6(spec, a, b)
    ok = F.notna() & W.notna()
    if spec.mode == "coupe":
        vals = []
        for t in F.index[ok.sum(axis=1) >= 4]:
            x, y = F.loc[t][ok.loc[t]], W.loc[t][ok.loc[t]]
            if x.std() > 0 and y.std() > 0:
                vals.append(np.corrcoef(x, y)[0, 1])
        return float(np.mean(vals)) if vals else float("nan")
    x, y = F.where(ok).to_numpy(float), W.where(ok).to_numpy(float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1])


def _tc_s6(spec: SpecQuotidienne, a, b) -> float:
    """TC de S6 : corrélation entre 1/variance mensuelle réalisée non plafonnée et le poids appliqué (plafond 2)."""
    rend = spec.P.pct_change(fill_method=None)
    mois = rend.index.to_period("M")
    rv = (rend ** 2).groupby(mois).mean() * 252
    ideal = (1.0 / rv.where(rv > 0)).reindex(mois)
    ideal.index = rend.index
    ideal = ideal.where(spec.F.notna()).loc[a:b]
    reel = spec.F.loc[a:b]
    m = np.isfinite(ideal.to_numpy(float)) & np.isfinite(reel.to_numpy(float))
    return float(sps.spearmanr(ideal.to_numpy(float)[m], reel.to_numpy(float)[m])[0])


def horizon_detention(poids: pd.DataFrame, rotation_annuelle: float, a, b) -> float:
    """Durée moyenne de détention (jours) = 252 x exposition brute moyenne / rotation annuelle."""
    expo = poids.fillna(0.0).abs().sum(axis=1).loc[a:b].mean()
    return float(252.0 * expo / rotation_annuelle) if rotation_annuelle > 0 else float("nan")


def plus_proche(h: float, grille=H_GRILLE) -> int:
    """Élément de la grille le plus proche de h en échelle logarithmique."""
    return int(min(grille, key=lambda g: abs(np.log(g) - np.log(h))))


def ir_actif_vs_facteur(brut: pd.Series, facteur: pd.Series, a, b) -> dict:
    """Régression du rendement brut sur le facteur « indices » : alpha annualisé, vol résiduelle, IR actif
    (alpha / vol résiduelle) et bêta. C'est la grandeur que la loi de Grinold prédit (IR actif, pas Sharpe total)."""
    y = brut.loc[a:b]
    x = facteur.reindex(y.index)
    ok = y.notna() & x.notna()
    y, x = y[ok].to_numpy(), x[ok].to_numpy()
    beta = np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1)
    res = y - beta * x
    return {"beta": float(beta), "alpha_annuel": float(res.mean() * 252),
            "ir_actif": float(res.mean() / res.std(ddof=1) * np.sqrt(252)) if res.std() > 0 else None}


def theme1_grinold(base: dict, specs: dict[str, SpecQuotidienne], ic_minutes: dict, facteur_indices: pd.Series) -> dict:
    """Pour chaque sleeve et chaque période : IC, TC, breadth, IR prédit, Sharpe brut réalisé,
    IC et breadth nécessaires pour un IR de 2."""
    res, fen = base["res"], base["fen"]
    out = {"definitions": {
        "IC": "corrélation de rang entre la prévision (ou le poids) et le rendement futur normalisé par la vol passée, à l'horizon de détention",
        "TC": "corrélation entre la prévision et la position pondérée du risque (w x sigma) : ce que les contraintes (tampon, 3/3, plafond) retiennent du signal",
        "breadth": "nombre de paris indépendants par an = participation (nombre effectif) des instruments x 252 / horizon de détention (S4, S7 : 252 fenêtres/an ; S5 : 12 fins de mois/an)",
        "IR_predit": "TC x IC x racine(breadth) (Grinold / Clarke-de Silva-Thorley)",
    }, "sleeves": {}}
    for nom in ("S1", "S2", "S3", "S6", "S4", "S5", "S7"):
        r = res[nom]
        blocs = {}
        for p, (a, b) in PERIODES.items():
            a2 = max(a, r.debut)
            sub = r.tranche(a2, b)
            sr_brut = stats.sharpe(sub.brut)
            sr_net = stats.sharpe(sub.net)
            rot = float(sub.rotation.sum() / (len(sub.rotation) / 252))
            blocs[p] = {"n_jours": int(len(sub.brut)), "sharpe_brut": sr_brut, "sharpe_net": sr_net, "rotation_annuelle": rot,
                        "ir_actif_hors_facteur_indices": ir_actif_vs_facteur(r.brut, facteur_indices, a2, b)}
        if nom in specs:
            sp = specs[nom]
            for p, (a, b) in PERIODES.items():
                a2 = max(a, r.debut)
                h_det = horizon_detention(sp.W, blocs[p]["rotation_annuelle"], a2, b)
                h = plus_proche(h_det)
                s = ic_serie(sp, h)
                ic = resume_ic(s, a2, b, h, sp.espacement)
                Z = (sp.P.pct_change(fill_method=None) / sp.sigma.shift(1))[sp.F.columns]
                n_eff = n_effectif(Z, sp.mode == "coupe", a2, b)
                br = n_eff * 252.0 / h
                tc = transfert(sp, a2, b)
                blocs[p].update(horizon_detention_jours=h_det, horizon_ic_jours=h, ic=ic["ic"], t_nw_ic=ic["t_nw"],
                                se_ic=ic["se"], tc=tc, n_effectif=n_eff, breadth=br)
        else:  # sleeves intrajournalières : IC mesuré sur toute la fenêtre
            fen_cle = {"S4": MIN_S4[-1], "S5": MIN_S5[-1], "S7": MIN_S7[-1]}[nom]
            n_eff, par_an = {"S4": (None, 252.0), "S5": (None, 12.0), "S7": (1.0, 252.0)}[nom]
            for p, (a, b) in PERIODES.items():
                a2 = max(a, r.debut)
                mm = ic_minutes[nom][p][fen_cle]
                cols = {"S4": list(PAIRES_S4), "S5": list(sleeves.S5_PAIRES), "S7": ["SPXUSD"]}[nom]
                if nom == "S7":
                    ne = 1.0
                else:
                    z = fen["fen4" if nom == "S4" else "fen5"]
                    z = (z / z.std())[cols]
                    ne = n_effectif(z, False, a2, b)
                blocs[p].update(horizon_detention_jours=None, horizon_ic_jours=None, ic=mm["ic"] if mm else None,
                                t_nw_ic=mm["t_nw"] if mm else None, se_ic=mm["se"] if mm else None, tc=_tc_intra(base, nom, a2, b),
                                n_effectif=ne, breadth=ne * par_an)
        for p, bl in blocs.items():
            if bl.get("ic") is None or bl.get("tc") is None or not np.isfinite(bl["tc"]):
                bl["ir_predit"] = None
                continue
            bl["ir_predit"] = theorie.ir_fondamental(bl["tc"], bl["ic"], bl["breadth"])
            if bl.get("se_ic"):
                se_ir = bl["tc"] * np.sqrt(bl["breadth"]) * bl["se_ic"]
                se_sr = theorie.se_sharpe(bl["sharpe_brut"], bl["n_jours"])
                bl["se_ir_predit"] = se_ir
                bl["z_ecart_predit_vs_realise"] = (bl["sharpe_brut"] - bl["ir_predit"]) / float(np.hypot(se_ir, se_sr))
            bl["ic_requis_pour_ir_2"] = theorie.ic_requis(2.0, bl["tc"], bl["breadth"])
            bl["breadth_requise_pour_ir_2"] = theorie.breadth_requise(2.0, bl["tc"], bl["ic"])
            bl["facteur_breadth_a_trouver"] = (bl["breadth_requise_pour_ir_2"] / bl["breadth"]
                                               if np.isfinite(bl["breadth_requise_pour_ir_2"]) else None)
            bl["breadth_requise_pour_ir_2"] = bl["breadth_requise_pour_ir_2"] if np.isfinite(bl["breadth_requise_pour_ir_2"]) else None
        out["sleeves"][nom] = blocs
    out["pile"] = _pile_grinold(out["sleeves"])
    return out


def _pile_grinold(sl: dict) -> dict:
    """Breadth totale de la pile (sleeves supposées indépendantes : corrélation moyenne 0,03), IR prédit de la pile
    en risque égal, IC uniforme nécessaire pour un IR de 2, et accord prédit/réalisé sur les 14 couples (sleeve, période)."""
    n = len(sl)
    out = {}
    for p in PERIODES:
        bl = [sl[k][p] for k in sl]
        br = [b["breadth"] for b in bl]
        tc = float(np.nanmean([b["tc"] for b in bl]))
        ir = [b.get("ir_predit") for b in bl]
        out[p] = {"breadth_totale": float(np.sum(br)), "tc_moyen": tc,
                  "ir_pile_predit_risque_egal": float(np.nansum([x for x in ir if x is not None]) / np.sqrt(n)),
                  "ic_uniforme_requis_pour_ir_2": float(2.0 * np.sqrt(n) / (tc * np.sum(np.sqrt(br)))),
                  "ic_moyen_observe": float(np.mean([b["ic"] for b in bl if b["ic"] is not None]))}
    paires = [(sl[k][p]["ir_predit"], sl[k][p]["sharpe_brut"]) for k in sl for p in PERIODES if sl[k][p].get("ir_predit") is not None]
    x, y = np.array(paires).T
    out["accord_predit_realise"] = {"n_couples": int(len(x)), "correlation": float(np.corrcoef(x, y)[0, 1]),
                                    "correlation_rang_spearman": float(sps.spearmanr(x, y)[0])}
    return out


def _tc_intra(base: dict, nom: str, a, b) -> float:
    """TC des sleeves intrajournalières : corrélation entre la direction du signal et la position pondérée du risque.
    Le poids est direction x k / sigma par construction, donc le TC mesure surtout l'effet de l'estimation de sigma."""
    w = base["poids"][nom]
    fen = base["fen"]
    if nom == "S4":
        x = pd.DataFrame({a_: float(s) for a_, s in PAIRES_S4.items()}, index=w.index)
        sig = fen["fen4"].pow(2).ewm(halflife=risque.DEMI_VIE, min_periods=risque.MIN_OBS).mean().pow(0.5).shift(1)
    elif nom == "S5":
        x = sleeves.signal_s5(base["px06"]).reindex(w.index)
        sig = fen["fen5"].pow(2).ewm(halflife=risque.DEMI_VIE, min_periods=risque.MIN_OBS).mean().pow(0.5).shift(1)
    else:
        x = pd.DataFrame({"SPXUSD": np.sign(fen["matin"].reindex(w.index))})
        sig = fen["fen7"].to_frame("SPXUSD").pow(2).ewm(halflife=risque.DEMI_VIE, min_periods=risque.MIN_OBS).mean().pow(0.5).shift(1)
    wsig = (w * sig.reindex(columns=w.columns)).loc[a:b]
    x = x.reindex(columns=w.columns).loc[a:b]
    m = (wsig != 0).to_numpy() & np.isfinite(x.to_numpy(float)) & np.isfinite(wsig.to_numpy(float))
    if m.sum() < 30:
        return float("nan")
    xv, yv = x.to_numpy(float)[m], wsig.to_numpy(float)[m]
    if xv.std() == 0 or yv.std() == 0:
        return float("nan")
    return float(np.corrcoef(xv, yv)[0, 1])


# ----------------------------------------------------------------- Théme 2 : décroissance
def theme2_decroissance(base: dict, specs: dict[str, SpecQuotidienne], ic_minutes: dict) -> dict:
    out = {"horizons_jours": H_GRILLE, "sleeves_quotidiennes": {}, "minutes": ic_minutes,
           "principe": "net par jour = (G(h) - C)/h ; maximum quand 1 - (1+u)exp(-u) = C/A, u = h/tau, si G(h) = A(1 - exp(-h/tau))"}
    for nom, sp in specs.items():
        courbe = courbe_ic(sp)
        marg_all = {}
        for p in PERIODES:
            marg_all[p] = demi_vie_exponentielle(H_GRILLE, [courbe["marginal"][p][h]["ic"] for h in H_GRILLE])
        retards = (1, 5, 20, 60, 120, 250) if sp.espacement == 1 else (1, 2, 4, 8, 13)
        ac = autocorr_signal(sp.F, sp.espacement, retards)
        out["sleeves_quotidiennes"][nom] = {
            "ic": courbe, "demi_vie_ic_marginal_jours": marg_all,
            "autocorr_signal": ac, "demi_vie_signal_jours": demi_vie_signal(ac["autocorr"], sp.espacement),
            "profil_gain_cout": profil_gain_cout(sp) if nom in ("S1", "S2", "S3") else None,
        }
    return out


# ------------------------------------------------------------- Théme 3 : puissance
def theme3_puissance(train_val: dict, rend_val_nets: dict[str, np.ndarray]) -> dict:
    """Puissance statistique sur 4 ans de VAL, et probabilité qu'un vrai Sharpe de 0,5 donne ce qu'on a vu."""
    n_val = 1044  # jours de VAL (2019-2022)
    annees = n_val / 252
    out = {"n_jours_val": n_val, "annees_val": annees,
           "se_sharpe_val_sr0": theorie.se_sharpe(0.0, n_val), "se_sharpe_val_sr05": theorie.se_sharpe(0.5, n_val),
           "sharpe_min_detectable_80pct": {
               "unilateral_alpha5": theorie.sharpe_min_detectable(annees),
               "bilateral_alpha5": theorie.sharpe_min_detectable(annees, unilateral=False),
               "unilateral_bonferroni_7": theorie.sharpe_min_detectable(annees, n_tests=7),
               "bilateral_bonferroni_7": theorie.sharpe_min_detectable(annees, unilateral=False, n_tests=7)},
           "annees_pour_detecter_80pct_unilateral": {str(s): theorie.annees_pour_detecter(s) for s in (0.25, 0.5, 1.0, 2.0)},
           "par_serie": {}}
    for k, x in rend_val_nets.items():
        sr_obs = train_val["series"][k]["VAL"]["sharpe_net"]
        sk, ku = float(sps.skew(x)), float(sps.kurtosis(x, fisher=False))
        out["par_serie"][k] = {
            "sharpe_net_val": sr_obs, "se_lo_gaussienne": theorie.se_sharpe(sr_obs, len(x)),
            "se_mertens_asym_kurt": theorie.se_sharpe(sr_obs, len(x), sk, ku), "asymetrie": sk, "kurtosis": ku,
            "p_sharpe_vrai_05_donne_au_plus_obs": {
                "analytique": theorie.proba_sharpe_inferieur_analytique(sr_obs, 0.5, len(x)),
                "parametrique": theorie.proba_sharpe_inferieur_parametrique(sr_obs, 0.5, len(x), n_sim=10000),
                "bootstrap": theorie.proba_sharpe_inferieur_bootstrap(x, sr_obs, 0.5, n_sim=3000)},
            "p_sharpe_vrai_025_donne_au_plus_obs_analytique": theorie.proba_sharpe_inferieur_analytique(sr_obs, 0.25, len(x)),
            "p_sharpe_vrai_10_donne_au_plus_obs_analytique": theorie.proba_sharpe_inferieur_analytique(sr_obs, 1.0, len(x)),
        }
    return out


# ------------------------------------------------------ Théme 4 : tests multiples
# Nombres d'essais déclarés par un projet de recherche antérieur (non publié) sur le même univers et la même période VAL :
# cités tels quels, jamais estimés ici. Le plus grand (134) est un plancher déclaré, « pas un plafond ».
HISTORIQUE_ESSAIS = [
    ("exploration A", 9, "nombre d'essais déclaré (projet antérieur non publié)"),
    ("exploration B", 6, "nombre d'essais déclaré (projet antérieur non publié)"),
    ("exploration C", 12, "nombre d'essais déclaré (projet antérieur non publié)"),
    ("exploration D", 39, "nombre d'essais déclaré (projet antérieur non publié)"),
    ("exploration E", 50, "nombre d'essais déclaré (projet antérieur non publié)"),
    ("exploration F", 134, "plancher déclaré (« pas un plafond »), projet antérieur non publié"),
]


def theme4_tests_multiples(train_val: dict, rend_val_nets: dict[str, np.ndarray], n_rep: int = 1500) -> dict:
    sigma = theorie.se_sharpe(0.0, 1044)  # écart-type d'un Sharpe estimé sur VAL si le vrai Sharpe est nul
    sim = {}
    for n in (2, 4, 8, 20, 50, 134):
        m, s = theorie.simuler_sharpe_max(n, 1044, n_rep=n_rep)
        sim[str(n)] = {"formule": theorie.sharpe_max_attendu(n, sigma), "exact_gaussien": theorie.esperance_max_gaussien(n) * sigma,
                       "simulation_moyenne": m, "simulation_ecart_type": s}
    hist = [{"noeud": nom, "n_essais": n, "source": src, "sharpe_max_attendu_sigma_val": theorie.sharpe_max_attendu(n, sigma),
             "p_au_moins_un_sharpe_2": theorie.proba_au_moins_un_sharpe(2.0, n, sigma)} for nom, n, src in HISTORIQUE_ESSAIS]
    # N nécessaire pour qu'un Sharpe de 2 sorte du hasard, selon la durée du backtest
    besoins = {str(y): {"sigma_sr": 1.0 / np.sqrt(y), "n_essais_pour_sr_attendu_2": theorie.n_essais_pour_sharpe(2.0, 1.0 / np.sqrt(y))}
               for y in (1, 2, 4, 8)}
    # sur la durée de VAL : N pour que le hasard seul « fabrique » un Sharpe de 0,5 / 1 / 1,5 / 2
    cibles = {str(c): theorie.n_essais_pour_sharpe(c, sigma) for c in (0.5, 1.0, 1.5, 2.0)}
    illustration = {"n": 1770, "origine": "nombre de paires (60·59/2) d'un univers de 60 actifs : une illustration de sélection "
                                          "« la meilleure paire », PAS un compte d'essais documenté",
                    "sharpe_max_attendu_sans_edge": theorie.sharpe_max_attendu(1770, sigma)}
    # DSR du prereg (variance observée des 8 Sharpe, dominée par S7) vs seuil « théorique » (variance = SE^2)
    sh_q = np.array(list(train_val["dsr"]["sharpes_val_quotidiens"].values()))
    sr0_prereg = stats.sharpe_reference_dsr(sh_q) * np.sqrt(252)
    sr0_theo = theorie.sharpe_max_attendu(8, sigma)
    dsr_theo = {k: stats.psr(x, sr0_theo / np.sqrt(252)) for k, x in rend_val_nets.items()}
    return {"sigma_sharpe_val": sigma, "validation_formule_vs_simulation": sim, "historique_essais_anterieurs": hist,
            "n_essais_pour_sharpe_2_selon_duree_backtest_annees": besoins, "n_essais_pour_sharpe_cible_sur_4_ans": cibles,
            "illustration_selection_1770_paires": illustration,
            "dsr": {"sr0_annualise_prereg_variance_observee": sr0_prereg, "sr0_annualise_variance_theorique": sr0_theo,
                    "psr_contre_sr0_theorique_exploratoire": dsr_theo,
                    "lecture": "le SR0 du prereg (variance empirique des 8 Sharpe, tirée par S7 à -12) est 8x plus haut que le seuil théorique ; le verdict ne change pas (pile = -5,3)."}}


# -------------------------------------------------------- Théme 5 : anatomie de l'échec
SEUIL_BRUT = 0.30  # Sharpe brut en deçà duquel on dit « pas d'alpha brut » (~0,6 erreur-type d'un Sharpe sur 4 ans)


def sharpe_annuel_calendaire(x: pd.Series) -> pd.Series:
    g = x.dropna().groupby(x.dropna().index.year)
    return g.apply(lambda v: stats.sharpe(v) if len(v) >= 200 else np.nan).dropna()


def hetero_q(sharpes_an: pd.Series, n_par_an: int = 252) -> dict:
    """Test d'hétérogénéité (type Cochran) : Q = somme ((SR_a - SR_moyen)/SE)^2 ~ chi2(k-1) si le Sharpe est constant."""
    s = sharpes_an.to_numpy()
    se = np.array([theorie.se_sharpe(x, n_par_an) for x in s])
    w = 1.0 / se ** 2
    moy = float((w * s).sum() / w.sum())
    q = float((((s - moy) / se) ** 2).sum())
    return {"q": q, "ddl": int(len(s) - 1), "p_constance": float(sps.chi2.sf(q, len(s) - 1)), "sharpe_moyen_pondere": moy}


def cause_principale(brut_tr: float, brut_va: float, net_va: float, spread_regime: float, corr_indices: float = 0.0) -> dict:
    """Règle de décision EXPLICITE (décrite dans le README) :
    - brut >= 0,30 sur TRAIN ET VAL : l'alpha brut existe ; coût si les coûts mangent plus de la moitié du brut VAL.
    - brut >= 0,30 sur une seule période : « régime » si la sleeve est surtout un bêta actions (corrélation >= 0,5
      avec le facteur indices) ou si l'écart de Sharpe entre tercile de vol haut et bas dépasse 1 ; sinon « instabilité ».
    - sinon : pas d'alpha brut ; on note « + coût amplificateur » si les coûts retirent plus de 0,5 point de Sharpe en VAL."""
    perte_cout = brut_va - net_va
    if brut_tr >= SEUIL_BRUT and brut_va >= SEUIL_BRUT:
        cause = "coût" if perte_cout >= 0.5 * brut_va else "capacité / taille (alpha brut et net présents)"
        sec = ""
    elif brut_tr >= SEUIL_BRUT or brut_va >= SEUIL_BRUT:
        if abs(corr_indices) >= 0.5:
            cause, sec = "régime", "bêta actions : alpha brut présent sur une seule des deux périodes"
        elif abs(spread_regime) >= 1.0:
            cause, sec = "régime", "dépendance à la volatilité : alpha brut présent sur une seule des deux périodes"
        else:
            cause, sec = "instabilité", "alpha brut présent sur une seule des deux périodes"
    else:
        cause = "pas d'alpha brut"
        sec = "+ coût amplificateur" if perte_cout > 0.5 else ""
    return {"cause": cause, "precision": sec, "perte_de_sharpe_due_aux_couts_val": perte_cout}


def facteurs_marche(base: dict) -> tuple[pd.Series, pd.Series]:
    """(moyenne équipondérée des rendements des 58 actifs, moyenne équipondérée des 8 indices)."""
    prix, classes = base["prix"], base["classes"]
    rend = prix.ffill().pct_change(fill_method=None)
    idx_cols = [c for c in prix.columns if str(classes.get(c, "")).startswith("Indice")]
    return rend.mean(axis=1), rend[idx_cols].mean(axis=1)


def theme5_anatomie(base: dict, train_val: dict) -> dict:
    res, pile = base["res"], base["pile"]
    tout = {**res, "PILE": pile}
    fact_all, fact_idx = facteurs_marche(base)  # « marché » simple = moyenne équipondérée ; variante actions = 8 indices
    vol_idx = fact_idx.rolling(63, min_periods=40).std() * np.sqrt(252)
    vol_prec = vol_idx.shift(1)                  # connue la veille : pas de look-ahead
    q1, q2 = vol_prec.loc[:d.FIN_TRAIN].quantile([1 / 3, 2 / 3])
    regime = pd.Series(np.where(vol_prec <= q1, "bas", np.where(vol_prec <= q2, "moyen", "haut")), index=vol_prec.index)
    regime = regime.where(vol_prec.notna())
    out = {"facteur_marche": "moyenne équipondérée des rendements quotidiens des 58 actifs ; facteur indices = 8 indices",
           "regime_vol": {"variable": "vol réalisée 63 j (annualisée) du facteur indices, décalée d'un jour",
                          "seuils_terciles_train": [float(q1), float(q2)]}, "sleeves": {}}
    rolls, annuel = {}, {}
    for nom, r in tout.items():
        a0 = r.debut
        net, brut = r.net.loc[a0:], r.brut.loc[a0:]
        roll = net.rolling(252, min_periods=252).apply(lambda v: v.mean() / v.std(ddof=1) * np.sqrt(252) if v.std() > 0 else np.nan, raw=True)
        rolls[nom] = roll
        sa = sharpe_annuel_calendaire(net)
        annuel[nom] = sa
        s_tr = stats.sharpe(r.tranche(max(d.DEBUT_DONNEES, a0), d.FIN_TRAIN).brut)
        s_va = stats.sharpe(r.tranche(d.DEBUT_VAL, d.FIN_VAL).brut)
        n_va = stats.sharpe(r.tranche(d.DEBUT_VAL, d.FIN_VAL).net)
        n_tr = stats.sharpe(r.tranche(max(d.DEBUT_DONNEES, a0), d.FIN_TRAIN).net)
        reg = {}
        for g in ("bas", "moyen", "haut"):
            idx = regime[regime == g].index.intersection(brut.index)
            reg[g] = {"jours": int(len(idx)), "sharpe_brut": stats.sharpe(brut.loc[idx]), "sharpe_net": stats.sharpe(net.loc[idx])}
        sp = reg["haut"]["sharpe_brut"] - reg["bas"]["sharpe_brut"]
        bet = {}
        for p, (a, b) in PERIODES.items():
            y = net.loc[max(a, a0):b]
            row = {}
            for fn, f in (("tous_actifs", fact_all), ("indices", fact_idx)):
                x = f.reindex(y.index)
                row[fn] = {"correlation": float(y.corr(x)), "beta": float(np.cov(x[y.notna() & x.notna()], y[y.notna() & x.notna()], ddof=1)[0, 1] / x.var(ddof=1))}
            bet[p] = row
        valid = roll.dropna()
        out["sleeves"][nom] = {
            "debut_actif": str(a0.date()), "sharpe_brut": {"TRAIN": s_tr, "VAL": s_va}, "sharpe_net": {"TRAIN": n_tr, "VAL": n_va},
            "cout_annuel": {"TRAIN": train_val["series"][nom]["TRAIN"]["cout_annuel"], "VAL": train_val["series"][nom]["VAL"]["cout_annuel"]},
            "rotation_annuelle_val": train_val["series"][nom]["VAL"]["rotation_annuelle"],
            "sharpe_annuel_calendaire_net": {str(y): float(v) for y, v in sa.items()},
            "constance": hetero_q(sa), "part_annees_sharpe_net_positif": float((sa > 0).mean()),
            "sharpe_glissant_1an_net": {"min": float(valid.min()), "max": float(valid.max()), "ecart_type": float(valid.std()),
                                        "part_positive": float((valid > 0).mean()), "n_points": int(len(valid))},
            "facteur": bet, "regime": reg, "ecart_sharpe_brut_haut_moins_bas": sp,
            "cause": cause_principale(s_tr, s_va, n_va, sp, bet["VAL"]["indices"]["correlation"]),
        }
    out["_roll"], out["_annuel"] = rolls, annuel
    return out


# -------------------------------------------------------- Théme 6 : diversification
def theme6_diversification(train_val: dict) -> dict:
    noms = ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]
    corr = pd.DataFrame(train_val["correlations"]["VAL"]).loc[noms, noms].to_numpy()
    rho = theorie.correlation_moyenne(corr)
    s_val = np.array([train_val["series"][k]["VAL"]["sharpe_net"] for k in noms])
    matrice = theorie.sharpe_pile_matrice(s_val, corr)
    # les poids de la pile sont ∝ 1/vol TRAIN (~égaux) : la formule « risque égal » doit retrouver le Sharpe réalisé
    sh_pile = train_val["series"]["PILE"]["VAL"]["sharpe_net"]
    grille = {}
    for s in (0.3, 0.5, 0.7, 1.0):
        grille[str(s)] = {str(r): {"n_requis": theorie.n_sleeves_requis(s, r), "plafond_sr": (s / np.sqrt(r) if r > 0 else None)}
                          for r in (0.0, round(rho, 4), 0.05, 0.10, 0.20)}
    n_req = theorie.n_sleeves_requis(0.5, rho)
    s_requis_7 = None
    # Sharpe individuel nécessaire avec 7 sleeves à la corrélation observée
    s_requis_7 = 2.0 * np.sqrt((1 + 6 * rho) / 7)
    return {"rho_moyen_val": rho, "n_sleeves": 7, "sharpe_net_val_par_sleeve": dict(zip(noms, s_val.tolist())),
            "pile_formule_risque_egal_avec_sharpe_reels": matrice["risque_egal"], "pile_optimale_theorique_sharpe_reels": matrice["optimal_theorique"],
            "pile_realisee_val": sh_pile,
            "sharpe_pile_si_7_sleeves_de_sharpe_05": theorie.sharpe_pile(0.5, 7, rho),
            "sharpe_pile_si_7_sleeves_de_sharpe_05_independantes": theorie.sharpe_pile(0.5, 7, 0.0),
            "n_sleeves_requis_sharpe_05_rho_observe": n_req, "n_sleeves_requis_sharpe_05_independantes": theorie.n_sleeves_requis(0.5, 0.0),
            "sharpe_individuel_requis_avec_7_sleeves": s_requis_7, "plafond_sharpe_pile_sleeves_05_rho_observe": 0.5 / np.sqrt(rho) if rho > 0 else None,
            "grille_n_requis": grille,
            "meilleur_sharpe_net_val": float(s_val.max()), "meilleure_sleeve": noms[int(s_val.argmax())]}


# ----------------------------------------------------------- Théme 7 : capacité / impact
# Hypothèses d'ordre de grandeur, NON sourcées : à remplacer par les volumes du courtier.
ADV_USD = {"FX": 1.0e10, "Indice": 5.0e10, "Matière": 5.0e9}
Y_IMPACT = 1.0  # préfacteur de l'impact racine carrée : impact = Y sigma racine(Q/ADV)


def adv_actif(classes: pd.Series, cols) -> pd.Series:
    def un(c):
        cl = str(classes.get(c, "FX"))
        return ADV_USD["Indice"] if cl.startswith("Indice") else ADV_USD["Matière"] if cl.startswith("Mati") else ADV_USD["FX"]
    return pd.Series({c: un(c) for c in cols})


def theme7_capacite(base: dict, specs: dict[str, SpecQuotidienne], facteur_adv: float = 1.0) -> dict:
    """Impact en racine carrée : coût d'un ordre de taille Q = Y sigma racine(Q/ADV) x Q. Pour un capital A,
    coût annuel d'impact = racine(A) x K avec K = somme sur (jours, actifs) de Y sigma |de|^1,5 / racine(ADV) par an.
    Capacité = A tel que rendement brut - coût réel - impact = 0 ; elle est proportionnelle à ADV."""
    out = {"hypotheses": {"ADV_usd_par_jour": ADV_USD, "Y": Y_IMPACT,
                          "avertissement": "volumes et préfacteur d'ordre de grandeur, NON sourcés ; capacité ∝ ADV, ∝ (rendement net avant impact)^2"},
           "sleeves": {}}
    for nom in ("S1", "S6"):
        sp = specs[nom]
        w = sp.W.fillna(0.0)
        e = w.shift(1).fillna(0.0)                      # position exécutée (J+1)
        de = e.diff().fillna(e).abs()
        adv = adv_actif(base["classes"], w.columns) * facteur_adv
        sig = sp.sigma[w.columns].reindex(w.index).fillna(0.0)
        res = base["res"][nom]
        blocs = {}
        for p, (a, b) in PERIODES.items():
            a2 = max(a, res.debut)
            ans = len(de.loc[a2:b]) / 252
            K = float((Y_IMPACT * sig * de ** 1.5 / np.sqrt(adv.to_numpy())[None, :]).loc[a2:b].sum().sum() / ans)
            sub = res.tranche(a2, b)
            brut, cout = float(sub.brut.mean() * 252), float(sub.cout.mean() * 252)
            net0 = brut - cout
            cap = (net0 / K) ** 2 if (net0 > 0 and K > 0) else 0.0
            cap_cout = (cout / K) ** 2 if K > 0 else None
            blocs[p] = {"rendement_brut_annuel": brut, "cout_reel_annuel": cout, "rendement_net_avant_impact": net0,
                        "K_impact_par_racine_usd": K, "capacite_usd": cap, "usd_ou_impact_egale_cout_reel": cap_cout,
                        "impact_annuel_a_1e8_usd": K * np.sqrt(1e8), "impact_annuel_a_1e9_usd": K * np.sqrt(1e9),
                        "sharpe_brut": stats.sharpe(sub.brut)}
        out["sleeves"][nom] = blocs
    return out
